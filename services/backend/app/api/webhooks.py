import hashlib
import hmac
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.models import Job, Message
from app.db.session import get_db

router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks"])


@router.get("")
def verify(request: Request):
    settings = get_settings()
    supplied = request.query_params.get("hub.verify_token", "")
    if (
        not settings.whatsapp_verify_token
        or request.query_params.get("hub.mode") != "subscribe"
        or not hmac.compare_digest(supplied, settings.whatsapp_verify_token)
    ):
        raise HTTPException(403, "Verification failed")
    return PlainTextResponse(request.query_params.get("hub.challenge", ""))


@router.post("")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    raw = await request.body()
    if len(raw) > 1024 * 1024:
        raise HTTPException(413, "Payload too large")
    signature = request.headers.get("x-hub-signature-256", "")
    expected = "sha256=" + hmac.new(settings.whatsapp_app_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not settings.whatsapp_app_secret or not hmac.compare_digest(signature, expected):
        raise HTTPException(403, "Invalid webhook signature")
    try:
        payload = json.loads(raw)
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                if value.get("metadata", {}).get("phone_number_id") != settings.whatsapp_phone_number_id:
                    continue
                for incoming in value.get("messages", []):
                    job_id = f"incoming:{incoming['id']}"
                    if not db.get(Job, job_id):
                        db.add(Job(id=job_id, kind="incoming_message", payload=incoming))
                for status in value.get("statuses", []):
                    msg = db.scalar(select(Message).where(Message.provider_id == status.get("id")))
                    if msg and status.get("status") in {"sent", "delivered", "read", "failed"}:
                        ranks = {"sent": 1, "delivered": 2, "read": 3}
                        value_status = status["status"]
                        if value_status == "failed" or ranks.get(value_status, 0) > ranks.get(msg.status, 0):
                            msg.status = value_status
        db.commit()
    except (ValueError, KeyError, TypeError) as exc:
        db.rollback()
        raise HTTPException(422, "Malformed webhook") from exc
    return {"received": True}
