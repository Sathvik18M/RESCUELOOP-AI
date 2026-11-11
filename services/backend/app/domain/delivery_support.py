"""Delivery facts and disputes are separate; unavailable evidence stays unavailable."""

from sqlalchemy import select

from app.domain.cases import support_case, transition
from app.domain.common import audit
from app.domain.store_tools import lookup_shipment
from app.persistence.models import Case


def handle(db, conv, proposal, order, message_id):
    text = proposal["request_text"]
    disputed = proposal["intent"] == "delivery_dispute"
    reference = order.id if order else proposal.get("order_id")
    existing = list(
        db.scalars(
            select(Case)
            .where(
                Case.conversation_id == conv.id,
                Case.order_id == (order.id if order else None),
                Case.kind.in_(["delivery_dispute", "tracking_mismatch", "missing_package"]),
                Case.primary_status != "resolved",
            )
            .order_by(Case.updated_at.desc())
            .with_for_update()
        )
    )
    case = (
        existing[0]
        if existing
        else support_case(
            db, conv, "delivery_dispute" if disputed else "tracking", text, order.id if order else None
        )
    )
    if disputed and case.kind != "delivery_dispute":
        audit(
            db,
            conv.merchant_id,
            "resolution",
            "case.reclassified",
            case.id,
            previous_kind=case.kind,
            kind="delivery_dispute",
            input_message_id=message_id,
        )
        case.kind = "delivery_dispute"
    facts = lookup_shipment(db, conv, reference, case.id, message_id) if reference else None
    details = {
        **case.details,
        "source_message_ids": list(dict.fromkeys([*case.details.get("source_message_ids", []), message_id])),
    }
    if proposal.get("issue_code"):
        details["issue_code"] = proposal["issue_code"]
    if disputed:
        claims = list(details.get("customer_claims", []))
        if not any(c["text"] == text for c in claims):
            claims.append({"text": text, "message_id": message_id})
        details["customer_claims"] = claims
        details["customer_claim"] = "\n".join(c["text"] for c in claims)
        details["customer_claim_source_message_id"] = message_id
    if not facts:
        details["missing_details"] = [] if reference else ["your order reference"]
        details["suggested_action"] = "Verify the customer's order ownership."
        case.details = details
        transition(
            db,
            case,
            "flagged" if reference else "ongoing",
            "pending_verification" if reference else "needs_customer_details",
            "Order ownership needs verification." if reference else "",
        )
        return (
            "The store must verify ownership before sharing shipment information."
            if reference
            else "Please share your order reference so I can check the shipment."
        ), case
    details.update(
        verified_store_facts=facts, conflicting_evidence=facts["conflicting_evidence"], missing_details=[]
    )
    needs_review = disputed or case.kind == "delivery_dispute" or bool(facts["conflicting_evidence"])
    answer = f"The store record for {order.id} says {facts['delivery_status'].upper()}."
    if needs_review:
        case.kind = "delivery_dispute"
        details["suggested_action"] = (
            "Ask the courier for proof of delivery and the delivery location; reconcile shipment history with the customer's claim before resolving."
        )
        reason = "Customer disputes delivery or requests delivery evidence."
        if facts["conflicting_evidence"]:
            reason += " " + " ".join(facts["conflicting_evidence"])
        if not facts["proof_of_delivery"]:
            reason += " Proof of delivery is not available in the connected store records."
        transition(db, case, "flagged", "pending_verification", reason)
        answer += " That status alone does not verify that you received the package."
        answer += (
            f" The recorded delivery location is {facts['delivery_location']}."
            if facts["delivery_location"]
            else " No delivery location is available in the connected records."
        )
        answer += (
            " Recorded delivery evidence is available for the seller to verify."
            if facts["proof_of_delivery"]
            else " No proof of delivery is available; the store team needs to obtain it from the courier."
        )
        if facts["conflicting_evidence"]:
            answer += " The saved status sources conflict and need seller verification."
        answer += f" Case #{case.id[:6].upper()} is PENDING_VERIFICATION."
        audit(
            db,
            conv.merchant_id,
            "resolution",
            "case.escalated",
            case.id,
            input_message_id=message_id,
            reason=reason,
        )
    else:
        transition(db, case, "ongoing", "status_checked")
        answer += " This is the saved status, not independent proof of receipt."
    if not facts["history_available"]:
        answer += " The store has no shipment event history available."
    if "date" in text.casefold() or "when" in text.casefold():
        answer += " A verified expected delivery date is not available."
    case.details = details
    case.checks = [
        {"label": "Order ownership verified", "passed": True},
        {"label": "Shipment event history available", "passed": facts["history_available"]},
        {"label": "Status sources agree", "passed": not facts["conflicting_evidence"]},
        {"label": "Proof of delivery available", "passed": bool(facts["proof_of_delivery"])},
    ]
    audit(
        db,
        conv.merchant_id,
        "resolution",
        "case.delivery_checked",
        case.id,
        input_message_id=message_id,
        details=details,
        stage=case.status,
    )
    return answer, case
