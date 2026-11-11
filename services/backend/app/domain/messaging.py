"""Persist normalized provider events before handing them to existing agent jobs."""

import hashlib

from sqlalchemy import select

from app.domain.common import audit, utc
from app.persistence.models import Conversation, Customer, DeliveryReceipt, Job, Message, Order


def save_incoming(
    db,
    *,
    merchant_id,
    provider,
    recipient,
    phone,
    provider_id,
    message_id,
    body,
    received_at,
    media=None,
    unsupported_type=None,
):
    if db.get(Message, message_id):
        return False
    conv = db.scalar(
        select(Conversation)
        .where(
            Conversation.merchant_id == merchant_id,
            Conversation.channel == "whatsapp",
            Conversation.messaging_provider == provider,
            Conversation.provider_recipient == recipient,
        )
        .with_for_update()
    )
    if not conv:
        customer = (
            db.scalar(
                select(Customer).where(
                    Customer.merchant_id == merchant_id,
                    Customer.phone == phone,
                )
            )
            if phone
            else None
        )
        if not customer:
            customer = Customer(merchant_id=merchant_id, name="Unverified WhatsApp customer", phone=phone)
            db.add(customer)
            db.flush()
        # Preserve conversations created before provider pinning was introduced.
        if provider == "twilio":
            conv = db.scalar(
                select(Conversation)
                .where(
                    Conversation.customer_id == customer.id,
                    Conversation.channel == "whatsapp",
                    Conversation.messaging_provider == provider,
                    Conversation.provider_recipient.is_(None),
                )
                .with_for_update()
            )
        if not conv:
            orders = list(
                db.scalars(
                    select(Order).where(
                        Order.customer_id == customer.id,
                        Order.merchant_id == merchant_id,
                    )
                )
            )
            conv = Conversation(
                merchant_id=merchant_id,
                customer_id=customer.id,
                channel="whatsapp",
                messaging_provider=provider,
                provider_recipient=recipient,
                order_id=orders[0].id if len(orders) == 1 else None,
                last_inbound_at=received_at,
            )
            db.add(conv)
            db.flush()
        else:
            conv.provider_recipient = recipient
    conv.last_inbound_at = max(utc(conv.last_inbound_at), received_at)
    db.add(
        Message(
            id=message_id,
            provider_id=provider_id,
            conversation_id=conv.id,
            role="customer",
            body=body,
            status="received",
            processed=False,
            created_at=received_at,
        )
    )
    db.add(
        Job(
            id=f"incoming:{message_id}",
            kind="incoming_message",
            payload={
                "message_id": message_id,
                "conversation_id": conv.id,
                "provider": provider,
                "media": media or [],
                "unsupported_type": unsupported_type,
            },
        )
    )
    audit(db, merchant_id, provider, "whatsapp.received", message_id, provider=provider)
    return True


def record_receipt(db, *, merchant_id, provider, provider_id, recipient, status):
    key = hashlib.sha256(f"{merchant_id}:{provider}:{provider_id}:{status}".encode()).hexdigest()
    if db.get(DeliveryReceipt, key):
        return
    db.add(
        DeliveryReceipt(
            id=key,
            merchant_id=merchant_id,
            provider=provider,
            provider_id=provider_id,
            recipient=recipient,
            status=status,
        )
    )
    db.flush()
    msg = db.scalar(select(Message).where(Message.provider_id == provider_id))
    if msg:
        apply_receipts(db, msg)


def apply_receipts(db, msg):
    from app.api.webhooks import apply_delivery

    conv = db.get(Conversation, msg.conversation_id)
    if msg.role == "customer":
        return
    receipts = list(
        db.scalars(
            select(DeliveryReceipt)
            .where(
                DeliveryReceipt.merchant_id == conv.merchant_id,
                DeliveryReceipt.provider == conv.messaging_provider,
                DeliveryReceipt.provider_id == msg.provider_id,
                DeliveryReceipt.recipient == conv.provider_recipient,
            )
            .order_by(DeliveryReceipt.created_at)
        )
    )
    for item in receipts:
        previous = msg.status
        apply_delivery(db, msg, item.status)
        if msg.status != previous:
            audit(
                db,
                conv.merchant_id,
                item.provider,
                "message.delivery",
                msg.id,
                status=msg.status,
                provider=item.provider,
                receipt_id=item.id,
            )
    return bool(receipts)
