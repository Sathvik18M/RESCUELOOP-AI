"""Authenticated development-only 360dialog Sandbox webhook.

Sandbox documents URL registration, not payload signatures/custom headers. A random
URL bearer secret protects this endpoint; it must never appear in access logs.
"""

import hashlib
import hmac
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.messaging import record_receipt, save_incoming
from app.persistence.models import Merchant, now
from app.persistence.session import get_db

router = APIRouter(prefix="/webhooks/360dialog", tags=["360dialog WhatsApp"])


@router.post("/{token}", include_in_schema=False)
async def incoming(token: str, request: Request, db: Annotated[Session, Depends(get_db)]):
    s = get_settings()
    if s.whatsapp_provider != "360dialog_sandbox":
        raise HTTPException(404, "Provider is disabled")
    if len(s.d360_webhook_secret) < 32 or not hmac.compare_digest(token, s.d360_webhook_secret):
        raise HTTPException(403, "Invalid webhook authentication")
    if not s.d360_api_key or not s.d360_sandbox_recipient:
        raise HTTPException(503, "Sandbox is not configured")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 1024 * 1024:
            raise HTTPException(413, "Payload too large")
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("entry"), list):
            raise TypeError()
        values = [
            change["value"]
            for entry in payload["entry"]
            for change in entry["changes"]
            if change.get("field") == "messages"
        ]
        events = [
            (kind, item)
            for value in values
            for kind in ("messages", "statuses")
            for item in value.get(kind, [])
        ]
        if len(events) > 50:
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(422, "Invalid webhook payload")
    merchant = db.scalar(select(Merchant).where(Merchant.id == s.whatsapp_merchant_id).with_for_update())
    if not merchant:
        raise HTTPException(503, "Store mapping is missing")
    for kind, item in events:
        try:
            if not isinstance(item, dict):
                raise TypeError()
            key = (
                ("from_user_id" if s.d360_recipient_type == "bsuid" else "from")
                if kind == "messages"
                else ("recipient_user_id" if s.d360_recipient_type == "bsuid" else "recipient_id")
            )
            recipient = item.get(key)
            if not isinstance(recipient, str) or not hmac.compare_digest(recipient, s.d360_sandbox_recipient):
                raise HTTPException(403, "Unexpected Sandbox tester")
            pid = item["id"]
            if not isinstance(pid, str) or not 1 <= len(pid) <= 200:
                raise ValueError()
            if kind == "statuses":
                status = item["status"]
                if status not in {"sent", "delivered", "read", "failed"}:
                    continue
                record_receipt(
                    db,
                    merchant_id=merchant.id,
                    provider="360dialog_sandbox",
                    provider_id=pid,
                    recipient=recipient,
                    status=status,
                )
                continue
            received_at = datetime.fromtimestamp(int(item["timestamp"]), UTC)
            if received_at > now() + timedelta(minutes=5):
                raise ValueError()
            phone = None
            if s.d360_recipient_type == "phone":
                if not re.fullmatch(r"[1-9]\d{7,14}", recipient):
                    raise ValueError()
                phone = "+" + recipient
            message_type = item.get("type")
            body = item.get("text", {}).get("body") if message_type == "text" else None
            if message_type == "text" and (not isinstance(body, str) or not 1 <= len(body) <= 4000):
                raise ValueError()
            mid = "d360:" + hashlib.sha256(f"{merchant.id}:{pid}".encode()).hexdigest()
            save_incoming(
                db,
                merchant_id=merchant.id,
                provider="360dialog_sandbox",
                recipient=recipient,
                phone=phone,
                provider_id=pid,
                message_id=mid,
                body=body or "Unsupported WhatsApp attachment",
                received_at=received_at,
                unsupported_type=None if message_type == "text" else str(message_type)[:30],
            )
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError, OSError):
            raise HTTPException(422, "Invalid message event")
    db.commit()
    return {"received": True}
