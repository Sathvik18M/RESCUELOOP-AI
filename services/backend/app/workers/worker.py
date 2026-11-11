"""Run with python -m app.workers.worker. Jobs and effects are persisted independently."""

import logging
import math
import time
from datetime import timedelta
from sqlalchemy import select, or_, text
import httpx
from app.core.config import get_settings
from app.persistence.models import (
    Job,
    Conversation,
    Customer,
    Message,
    Case,
    Operation,
    Refund,
    Reservation,
    PickupSlot,
    ServiceState,
    Merchant,
    now,
)
from app.persistence.session import SessionLocal
from app.integrations.whatsapp import (
    get_provider, download_media, WindowClosed, PermanentProviderError, ProviderDisabled,
)
from app.domain.messaging import apply_receipts
from app.domain.common import audit, reply, utc
from app.domain.cases import flag, support_case
from app.domain.conversations import receive
from app.domain.commerce import complete_operation
from app.domain.evidence import save_evidence

logger = logging.getLogger("rescueloop.worker")


def permanent(exc):
    status = getattr(exc, "status_code", None)
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
    return isinstance(exc, PermanentProviderError) or (
        isinstance(status, int) and 400 <= status < 500 and status not in {408, 409, 429}
    )


def delay_for(attempt, exc):
    minimum = 5 if attempt == 1 else 15
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            minimum = max(minimum, math.ceil(float(response.headers.get("retry-after", "0"))))
        except ValueError:
            pass
    return minimum


def process_incoming(db, job):
    p = job.payload
    conv = db.scalar(select(Conversation).where(Conversation.id == p["conversation_id"]).with_for_update())
    msg = db.get(Message, p["message_id"])
    if msg.processed:
        return
    get_provider(conv.messaging_provider)
    # Earlier pending messages block later turns from overtaking a retry.
    earlier = list(
        db.scalars(
            select(Message).where(
                Message.conversation_id == conv.id,
                Message.role == "customer",
                Message.processed.is_(False),
                Message.created_at < msg.created_at,
            )
        )
    )
    if earlier:
        job.status = "pending"
        job.attempts -= 1
        job.available_at = now() + timedelta(seconds=2)
        return
    if p.get("unsupported_type"):
        case = support_case(db, conv, "technical", "WhatsApp attachment needs seller review")
        flag(db, case, "This Sandbox cannot retrieve media. Ask for a text description or review the attachment manually.")
        msg.case_ids = [case.id]
        msg.processed = True
        reply(db, conv, "This test WhatsApp connection supports text only. Please describe the issue in a message; the store can review attachments separately.", role="system", cases=[case])
        audit(db, conv.merchant_id, conv.messaging_provider, "whatsapp.media_unsupported", msg.id)
    elif p.get("media"):
        if msg.body != "Photo attached":
            receive(db, conv, msg.body, msg.id)
        for url in p["media"]:
            case_id = msg.case_ids[0] if len(msg.case_ids) == 1 else None
            save_evidence(db, conv, download_media(url, conv.messaging_provider), "whatsapp-photo.jpg", case_id=case_id)
        msg.processed = True
    else:
        receive(db, conv, msg.body, msg.id)


