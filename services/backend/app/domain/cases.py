"""Case lifecycle is independent of approval, execution and delivery states."""

import hashlib
import json
import secrets
from datetime import timedelta
from sqlalchemy import select
from app.persistence.models import Case, Job, Message, now
from app.domain.common import audit, utc


def transition(db, case, primary, stage, reason=""):
    previous = case.primary_status
    case.primary_status, case.status, case.flag_reason = primary, stage, reason
    case.updated_at = now()
    case.resolved_at = now() if primary == "resolved" else None
    audit(
        db,
        case.merchant_id,
        "system",
        "case.transition",
        case.id,
        previous=previous,
        primary=primary,
        stage=stage,
        reason=reason,
    )


def flag(db, case, reason):
    transition(db, case, "flagged", "pending_seller", reason)


DEFAULT_ORDER = object()


def support_case(db, conv, kind, summary, order_id=DEFAULT_ORDER, reuse=True):
    if order_id is DEFAULT_ORDER:
        order_id = conv.order_id
    case = (
        db.scalar(
            select(Case)
            .where(Case.conversation_id == conv.id, Case.order_id == order_id, Case.kind == kind)
            .order_by(Case.updated_at.desc())
            .limit(1)
        )
        if reuse
        else None
    )
    if case and case.primary_status != "resolved":
        return case
    case = Case(
        merchant_id=conv.merchant_id,
        conversation_id=conv.id,
        order_id=order_id,
        kind=kind,
        summary=summary[:2000],
        policy_version=0,
        primary_status="ongoing",
        status="investigating",
        expires_at=now() + timedelta(hours=24),
    )
    db.add(case)
    db.flush()
    audit(db, conv.merchant_id, "coordinator", "case.opened", case.id, kind=kind)
    return case


def terms_fingerprint(case, order):
    data = {
        "order": order.id,
        "total": order.total_paise,
        "status": order.status,
        "kind": case.kind,
        "policy": case.policy_version,
        "quote": case.quote_paise,
        "details": {
            k: v
            for k, v in case.details.items()
            if k not in {"last_solution", "failed_solution", "customer_clarification"}
        },
        "revision": case.proposal_revision,
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def issue_proposal(db, case, order):
    case.proposal_revision += 1
    case.proposal_ref = "R" + secrets.token_hex(3).upper()
    case.consented_at = None
    case.expires_at = now() + timedelta(hours=24)
    case.terms_hash = terms_fingerprint(case, order)
    transition(db, case, "ongoing", "pending_customer")
    db.add(
        Job(
            id=f"expire:{case.id}:{case.proposal_revision}",
            kind="case_expire",
            payload={"case_id": case.id, "revision": case.proposal_revision},
            available_at=case.expires_at,
        )
    )
    audit(
        db,
        case.merchant_id,
        "system",
        "proposal.issued",
        case.id,
        reference=case.proposal_ref,
        revision=case.proposal_revision,
    )


def delivered_completion(db, msg):
    if not msg.completes_case or msg.status not in {"delivered", "read", "demo_delivered"}:
        return
    for cid in msg.case_ids:
        case = db.get(Case, cid)
        # A late provider receipt can finish the exact outcome that failed delivery,
        # but must never close a subsequently reopened issue or a seller handoff.
        if case and (
            case.status == "awaiting_notification"
            or (
                case.details.get("notification_failure") == msg.id
                and case.details.get("last_solution") == msg.id
                and case.flag_reason
                == "Customer notification failed. Verify delivery before closing the case."
            )
        ):
            case.details = {k: v for k, v in case.details.items() if k != "notification_failure"}
            transition(db, case, "resolved", "completed")


def remember(db, case):
    history = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == case.conversation_id)
            .order_by(Message.created_at, Message.id)
        )
    )
    relevant = [m for m in history if case.id in (m.case_ids or [])]
    older = relevant[:-12]
    case.memory = {
        **case.memory,
        "source_message_ids": [m.id for m in older],
        "observations": [{"message_id": m.id, "role": m.role, "excerpt": m.body[:240]} for m in older[-12:]],
        "generated_at": now().isoformat(),
        "untrusted_summary": True,
    }
    return relevant[-12:]


def context_for(db, case, order, current_policy, evidence):
    recent = remember(db, case)
    return json.dumps(
        {
            "case_id": case.id,
            "request": case.summary,
            "order": {
                "id": order.id,
                "status": order.status,
                "delivery": order.delivery_status,
                "total_paise": order.total_paise,
                "paid_paise": order.paid_paise,
            }
            if order
            else None,
            "published_policy": current_policy.rules if current_policy else None,
            "primary_status": case.primary_status,
            "stage": case.status,
            "resolution_attempts": case.resolution_attempts,
            "pending_proposal": case.proposal_ref,
            "consented_at": str(case.consented_at),
            "history_summary": case.memory,
            "messages": [{"id": m.id, "role": m.role, "text": m.body} for m in recent],
            "evidence": [
                {"id": e.id, "observation": e.assessment, "seller_verified": e.verified} for e in evidence
            ],
        },
        default=str,
    )
