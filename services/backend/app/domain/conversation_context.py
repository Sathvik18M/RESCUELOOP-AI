"""Durable, case-scoped facts. A model's inference is never a completed action."""

import re

from sqlalchemy import select

from app.domain.common import audit
from app.persistence.models import Case, Message, Operation


def hydrate(db, conv):
    context = dict(conv.context or {})
    if not context.get("active_order_id"):
        context["active_order_id"] = conv.order_id
    if not context.get("active_case_id"):
        prior = db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id, Message.processed.is_(True))
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(30)
        )
        for message in prior:
            if message.case_ids:
                candidate = db.get(Case, message.case_ids[-1])
                if candidate and candidate.conversation_id == conv.id:
                    context["active_case_id"] = candidate.id
                    break
    conv.context = context
    return context


def relevant_history(db, conv, limit=24):
    # Keep recent exchanges plus the active case's durable source messages.
    recent = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
    )
    active = (
        db.get(Case, (conv.context or {}).get("active_case_id"))
        if (conv.context or {}).get("active_case_id")
        else None
    )
    ids = (
        active.details.get("source_message_ids", [])[-12:]
        if active and active.conversation_id == conv.id
        else []
    )
    older = (
        list(db.scalars(select(Message).where(Message.conversation_id == conv.id, Message.id.in_(ids))))
        if ids
        else []
    )
    return sorted({m.id: m for m in [*recent, *older]}.values(), key=lambda m: (m.created_at, m.id))


def select_continuation(db, conv, candidates, text):
    # An explicit case/order reference outranks the active case. Unrelated open
    # cases never make a clear follow-up ambiguous.
    explicit = [
        c
        for c in candidates
        if c.id[:6].upper() in text.upper() or (c.proposal_ref and c.proposal_ref in text.upper())
    ]
    if len(explicit) == 1:
        return explicit[0]
    refs = set(re.findall(r"\bORD\d+\b", text.upper()))
    if refs:
        candidates = [c for c in candidates if c.order_id in refs]
    active = next((c for c in candidates if c.id == (conv.context or {}).get("active_case_id")), None)
    return active or (candidates[0] if len(candidates) == 1 else None)


def remember_turn(db, conv, message_id):
    message = db.get(Message, message_id)
    context = dict(conv.context or {})
    cases = list(db.scalars(select(Case).where(Case.conversation_id == conv.id)))
    linked = [c for cid in message.case_ids for c in cases if c.id == cid]
    if linked:
        context["active_case_id"] = linked[-1].id
        if linked[-1].order_id:
            context["active_order_id"] = linked[-1].order_id
    facts = dict(context.get("known_customer_facts", {}))
    pending = []
    for case in cases:
        facts[case.id] = {
            k: v
            for k, v in case.details.items()
            if k
            in {
                "ordered_product",
                "received_product",
                "requested_resolution",
                "reported_order_id",
                "complaint_type",
                "customer_claim",
                "engraving",
                "gift_wrap",
                "special_request",
                "reason",
                "address",
            }
            or k.endswith("_source_message_id")
        }
        if case.primary_status != "resolved":
            for field in case.details.get("missing_details", []):
                pending.append({"case_id": case.id, "field": field})
            if case.status == "needs_details" and case.details.get("seller_question"):
                pending.append({"case_id": case.id, "question": case.details["seller_question"]})
    # Only confirmed backend operations qualify, never proposed/requested actions.
    operations = list(
        db.scalars(
            select(Operation)
            .where(Operation.case_id.in_([c.id for c in cases]), Operation.status == "succeeded")
            .order_by(Operation.created_at.desc())
            .limit(10)
        )
    )
    context.update(
        known_customer_facts=facts,
        pending_questions=pending,
        last_completed_actions=[
            {"operation_id": o.id, "case_id": o.case_id, "kind": o.kind, "status": o.status}
            for o in operations
        ],
        last_message_id=message_id,
    )
    conv.context = context
    audit(
        db,
        conv.merchant_id,
        "coordinator",
        "conversation.context_updated",
        conv.id,
        input_message_id=message_id,
        active_order_id=context.get("active_order_id"),
        active_case_id=context.get("active_case_id"),
        pending_questions=pending,
    )