def send_job(db, job):
    msg = db.get(Message, job.payload["message_id"])
    conv = db.scalar(select(Conversation).where(Conversation.id == msg.conversation_id).with_for_update())
    if conv.handoff and msg.role == "assistant":
        msg.status = "held_for_seller"
        job.status = "held"
        return
    if msg.status in {"sending", "uncertain"}:
        msg.status = "uncertain"
        job.status = "needs_review"
        for cid in msg.case_ids:
            case = db.get(Case, cid)
            if case:
                flag(db, case, "Message delivery is uncertain. Reconcile its provider status.")
        return
    if msg.status in {"sent", "delivered", "read"} or msg.provider_id:
        return
    provider = get_provider(conv.messaging_provider)
    provider.credentials()
    if now() - utc(conv.last_inbound_at) > timedelta(hours=24):
        job.status = "waiting_window"
        msg.status = "waiting_window"
        job.attempts -= 1
        return
    # Serialize sends per provider; never route an old conversation through a new provider.
    send_key = provider.name + "-send"
    interval = provider.minimum_send_interval
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": "rescueloop-" + send_key})
    state = db.scalar(select(ServiceState).where(ServiceState.id == send_key).with_for_update())
    if state and (now() - utc(state.updated_at)).total_seconds() < interval:
        job.status = "pending"
        job.attempts -= 1
        job.available_at = utc(state.updated_at) + timedelta(seconds=interval)
        return
    customer = db.get(Customer, conv.customer_id)
    msg.status = "sending"
    if not state:
        db.add(ServiceState(id=send_key))
    else:
        state.updated_at = now()
    db.commit()  # Preserve the send marker before crossing the provider boundary.
    # A second handoff check covers changes between the marker commit and the send.
    conv = db.scalar(
        select(Conversation)
        .where(Conversation.id == conv.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if conv.handoff and msg.role == "assistant":
        msg.status = "held_for_seller"
        job.status = "held"
        return
    sid = provider.send_text(conv.provider_recipient or customer.phone, msg.body, conv.last_inbound_at, msg.id)
    # Serialize provider-ID association with receipt ingestion to close the callback race.
    db.scalar(select(Merchant).where(Merchant.id == conv.merchant_id).with_for_update())
    db.refresh(msg)
    msg.provider_id = sid
    if msg.status == "sending":
        msg.status = "queued"
    audit(db, conv.merchant_id, "worker", "whatsapp.accepted", msg.id, provider=provider.name)
    apply_receipts(db, msg)


def maintenance(db):
    for reservation in db.scalars(select(Reservation).where(Reservation.status.in_(["reserved", "ready"]))):
        slot = db.get(PickupSlot, reservation.slot_id)
        case = db.get(Case, reservation.case_id)
        if slot.ends_at and utc(slot.ends_at) < now() and not case.details.get("missed_window"):
            case.details = {**case.details, "missed_window": True}
            flag(db, case, "Pickup window ended. Stock remains held until collection or cancellation.")
    state = db.get(ServiceState, "worker")
    if not state:
        db.add(ServiceState(id="worker", detail={"status": "running"}))
    else:
        state.updated_at = now()
        state.detail = {"status": "running"}


def execute_job(db, job):
    job.status = "processing"
    if job.kind == "incoming_message":
        process_incoming(db, job)
    elif job.kind == "send_message":
        send_job(db, job)
    elif job.kind == "operation":
        operation = db.scalar(
            select(Operation).where(Operation.id == job.payload["operation_id"]).with_for_update()
        )
        if operation:
            complete_operation(db, operation)
    elif job.kind == "case_expire":
        case = db.get(Case, job.payload["case_id"])
        if (
            case
            and case.proposal_revision == job.payload.get("revision")
            and case.status == "pending_customer"
            and utc(case.expires_at) <= now()
        ):
            flag(db, case, "Proposal expired. Issue a fresh proposal after rechecking terms.")
            reply(
                db,
                db.get(Conversation, case.conversation_id),
                "Your proposal expired. The store can issue updated terms.",
                role="system",
                cases=[case],
            )
    if job.status == "processing":
        job.status = "done"


def fail_job(db, job, exc):
    job.error = type(exc).__name__
    if isinstance(exc, ProviderDisabled):
        job.status = "waiting_provider"
        job.attempts -= 1
        return
    if isinstance(exc, WindowClosed):
        job.status = "waiting_window"
        job.attempts -= 1
        return
    uncertain = False
    if job.kind == "send_message":
        msg = db.get(Message, job.payload["message_id"])
        if msg.status == "sending":
            # A definitive HTTP rejection did not accept the send; a transport failure may have.
            definitive = isinstance(exc, PermanentProviderError) or (
                isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500
            )
            msg.status = "failed" if definitive else "uncertain"
            uncertain = not definitive
    job.status = (
        "needs_review" if uncertain else "failed" if permanent(exc) or job.attempts >= 3 else "pending"
    )
    job.available_at = now() + timedelta(seconds=delay_for(job.attempts, exc))
    if job.status in {"failed", "needs_review"}:
        conv = None
        ids = []
        if job.kind in {"incoming_message", "send_message"}:
            msg = db.get(Message, job.payload["message_id"])
            conv = db.get(Conversation, msg.conversation_id)
            ids = msg.case_ids
            if job.kind == "incoming_message":
                msg.processed = True
        elif job.kind == "operation":
            op = db.get(Operation, job.payload["operation_id"])
            ids = [op.case_id]
            op.status = "uncertain" if uncertain else "failed"
            refund = db.scalar(select(Refund).where(Refund.case_id == op.case_id))
            if refund and refund.status == "pending":
                refund.status = "uncertain" if uncertain else "failed"
        if not ids and conv:
            ids = [support_case(db, conv, "technical", "Processing needs seller review").id]
        for cid in ids:
            case = db.get(Case, cid)
            if case:
                flag(
                    db,
                    case,
                    "Integration unavailable or processing failed. Technical retries did not count as failed customer resolutions.",
                )
        if job.kind == "incoming_message" and conv:
            from app.agents.client import provider_error_code

            msg.case_ids = list(dict.fromkeys([*msg.case_ids, *ids]))
            audit(db, conv.merchant_id, "worker", "message.processing_failed", msg.id,
                  job_id=job.id, attempts=job.attempts, error_type=type(exc).__name__,
                  provider_error_code=provider_error_code(exc), case_ids=ids)
            notice_id = "processing-error:" + msg.id
            # Idempotent service notice, explicitly not a model-generated answer.
            if not conv.handoff and not db.get(Message, notice_id):
                reply(db, conv,
                      "I'm having trouble processing this message. I've saved it for the store team to review. Please include your order reference if available.",
                      role="system", message_id=notice_id,
                      cases=[db.get(Case, cid) for cid in ids if db.get(Case, cid)])
    logger.warning("Job failed: %s (%s)", job.id, type(exc).__name__)


def run_once():
    with SessionLocal() as db:
        maintenance(db)
        db.commit()
        job = db.scalar(
            select(Job)
            .where(
                or_(
                    (Job.status == "pending") & (Job.available_at <= now()),
                    (Job.status == "processing") & (Job.locked_until < now()),
                )
            )
            .order_by(Job.available_at, Job.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return False
        job.status = "processing"
        job.attempts += 1
        job.locked_until = now() + timedelta(minutes=15)
        jid = job.id
        db.commit()
        try:
            execute_job(db, job)
            db.commit()
        except Exception as exc:
            db.rollback()
            job = db.get(Job, jid)
            fail_job(db, job, exc)
            db.commit()
    return True


if __name__ == "__main__":
    from contextlib import ExitStack
    from app.agents.workflows import orchestrator

    s = get_settings()
    s.validate_runtime()
    logging.basicConfig(level=logging.INFO)
    with ExitStack() as stack:
        if s.database_url.startswith("postgresql"):
            from app.agents.workflows.checkpoints import checkpoint_store

            orchestrator.workflow = orchestrator.build_graph(stack.enter_context(checkpoint_store()))
        while True:
            if not run_once():
                time.sleep(1)
