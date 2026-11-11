"""Wrong-item resolution workflow: evidence first, truthful state, no repeated intake."""

import hashlib
import re
from datetime import datetime, timedelta

from sqlalchemy import select

from app.agents.workflows.wrong_item import extract_facts, is_wrong_item
from app.core.config import get_settings
from app.domain.cases import support_case, transition
from app.domain.common import audit, reply, utc
from app.domain.store_tools import lookup_owned_order, lookup_replacement_policy, lookup_shipment
from app.persistence.models import Case, Evidence, Message, now


def should_handle(db, conv, text):
    if len(set(re.findall(r"\bORD\d+\b", text, re.IGNORECASE))) > 1:
        return False  # Keep distinct-order routing in the coordinator.
    if is_wrong_item(text):
        return True
    active = list(
        db.scalars(
            select(Case).where(
                Case.conversation_id == conv.id,
                Case.kind == "wrong_product",
                Case.primary_status != "resolved",
            )
        )
    )
    return bool(
        active
        and (
            re.fullmatch(r"\s*ORD\d+[.!]?\s*", text, re.IGNORECASE)
            or re.search(r"\bi (?:received|ordered|got)\b", text, re.IGNORECASE)
            or re.fullmatch(r"\s*(?:i want |please )?(?:a )?replacement[.!]?\s*", text, re.IGNORECASE)
        )
    )


def _case_for(db, conv, reference):
    rows = list(
        db.scalars(
            select(Case)
            .where(
                Case.conversation_id == conv.id,
                Case.kind == "wrong_product",
            )
            .order_by(Case.updated_at.desc())
            .with_for_update()
        )
    )
    exact = [
        c
        for c in rows
        if reference and (c.order_id == reference or c.details.get("reported_order_id") == reference)
    ]
    unbound = [
        c
        for c in rows
        if not c.order_id and not c.details.get("reported_order_id") and c.primary_status != "resolved"
    ]
    if exact:
        return exact[0]
    if len(unbound) == 1:
        return unbound[0]
    if not reference and len([c for c in rows if c.primary_status != "resolved"]) == 1:
        return next(c for c in rows if c.primary_status != "resolved")
    return support_case(db, conv, "wrong_product", "Wrong-item complaint", order_id=None, reuse=False)


def _comparison(reported, stored):
    if not reported:
        return "not_supplied"
    words = lambda value: set(re.findall(r"[a-z0-9]+", value.casefold())) - {"a", "an", "the"}
    a, b = words(reported), words(stored)
    return "consistent" if a and (a <= b or b <= a) else "needs_seller_verification"


