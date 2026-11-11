"""Collect and validate customization before creating a commerce request."""

import re

from fastapi import HTTPException
from sqlalchemy import select

from app.domain.cases import support_case, transition
from app.domain.commerce import configure_request, confirmation_text, eligible
from app.domain.common import audit, policy
from app.persistence.models import Case, Product


def handle(db, conv, proposal, order, message_id):
    text = proposal["request_text"]
    cases = list(
        db.scalars(
            select(Case)
            .where(
                Case.conversation_id == conv.id,
                Case.order_id == (order.id if order else None),
                Case.kind.in_(["customization", "customization_inquiry"]),
                Case.primary_status != "resolved",
            )
            .order_by(Case.updated_at.desc())
            .with_for_update()
        )
    )
    case = (
        cases[0]
        if cases
        else support_case(db, conv, "customization_inquiry", text, order.id if order else None)
    )
    details = dict(case.details)
    details["issue_code"] = "29"
    if case.status == "needs_details":
        details["customer_clarification"] = text
    engraving = proposal.get("engraving")
    if engraving and (
        engraving == "Requested engraving" or re.match(r"(?:my|your|the) name\b", engraving, re.IGNORECASE)
    ):
        engraving = None
    if engraving and (len(engraving) > 40 or engraving.casefold() not in text.casefold()):
        engraving = None
    if engraving:
        details["engraving"] = engraving
        details["engraving_source_message_id"] = message_id
    if proposal.get("gift_wrap"):
        details["gift_wrap"] = True
    if (
        "the exact engraving text" in details.get("missing_details", [])
        and not engraving
        and not re.search(r"custom|engrave|wrap|\?", text, re.IGNORECASE)
        and 0 < len(text.strip()) <= 40
    ):
        details["engraving"] = text.strip().strip('"')
        details["engraving_source_message_id"] = message_id
    details["engraving_requested"] = bool(
        details.get("engraving_requested")
        or re.search(r"engrav", text, re.IGNORECASE)
        or details.get("engraving")
    )
    details["customer_claim"] = text
    details["source_message_ids"] = list(dict.fromkeys([*details.get("source_message_ids", []), message_id]))
    missing = []
    errors = []
    product = db.get(Product, order.product_id) if order else None
    current = None
    if not order:
        missing.append("your order reference")
    else:
        try:
            current = policy(db, conv.merchant_id)
            eligible(order, "customization", current.rules)
        except HTTPException as exc:
            errors.append(str(exc.detail))
        if details.get("engraving_requested") and not product.options.get("engraving"):
            errors.append("Engraving is not listed as an available option for this product.")
        if details.get("gift_wrap") and "gift_wrap_paise" not in product.options:
            errors.append("Gift wrapping is not listed as an available option for this product.")
        details["verified_store_facts"] = {
            "order_id": order.id,
            "order_status": order.status,
            "product_name": product.name,
            "product_options": product.options,
            "policy_version": current.version if current else None,
        }
    if details.get("engraving_requested") and not details.get("engraving"):
        missing.append("the exact engraving text")
    if not details.get("engraving_requested") and not details.get("gift_wrap"):
        missing.append("the customization you want, such as engraving or gift wrapping")
    details.update(
        missing_details=missing,
        suggested_action=(
            "Explain the failed prerequisites and discuss eligible alternatives; do not modify the order."
            if errors
            else "Collect only the missing customization requirements."
            if missing
            else "Review the customization terms before requesting customer confirmation."
        ),
    )
    case.details = details
    audit(
        db,
        conv.merchant_id,
        "shopping",
        "tool.customization_prerequisites_checked",
        case.id,
        input_message_id=message_id,
        passed=not errors and not missing,
        errors=errors,
        missing_fields=missing,
        verified_facts=details.get("verified_store_facts"),
    )
    if errors:
        # Keep historical requests and audits; record the blocked intake accurately.
        if case.kind == "customization" and not case.proposal_ref and not case.seller_approved:
            audit(db, conv.merchant_id, "shopping", "case.reclassified", case.id,
                input_message_id=message_id, previous_kind=case.kind, kind="customization_inquiry")
            case.kind = "customization_inquiry"
        transition(db, case, "flagged", "pending_verification", " ".join(errors))
        audit(
            db,
            conv.merchant_id,
            "shopping",
            "case.escalated",
            case.id,
            input_message_id=message_id,
            reason="customization_prerequisites",
            errors=errors,
        )
        return (
            f"I can't submit a customization for {order.id} as requested. "
            + " ".join(errors)
            + f" Case #{case.id[:6].upper()} is PENDING_VERIFICATION for the store to explain alternatives. No customization has been applied."
        ), case
    if missing:
        transition(db, case, "ongoing", "needs_customer_details")
        return "Before submitting a customization, please provide only: " + "; ".join(missing) + ".", case
    if case.kind != "customization":
        audit(
            db,
            conv.merchant_id,
            "shopping",
            "customization.request_created",
            case.id,
            input_message_id=message_id,
            previous_kind=case.kind,
            order_id=order.id,
        )
        case.kind = "customization"
    if case.status not in {"pending_customer", "executing"}:
        configure_request(db, case, conv, details)
    if case.status == "pending_customer":
        return confirmation_text(db, case), case
    return (
        f"Customization case #{case.id[:6].upper()} is {case.status.upper()} for seller review. No order modification has been applied.",
        case,
    )
