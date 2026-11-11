from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from app.db.models import AuditLog, Conversation, Job, Message, Policy


def utc(value: datetime):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def record(row):
    result = {}
    for attr in inspect(row).mapper.column_attrs:
        value = getattr(row, attr.key)
        result[attr.key] = utc(value).isoformat() if isinstance(value, datetime) else value
    return result


def scoped(db: Session, model, entity_id: str, merchant_id: str, lock=False):
    stmt = select(model).where(model.id == entity_id, model.merchant_id == merchant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = db.scalar(stmt)
    if row is None:
        raise HTTPException(404, "Record not found")
    return row


def policy(db: Session, merchant_id: str):
    row = db.scalar(
        select(Policy)
        .where(Policy.merchant_id == merchant_id, Policy.published.is_(True))
        .order_by(Policy.version.desc())
        .limit(1)
    )
    if row is None:
        raise HTTPException(409, "Publish a store policy first")
    return row


def audit(db: Session, merchant_id: str, actor: str, action: str, entity_id: str, **detail):
    db.add(AuditLog(merchant_id=merchant_id, actor=actor, action=action, entity_id=entity_id, detail=detail))


def reply(db: Session, conv: Conversation, body: str, role="assistant", message_id=None):
    values = {"id": message_id} if message_id else {}
    msg = Message(
        **values,
        conversation_id=conv.id,
        role=role,
        body=body,
        status="demo_delivered" if conv.channel == "demo" else "queued",
    )
    db.add(msg)
    db.flush()
    if conv.channel == "whatsapp":
        db.add(Job(id=f"send:{msg.id}", kind="send_message", payload={"message_id": msg.id}))
    return msg