def handle(db, conv, text, message_id):
    msg = db.get(Message, message_id)
    refs = re.findall(r"\bORD\d+\b", text, re.IGNORECASE)
    reference = refs[0].upper() if refs else (conv.context or {}).get("active_order_id")
    case = _case_for(db, conv, reference)
    old = dict(case.details)
    reference = reference or old.get("reported_order_id") or case.order_id
    history = list(
        db.scalars(
            select(Message)
            .where(
                Message.conversation_id == conv.id,
                Message.role == "customer",
                Message.created_at <= msg.created_at,
            )
            .order_by(Message.created_at.desc())
            .limit(40)
        )
    )
    sources = []
    for prior in reversed(history):
        if prior.id == message_id:
            sources.append({"id": prior.id, "text": text})
            continue
        other_refs = set(re.findall(r"\bORD\d+\b", prior.body.upper()))
        if reference and other_refs and other_refs != {reference}:
            continue
        if case.id in prior.case_ids or is_wrong_item(prior.body):
            sources.append({"id": prior.id, "text": prior.body})
    sources = sources[-12:]
    audit(
        db,
        conv.merchant_id,
        "resolution",
        "tool.resolution_extract_requested",
        case.id,
        input_message_id=message_id,
        source_message_ids=[m["id"] for m in sources],
    )
    facts = extract_facts(sources)
    audit(
        db,
        conv.merchant_id,
        "resolution",
        "tool.resolution_extract_completed",
        case.id,
        input_message_id=message_id,
        ai_provider=get_settings().ai_mode,
        model=get_settings().groq_model if get_settings().ai_mode == "groq" else "demo",
        extracted=facts.model_dump(),
    )
    details = {
        **old,
        "issue_code": "15",
        "customer_issue": "Wrong product received",
        "complaint_type": "wrong_item",
        "source_message_ids": list(
            dict.fromkeys([*old.get("source_message_ids", []), *[m["id"] for m in sources]])
        ),
    }
    for field in ("ordered_product", "received_product"):
        value = getattr(facts, field)
        if value:
            details[field] = value.value
            details[field + "_source_message_id"] = value.message_id
    if facts.order_id:
        reference = facts.order_id.value.upper()
        details["order_id_source_message_id"] = facts.order_id.message_id
    if reference:
        details["reported_order_id"] = reference
    if facts.requested_resolution:
        details["requested_resolution"] = facts.requested_resolution
        details["resolution_source_message_id"] = facts.resolution_message_id
    case.details = details
    msg.case_ids = list(dict.fromkeys([*msg.case_ids, case.id]))
    order, record = (
        lookup_owned_order(db, conv, reference, case.id, message_id) if reference else (None, None)
    )
    current, replacement_policy = lookup_replacement_policy(db, conv, case.id, message_id)
    reasons = []
    checks = []
    missing = []
    if not reference:
        missing.append("your order reference")
    elif not order:
        reasons.append("Order ownership must be verified by the store.")
    if order:
        case.order_id = order.id
        conv.order_id = order.id
        details["verified_order"] = record
        shipment = lookup_shipment(db, conv, order.id, case.id, message_id)
        details["verified_store_facts"] = shipment
        details["conflicting_evidence"] = shipment["conflicting_evidence"]
        details["suggested_action"] = "Verify the received product, reconcile delivery evidence and review replacement eligibility before offering terms."
        reasons.extend(shipment["conflicting_evidence"])
        comparison = _comparison(details.get("ordered_product"), record["product_name"])
        details["ordered_product_comparison"] = comparison
        details["received_product_comparison"] = _comparison(
            details.get("received_product"), record["product_name"]
        )
        checks.append({"label": "Customer owns this order", "passed": True})
        checks.append(
            {
                "label": "Reported ordered product matches store record",
                "passed": comparison != "needs_seller_verification",
            }
        )
        if comparison == "needs_seller_verification":
            reasons.append(
                "The reported ordered product differs from the store order and requires verification."
            )
        received_claim = bool(
            details.get("received_product")
            or any(re.search(r"\b(?:received|got|arrived)\b", m["text"], re.IGNORECASE) for m in sources)
        )
        discrepancy = received_claim and record["delivery_status"].casefold() != "delivered"
        details["delivery_discrepancy"] = discrepancy
        checks.append(
            {"label": "Delivery status agrees with customer's receipt report", "passed": not discrepancy}
        )
        if discrepancy:
            reasons.append(
                f"Store delivery status is {record['delivery_status'].upper()}, but the customer reports receiving a product."
            )
    if not details.get("ordered_product") and not record:
        missing.append("the product you ordered")
    if not details.get("received_product"):
        missing.append("the product you received")
    if not details.get("requested_resolution"):
        missing.append("whether you want a replacement, return or refund")
    details["replacement_policy_check"] = replacement_policy
    if not replacement_policy:
        reasons.append("A published replacement policy is unavailable; seller clarification is required.")
    else:
        case.policy_version = current.version
        checks.append({"label": f"Published policy v{current.version} checked", "passed": True})
        if replacement_policy["replacement_permission"] == "unavailable":
            reasons.append(
                "Replacement is unavailable under the published policy; the seller must explain alternatives."
            )
        if "incorrect_item" not in replacement_policy["eligible_reasons"]:
            reasons.append("Wrong-item eligibility needs seller review under the published policy.")
        if record and record["delivered_at"] and replacement_policy["window_days"] is not None:
            within = now() - utc(datetime.fromisoformat(record["delivered_at"])) <= timedelta(
                days=replacement_policy["window_days"]
            )
            checks.append({"label": "Within the published replacement eligibility window", "passed": within})
            if not within:
                reasons.append("The published eligibility window has ended; seller review is required.")
        evidence = list(db.scalars(select(Evidence).where(Evidence.case_id == case.id)))
        if replacement_policy["require_photo"] and not any(
            e.verified or e.quality == "clear" for e in evidence
        ):
            reasons.append(
                "Product evidence requires seller verification before a replacement can be offered."
            )
    case.details = {**details, "verification_reasons": reasons, "missing_details": missing}
    case.checks = checks
    case.summary = f"Wrong item: {details.get('ordered_product', 'ordered product not yet identified')} → {details.get('received_product', 'received product not yet identified')}; requested {details.get('requested_resolution', 'resolution not yet specified')}"
    if reasons:
        transition(db, case, "flagged", "pending_verification", " ".join(reasons))
        audit(
            db,
            conv.merchant_id,
            "resolution",
            "case.escalated",
            case.id,
            input_message_id=message_id,
            reason="verification_required",
            verification_reasons=reasons,
        )
    elif missing:
        transition(db, case, "ongoing", "needs_customer_details")
    else:
        transition(
            db,
            case,
            "flagged",
            "pending_seller",
            "Seller review is required before replacement terms can be offered.",
        )
        audit(
            db,
            conv.merchant_id,
            "resolution",
            "case.escalated",
            case.id,
            input_message_id=message_id,
            reason="replacement_seller_review",
        )
    audit(
        db,
        conv.merchant_id,
        "resolution",
        "case.complaint_updated",
        case.id,
        input_message_id=message_id,
        previous_details=old,
        details=case.details,
        stage=case.status,
        resolution_attempts=case.resolution_attempts,
    )
    collected = []
    if reference:
        collected.append(f"order {reference}")
    if details.get("ordered_product"):
        collected.append(f"ordered {details['ordered_product']}")
    if details.get("received_product"):
        collected.append(f"received {details['received_product']}")
    if details.get("requested_resolution"):
        collected.append(f"requested {details['requested_resolution']}")
    response = (
        "I've recorded " + "; ".join(collected) + "."
        if collected
        else "I've saved your wrong-item complaint."
    )
    if record:
        response += f" The store order lists {record['product_name']} and delivery status {record['delivery_status'].upper()}."
    if details.get("delivery_discrepancy"):
        response += " That conflicts with your report of receiving an item."
    elif details.get("conflicting_evidence"):
        response += " The saved status sources conflict and require seller verification."
    response += f" Case #{case.id[:6].upper()} is {case.status.upper()}."
    if case.primary_status == "flagged":
        response += " The store team will verify the order, delivery and evidence before deciding the next step. No replacement has been authorized."
    if missing:
        response += " Please provide only: " + "; ".join(missing) + "."
    if (
        conv.messaging_provider == "360dialog_sandbox"
        and replacement_policy
        and replacement_policy["require_photo"]
    ):
        response += " This Sandbox cannot retrieve photos for AI review; the seller must arrange evidence verification."
    outgoing = reply(db, conv, response, cases=[case])
    audit(
        db,
        conv.merchant_id,
        "resolution",
        "resolution.reply_composed",
        case.id,
        input_message_id=message_id,
        output_message_id=outgoing.id,
        response_mode="verified_workflow_template",
        response_sha256=hashlib.sha256(response.encode()).hexdigest(),
        requested_missing_fields=missing,
    )
    msg.processed = True
    db.flush()
    return {"duplicate": False, "reply": response, "case_ids": [case.id]}
