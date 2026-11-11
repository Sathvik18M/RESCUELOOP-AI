from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator
from app.core.config import get_settings
from app.persistence.models import Job, Message, Merchant, Customer, Conversation, Order, now
from app.persistence.session import get_db
from app.domain.cases import delivered_completion, flag
from app.domain.common import audit

router = APIRouter(prefix="/webhooks/twilio", tags=["Twilio WhatsApp"])


async def verified_form(request):
    s = get_settings()
    if s.whatsapp_provider != "twilio":
        raise HTTPException(404, "Provider is disabled")
    raw = await request.body()
    if len(raw) > 1024 * 1024:
        raise HTTPException(413, "Payload too large")
    form = await request.form()
    if not s.twilio_auth_token or not s.public_webhook_url:
        raise HTTPException(503, "Webhook is not configured")
    url = s.public_webhook_url.rstrip("/") + request.url.path
    if request.url.query:
        url += "?" + request.url.query
    if not RequestValidator(s.twilio_auth_token).validate(
        url, form, request.headers.get("X-Twilio-Signature", "")
    ):
        raise HTTPException(403, "Invalid webhook signature")
    if form.get("AccountSid") != s.twilio_account_sid:
        raise HTTPException(403, "Unexpected account")
    return form


def apply_delivery(db, msg, status):
    ranks = {"queued": 0, "sending": 1, "sent": 2, "delivered": 3, "read": 4}
    if status in {"failed", "undelivered"}:
        if msg.status in {"delivered", "read"}:
            return
        msg.status = "failed"
        from app.persistence.models import Case

        for cid in msg.case_ids:
            case = db.get(Case, cid)
            if case:
                if msg.completes_case and case.details.get("last_solution") == msg.id:
                    case.details = {**case.details, "notification_failure": msg.id}
                flag(db, case, "Customer notification failed. Verify delivery before closing the case.")
    elif status in ranks and ranks[status] > ranks.get(msg.status, -1):
        msg.status = status
    delivered_completion(db, msg)


@router.post("/incoming")
async def incoming(request: Request, db: Session = Depends(get_db)):
    form = await verified_form(request)
    s = get_settings()
    if form.get("To") != s.twilio_whatsapp_from:
        raise HTTPException(403, "Unexpected recipient")
    sid = form.get("MessageSid", "")
    if not sid.startswith("SM") or len(sid) > 100:
        raise HTTPException(422, "Missing message identifier")
    if db.get(Message, sid):
        return Response("<Response/>", media_type="application/xml")
    merchant = db.scalar(select(Merchant).where(Merchant.id == s.twilio_merchant_id).with_for_update())
    if not merchant:
        raise HTTPException(503, "Store mapping is missing")
    phone = form.get("From", "")
    if not phone.startswith("whatsapp:+"):
        raise HTTPException(422, "Expected a WhatsApp sender")
    phone = phone.removeprefix("whatsapp:")
    customer = db.scalar(select(Customer).where(Customer.merchant_id == merchant.id, Customer.phone == phone))
    if not customer:
        customer = Customer(merchant_id=merchant.id, name="Unverified WhatsApp customer", phone=phone)
        db.add(customer)
        db.flush()
    conv = db.scalar(
        select(Conversation)
        .where(Conversation.customer_id == customer.id, Conversation.channel == "whatsapp",
               Conversation.messaging_provider == "twilio")
        .with_for_update()
    )
    if not conv:
        orders = list(
            db.scalars(
                select(Order).where(Order.customer_id == customer.id, Order.merchant_id == merchant.id)
            )
        )
        conv = Conversation(
            merchant_id=merchant.id,
            customer_id=customer.id,
            channel="whatsapp",
            messaging_provider="twilio",
            provider_recipient=phone,
            order_id=orders[0].id if len(orders) == 1 else None,
        )
        db.add(conv)
        db.flush()
    conv.last_inbound_at = now()
    conv.provider_recipient = phone
    media = []
    try:
        count = int(form.get("NumMedia", "0"))
    except ValueError:
        raise HTTPException(422, "Invalid media count")
    if count < 0 or count > 4:
        raise HTTPException(422, "Send up to four photos per message")
    for i in range(count):
        mime = form.get(f"MediaContentType{i}", "")
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(422, "Unsupported media type")
        media.append(form.get(f"MediaUrl{i}", ""))
    body = str(form.get("Body", ""))[:4000]
    db.add(
        Message(
            id=sid,
            provider_id=sid,
            conversation_id=conv.id,
            role="customer",
            body=body or "Photo attached",
            status="received",
            processed=False,
        )
    )
    db.add(
        Job(
            id=f"incoming:{sid}",
            kind="incoming_message",
            payload={"message_id": sid, "conversation_id": conv.id, "media": media},
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if not db.get(Message, sid):
            raise
    return Response("<Response/>", media_type="application/xml")


@router.post("/status")
async def delivery_status(request: Request, db: Session = Depends(get_db)):
    form = await verified_form(request)
    s = get_settings()
    msg = db.get(Message, request.query_params.get("local_id", ""))
    if not msg:
        msg = db.scalar(select(Message).where(Message.provider_id == form.get("MessageSid")))
    if msg:
        conv = db.get(Conversation, msg.conversation_id)
        if conv.merchant_id != s.twilio_merchant_id or conv.messaging_provider != "twilio" or msg.role == "customer":
            raise HTTPException(403, "Unexpected status target")
        if msg.provider_id and msg.provider_id != form.get("MessageSid"):
            raise HTTPException(409, "Provider identifier mismatch")
        msg.provider_id = form.get("MessageSid")
        apply_delivery(db, msg, str(form.get("MessageStatus", "")))
        audit(db, conv.merchant_id, "twilio", "message.delivery", msg.id, status=msg.status)
        db.commit()
    return Response("<Response/>", media_type="application/xml")
