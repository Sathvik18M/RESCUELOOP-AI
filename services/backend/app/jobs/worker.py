"""Durable PostgreSQL outbox worker. Run with python -m app.jobs.worker."""

import logging
import time
from datetime import timedelta
from sqlalchemy import or_, select
from app.core.config import get_settings
from app.db.models import Job, Conversation, Customer, Merchant, Message, Order, Case, now
from app.db.session import SessionLocal
from app.integrations.whatsapp import download_media, send_text
from app.modules.common import audit, reply
from app.modules.conversations import receive
from app.modules.evidence import save_evidence

logger = logging.getLogger("rescueloop.worker")


def process_incoming(db, job):
    incoming = job.payload
    phone = incoming["from"]
    settings = get_settings()
    merchant = db.scalar(
        select(Merchant).where(
            Merchant.settings["whatsapp_phone_number_id"].as_string() == settings.whatsapp_phone_number_id
        )
    )
    if not merchant:
        raise ValueError("No merchant is mapped to this WhatsApp phone number")
    # Lock the merchant to serialize first-contact customer/conversation creation.
    merchant = db.scalar(select(Merchant).where(Merchant.id == merchant.id).with_for_update())
    customer = db.scalar(select(Customer).where(Customer.merchant_id == merchant.id, Customer.phone == phone))
    if not customer:
        customer = Customer(merchant_id=merchant.id, name="WhatsApp customer", phone=phone)
        db.add(customer)
        db.flush()
    conv = db.scalar(
        select(Conversation)
        .where(Conversation.customer_id == customer.id, Conversation.channel == "whatsapp")
        .with_for_update()
    )
    if not conv:
        order = db.scalar(
            select(Order).where(Order.customer_id == customer.id).order_by(Order.created_at.desc()).limit(1)
        )
        conv = Conversation(
            merchant_id=merchant.id,
            customer_id=customer.id,
            order_id=order.id if order else None,
            channel="whatsapp",
        )
        db.add(conv)
        db.flush()
    if incoming.get("type") == "image":
        if not db.get(Message, incoming["id"]):
            content = download_media(incoming["image"]["id"])
            db.add(
                Message(
                    id=incoming["id"],
                    conversation_id=conv.id,
                    role="customer",
                    body=incoming["image"].get("caption", "Photo attached"),
                    status="received",
                )
            )
            conv.last_inbound_at = now()
            save_evidence(db, conv, content, "whatsapp-photo.jpg")
    else:
        text = incoming.get("text", {}).get("body", "Unsupported message type. Please send text or a photo.")
        receive(db, conv, text[:4000], incoming["id"])


def run_once():
    with SessionLocal() as db:
        job = db.scalar(
            select(Job)
            .where(
                or_(
                    (Job.status == "pending") & (Job.available_at <= now()),
                    (Job.status == "processing") & (Job.locked_until < now()),
                )
            )
            .order_by(Job.available_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return False
        job.status = "processing"
        job.attempts += 1
        job.locked_until = now() + timedelta(minutes=3)
        job_id = job.id
        db.commit()
        try:
            if job.kind == "incoming_message":
                process_incoming(db, job)
            elif job.kind == "case_expire":
                case = db.scalar(select(Case).where(Case.id == job.payload["case_id"]).with_for_update())
                if case and case.status in {"pending_seller", "pending_customer", "needs_details"}:
                    case.status = "expired"
                    conv = db.get(Conversation, case.conversation_id)
                    if not conv.handoff:
                        reply(
                            db,
                            conv,
                            "Your pending request has expired. Send a new request whenever you're ready.",
                        )
                    audit(db, case.merchant_id, "worker", "case.expired", case.id)
            elif job.kind == "send_message":
                msg = db.get(Message, job.payload["message_id"])
                if msg.status in {"sending", "uncertain"}:
                    msg.status = "uncertain"
                    job.status = "needs_review"
                    job.error = "Delivery outcome is uncertain; verify in WhatsApp before resending"
                    db.commit()
                    return True
                if msg.status not in {"sent", "delivered", "read"}:
                    conv = db.get(Conversation, msg.conversation_id)
                    customer = db.get(Customer, conv.customer_id)
                    msg.status = "sending"
                    db.commit()
                    provider_id = send_text(customer.phone, msg.body, conv.last_inbound_at)
                    msg.provider_id = provider_id
                    msg.status = "sent"
                    audit(db, conv.merchant_id, "worker", "whatsapp.sent", msg.id)
            job.status = "done"
            job.error = None
            db.commit()
        except Exception as exc:
            db.rollback()
            job = db.get(Job, job_id)
            # Do not log credentials, payloads, or provider response bodies.
            job.error = type(exc).__name__
            if job.kind == "send_message":
                msg = db.get(Message, job.payload["message_id"])
                if msg.status == "sending":
                    msg.status = "uncertain"
                    job.status = "needs_review"
                else:
                    job.status = "failed" if job.attempts >= 5 else "pending"
            else:
                job.status = "failed" if job.attempts >= 5 else "pending"
            job.available_at = now() + timedelta(seconds=min(300, 2**job.attempts))
            db.commit()
            logger.warning("Job %s failed (%s)", job_id, type(exc).__name__)
    return True


if __name__ == "__main__":
    from contextlib import ExitStack
    from app.workflows import orchestrator

    settings = get_settings()
    settings.validate_runtime()
    logging.basicConfig(level=logging.INFO)
    with ExitStack() as stack:
        if settings.database_url.startswith("postgresql"):
            from app.workflows.checkpoints import checkpoint_store

            saver = stack.enter_context(checkpoint_store())
            orchestrator.workflow = orchestrator.build_graph(saver)
        while True:
            if not run_once():
                time.sleep(2)
