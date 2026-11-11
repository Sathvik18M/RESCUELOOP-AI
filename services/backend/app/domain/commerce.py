"""Policy-controlled business operations. All amounts are integer paise."""

import hashlib
import secrets
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select, func
from app.persistence.models import (
    Case,
    Conversation,
    Order,
    Product,
    PickupSlot,
    Reservation,
    Refund,
    Job,
    Operation,
    ReturnRecord,
    Evidence,
    now,
)
from app.domain.common import audit, policy, reply, scoped, utc
from app.domain.cases import flag, transition, support_case, issue_proposal, terms_fingerprint

KINDS = {
    "customization",
    "pickup",
    "redelivery",
    "refund",
    "return",
    "replacement",
    "cancellation",
    "warranty",
    "checkout",
}


def amount(value):
    return f"₹{value / 100:,.2f}"


def final_total(order, rules, pickup=False):
    return order.total_paise


def pending_refunds(db, order):
    return (
        db.scalar(
            select(func.coalesce(func.sum(Refund.amount_paise), 0)).where(
                Refund.order_id == order.id, Refund.status.in_(["pending", "uncertain"])
            )
        )
        or 0
    )


def eligible(order, kind, rules):
    if kind in {"return", "replacement", "refund", "warranty"}:
        if kind == "refund" and order.status == "cancelled":
            return
        if not order.delivered_at or order.delivery_status != "delivered":
            raise HTTPException(409, "Delivery must be verified before this action.")
        days = rules["warranty_days"] if kind == "warranty" else rules["return_window_days"]
        if now() - utc(order.delivered_at) > timedelta(days=days):
            raise HTTPException(409, "The published eligibility window has ended.")
    if kind == "cancellation" and (
        not rules["cancellation_before_shipping"] or order.status not in {"draft", "confirmed"}
    ):
        raise HTTPException(409, "Cancellation is only available before shipping.")
    if kind == "redelivery" and order.delivery_status != "failed_attempt":
        raise HTTPException(409, "A verified failed delivery is required.")
    if kind in {"customization", "checkout"} and order.status != "draft":
        raise HTTPException(409, "This action requires an unfulfilled draft order.")
    if kind == "pickup" and (rules["pickup"] == "prohibited" or order.status not in {"draft", "confirmed"}):
        raise HTTPException(409, "Pickup is unavailable for this order.")
    permission = rules.get(f"{kind}_permission", "automatic")
    if permission == "unavailable":
        raise HTTPException(409, "The published policy makes this action unavailable.")


def verified_evidence(db, case):
    items = list(db.scalars(select(Evidence).where(Evidence.case_id == case.id)))
    return any(e.verified or e.quality == "clear" for e in items)


def configure_request(db, case, conv, details):
    order = scoped(db, Order, case.order_id, conv.merchant_id, lock=True)
    if order.customer_id != conv.customer_id:
        raise HTTPException(403, "Order ownership not verified")
    case.details = {**case.details, **{k: v for k, v in details.items() if v is not None}}
    case.checks = [{"label": "Customer owns this order", "passed": True}]
    try:
        current = policy(db, conv.merchant_id)
        case.policy_version = current.version
        eligible(order, case.kind, current.rules)
    except HTTPException as exc:
        case.checks = [*case.checks, {"label": str(exc.detail), "passed": False}]
        flag(db, case, str(exc.detail))
        return case
    rules = current.rules
    case.checks = [*case.checks, {"label": f"Published policy v{current.version} checked", "passed": True}]
    needs_seller = rules.get(f"{case.kind}_permission") == "approval_required"
    reason = "Seller approval is required by the published policy."
    d = dict(case.details)
    if case.kind == "customization":
        d["gift_wrap_paise"] = rules["gift_wrap_paise"] if d.get("gift_wrap") else 0
        d["preparation_days"] = rules["preparation_days"]
        case.quote_paise = rules["engraving_paise"] if d.get("engraving") else 0
        needs_seller = needs_seller or bool(d.get("engraving") or d.get("special_request"))
        reason = "New engraving or customization requires a seller decision."
        if d.get("gift_wrap") and any(c.get("gift_wrap") for c in order.customizations):
            flag(db, case, "Gift wrapping is already present on this order.")
            return case
    if case.kind == "pickup":
        slot_id = d.get("slot_id") or "SLOT-PM"
        slot = scoped(db, PickupSlot, slot_id, conv.merchant_id)
        if slot.reserved >= slot.capacity or (slot.ends_at and utc(slot.ends_at) <= now()):
            flag(db, case, "The requested pickup window is full or has ended.")
            return case
        if db.scalar(
            select(Reservation).where(
                Reservation.order_id == order.id, Reservation.status.in_(["reserved", "ready"])
            )
        ):
            flag(db, case, "An active pickup already exists for this order.")
            return case
        product = db.get(Product, order.product_id)
        if product.stock - product.reserved_stock < 1 and not order.inventory_reserved:
            flag(db, case, "The product is unavailable for reservation.")
            return case
        needs_seller = rules["pickup"] == "approval_required"
        reason = "Pickup requires the seller to approve availability."
        d.update(slot_id=slot.id, slot_label=slot.label, confirmed_total_paise=order.total_paise)
    if case.kind in {"refund", "return", "replacement"}:
        if not d.get("reason"):
            case.details = d
            transition(db, case, "ongoing", "needs_customer_details")
            return case
        if d["reason"] not in rules["return_reasons"]:
            flag(db, case, "The request reason is outside the published return policy.")
            return case
        if rules.get("require_photo") and not verified_evidence(db, case):
            needs_seller = True
            reason = "Product evidence requires manual verification."
    if case.kind == "refund":
        remaining = order.paid_paise - order.refunded_paise - pending_refunds(db, order)
        requested = d.get("amount_paise") or remaining
        if type(requested) != int or requested <= 0 or requested > remaining:
            flag(db, case, "Refund exceeds the available paid balance.")
            return case
        d["amount_paise"] = requested
        if order.refunded_paise + pending_refunds(db, order) + requested > rules["auto_refund_limit_paise"]:
            needs_seller = True
            reason = "Refund exceeds the cumulative automatic limit."
        inspected = db.scalar(
            select(ReturnRecord).where(ReturnRecord.order_id == order.id, ReturnRecord.status == "accepted")
        )
        if rules["require_return_inspection"] and not inspected and order.status != "cancelled":
            needs_seller = True
            reason += " Return inspection or an explicit seller waiver is required."
        d["return_inspected"] = bool(inspected)
    if case.kind in {"replacement", "warranty"}:
        needs_seller = True
        reason = "Seller review is required for this resolution."
    if case.kind == "redelivery" and not d.get("address"):
        case.details = d
        transition(db, case, "ongoing", "needs_customer_details")
        return case
    case.details = d
    if needs_seller:
        flag(db, case, reason)
    else:
        issue_proposal(db, case, order)
    return case


def create_case(db, conv, kind, summary, details=None):
    if kind not in KINDS:
        raise HTTPException(422, "Unsupported action")
    case = support_case(db, conv, kind, summary)
    if case.status in {
        "pending_customer",
        "executing",
        "awaiting_return",
        "pickup_reserved",
        "pickup_ready",
        "awaiting_notification",
    }:
        return case
    return configure_request(db, case, conv, details or {})


def confirmation_text(db, case):
    order = db.get(Order, case.order_id)
    d = case.details
    action = d.get("action", case.kind)
    if action == "customization":
        text = f"Engraving text: {d.get('engraving') or 'none'}; fee: {amount(case.quote_paise)}. Gift wrap: {amount(d.get('gift_wrap_paise', 0))}. Updated order total: {amount(order.total_paise + case.quote_paise + d.get('gift_wrap_paise', 0))}. Preparation: {d.get('preparation_days', 1)} day(s)."
    elif action == "refund":
        text = f"Confirm a SIMULATED refund of {amount(d['amount_paise'])}. No real money will move."
    elif action == "pickup":
        text = f"Pickup: {d['slot_label']}. Total: {amount(order.total_paise)}. Any balance is due at collection; collection payment is simulated."
    elif action == "return":
        text = f"Return authorized for {order.id}. Collection is simulated. A refund requires receipt and seller inspection."
    else:
        text = f"Confirm {action.replace('_', ' ')} for {order.id}. Payment and courier operations are simulated."
    return f"{text} Reply CONFIRM {case.proposal_ref} to accept or DECLINE {case.proposal_ref}. This proposal expires in 24 hours."


def decision(db, case_id, merchant_id, actor, data):
    case = scoped(db, Case, case_id, merchant_id, lock=True)
    if case.status not in {"pending_seller", "pending_verification", "needs_details", "expired"}:
        raise HTTPException(409, "This case is not awaiting a seller decision.")
    conv = db.get(Conversation, case.conversation_id)
    case.seller_assisted = True
    if data.decision == "request_details":
        case.details = {**case.details, "seller_question": data.note}
        transition(db, case, "ongoing", "needs_details")
        text = f"Store team: {data.note}"
    elif data.decision == "reject":
        text = f"Store team: Your {case.kind} request was declined. {data.note}"
        reply(db, conv, text, role="system", cases=[case], completes=True)
        audit(db, merchant_id, actor, "case.rejected", case.id, note=data.note)
        return case
    else:
        if not case.order_id or case.kind not in KINDS:
            raise HTTPException(409, "Use the case resolution action after addressing this issue.")
        order = scoped(db, Order, case.order_id, merchant_id, lock=True)
        current = policy(db, merchant_id)
        eligible(order, case.details.get("action", case.kind), current.rules)
        case.policy_version = current.version
        case.seller_approved = True
        d = {**case.details, "seller_note": data.note, "preparation_days": data.preparation_days}
        if case.kind == "customization":
            if data.quote_paise is not None:
                case.quote_paise = data.quote_paise
            if data.engraving is not None:
                d["engraving"] = data.engraving.strip()
            if data.gift_wrap is not None:
                d["gift_wrap"] = data.gift_wrap
                d["gift_wrap_paise"] = current.rules["gift_wrap_paise"] if data.gift_wrap else 0
        if case.kind == "pickup":
            if data.slot_id:
                d["slot_id"] = data.slot_id
            slot = scoped(db, PickupSlot, d["slot_id"], merchant_id)
            if slot.ends_at and utc(slot.ends_at) <= now():
                raise HTTPException(409, "Choose a future pickup window.")
            if slot.reserved >= slot.capacity:
                raise HTTPException(409, "Choose a pickup window with available capacity.")
            d["slot_label"] = slot.label
            d["confirmed_total_paise"] = order.total_paise
        if (
            case.kind in {"return", "refund", "replacement"}
            and current.rules["require_photo"]
            and not verified_evidence(db, case)
        ):
            raise HTTPException(409, "Verify the product photo before approving this request.")
        if (
            case.kind == "refund"
            and not d.get("return_inspected")
            and current.rules["require_return_inspection"]
        ):
            if not data.waive_return:
                raise HTTPException(
                    409, "Record a return inspection or explicitly waive the return with a reason."
                )
            d["return_waiver"] = data.note
        case.details = d
        issue_proposal(db, case, order)
        text = confirmation_text(db, case)
    audit(
        db, merchant_id, actor, f"case.{data.decision}", case.id, quote_paise=case.quote_paise, note=data.note
    )
    reply(db, conv, text, role="system", cases=[case])
    return case


def reserve_inventory(db, order):
    if order.inventory_reserved:
        return
    product = scoped(db, Product, order.product_id, order.merchant_id, lock=True)
    if product.stock - product.reserved_stock < 1:
        raise HTTPException(409, "Stock is no longer available.")
    product.reserved_stock += 1
    order.inventory_reserved = True


def release_inventory(db, order, collected=False):
    if order.inventory_reserved:
        product = scoped(db, Product, order.product_id, order.merchant_id, lock=True)
        product.reserved_stock -= 1
        if collected:
            product.stock -= 1
        order.inventory_reserved = False


def confirm_case(db, reference, conv, accept=True):
    case = db.scalar(
        select(Case)
        .where(Case.proposal_ref == reference.upper(), Case.merchant_id == conv.merchant_id)
        .with_for_update()
    )
    if not case or case.conversation_id != conv.id:
        raise HTTPException(404, "This confirmation is unavailable for your conversation.")
    if case.consented_at:
        return "This proposal was already accepted. Its saved outcome is unchanged.", case, False
    if case.status != "pending_customer":
        raise HTTPException(409, "This proposal is not awaiting confirmation.")
    if not accept:
        transition(db, case, "ongoing", "awaiting_notification")
        return "You declined this proposal. No new business action was executed.", case, True
    if utc(case.expires_at) <= now():
        flag(db, case, "The proposal expired. A fresh proposal is required.")
        return "This proposal expired. The seller can prepare updated terms.", case, False
    order = scoped(db, Order, case.order_id, conv.merchant_id, lock=True)
    if order.customer_id != conv.customer_id:
        raise HTTPException(403, "Ownership not verified")
    current = policy(db, conv.merchant_id)
    rules = current.rules
    if current.version != case.policy_version or case.terms_hash != terms_fingerprint(case, order):
        flag(db, case, "Policy or order terms changed; fresh approval and consent are required.")
        return "The terms changed. Please wait for a fresh proposal before confirming.", case, False
    action = case.details.get("action", case.kind)
    eligible(order, action, rules)
    if rules.get(f"{action}_permission") == "approval_required" and not case.seller_approved:
        raise HTTPException(403, "The published policy requires seller approval.")
    d = case.details
    complete = False
    if action == "customization":
        if (d.get("engraving") or d.get("special_request")) and not case.seller_approved:
            raise HTTPException(403, "Seller approval is required.")
        order.customizations = [
            *order.customizations,
            {"case_id": case.id, **d, "quote_paise": case.quote_paise},
        ]
        order.total_paise += case.quote_paise + d.get("gift_wrap_paise", 0)
        result = f"Your customization terms are saved. Order total: {amount(order.total_paise)}. Preparation continues with the store."
        complete = True
    elif action == "pickup":
        if rules["pickup"] == "approval_required" and not case.seller_approved:
            raise HTTPException(403, "Seller approval required.")
        if db.scalar(
            select(Reservation).where(
                Reservation.order_id == order.id, Reservation.status.in_(["reserved", "ready"])
            )
        ):
            raise HTTPException(409, "An active pickup already exists.")
        slot = scoped(db, PickupSlot, d["slot_id"], conv.merchant_id, lock=True)
        if slot.reserved >= slot.capacity or (slot.ends_at and utc(slot.ends_at) <= now()):
            raise HTTPException(409, "This pickup window is unavailable.")
        reserve_inventory(db, order)
        slot.reserved += 1
        code = f"{secrets.randbelow(1000000):06d}"
        reservation = Reservation(
            case_id=case.id,
            order_id=order.id,
            slot_id=slot.id,
            code_hash=hashlib.sha256(code.encode()).hexdigest(),
        )
        db.add(reservation)
        db.flush()
        order.status = "confirmed"
        order.delivery_status = "pickup_reserved"
        transition(db, case, "ongoing", "pickup_reserved")
        result = f"Pickup reserved for {slot.label}. Collection code: {code}. Bring it to {slot.location}."
    elif action == "return":
        db.add(
            ReturnRecord(merchant_id=conv.merchant_id, case_id=case.id, order_id=order.id, reason=d["reason"])
        )
        transition(db, case, "ongoing", "awaiting_return")
        result = "Your return is authorized. Courier collection is simulated. The case stays open until receipt, inspection and the required resolution."
    elif action == "refund":
        pending = pending_refunds(db, order)
        value = d["amount_paise"]
        if value <= 0 or value > order.paid_paise - order.refunded_paise - pending:
            raise HTTPException(409, "This amount exceeds the remaining refundable balance.")
        if (
            order.refunded_paise + pending + value > rules["auto_refund_limit_paise"]
            and not case.seller_approved
        ):
            raise HTTPException(409, "Cumulative refund limit requires seller approval.")
        inspected = db.scalar(
            select(ReturnRecord).where(ReturnRecord.order_id == order.id, ReturnRecord.status == "accepted")
        )
        if (
            rules["require_return_inspection"]
            and not inspected
            and not (case.seller_approved and d.get("return_waiver"))
            and order.status != "cancelled"
        ):
            raise HTTPException(409, "Return inspection or an approved waiver is required.")
        db.add(
            Refund(
                case_id=case.id, order_id=order.id, amount_paise=value, status="pending", provider="simulated"
            )
        )
        queue_operation(db, case, "refund", {"amount_paise": value})
        transition(db, case, "ongoing", "executing")
        result = f"Your simulated refund of {amount(value)} is processing. No real money will move."
    elif action == "cancellation":
        release_inventory(db, order)
        for reservation in db.scalars(
            select(Reservation)
            .where(Reservation.order_id == order.id, Reservation.status.in_(["reserved", "ready"]))
            .with_for_update()
        ):
            slot = scoped(db, PickupSlot, reservation.slot_id, conv.merchant_id, lock=True)
            slot.reserved -= 1
            reservation.status = "cancelled"
        order.status = "cancelled"
        order.delivery_status = "cancelled"
        result = "The order is cancelled. Any remaining paid balance needs a separately confirmed simulated refund."
        complete = True
    else:
        if action in {"replacement", "warranty"} and not case.seller_approved:
            raise HTTPException(403, "Seller approval required.")
        if action in {"replacement", "checkout"}:
            reserve_inventory(db, order)
        queue_operation(db, case, action, d)
        transition(db, case, "ongoing", "executing")
        result = f"Your simulated {action} is processing. We will report the saved provider result."
    case.consented_at = now()
    audit(
        db,
        conv.merchant_id,
        f"customer:{conv.customer_id}",
        "proposal.accepted",
        case.id,
        reference=reference,
        revision=case.proposal_revision,
        terms_hash=case.terms_hash,
    )
    if action not in {"refund", "redelivery", "replacement", "warranty", "checkout"}:
        db.add(
            Operation(
                id=f"op:{case.id}:{case.proposal_revision}",
                merchant_id=case.merchant_id,
                case_id=case.id,
                kind=action,
                status="succeeded",
                provider="local",
                detail={"result": result},
            )
        )
    return result, case, complete


def queue_operation(db, case, kind, detail):
    oid = f"op:{case.id}:{case.proposal_revision}"
    if db.get(Operation, oid):
        return
    db.add(Operation(id=oid, merchant_id=case.merchant_id, case_id=case.id, kind=kind, detail=detail))
    db.add(Job(id=oid, kind="operation", payload={"operation_id": oid}))


def complete_operation(db, operation):
    if operation.status == "succeeded":
        return
    case = scoped(db, Case, operation.case_id, operation.merchant_id, lock=True)
    order = scoped(db, Order, case.order_id, case.merchant_id, lock=True)
    conv = db.get(Conversation, case.conversation_id)
    if operation.kind == "refund":
        refund = db.scalar(select(Refund).where(Refund.case_id == case.id).with_for_update())
        if refund.status not in {"pending", "uncertain"}:
            return
        refund.status = "succeeded"
        order.refunded_paise += refund.amount_paise
        result = (
            f"SIMULATED refund completed: {amount(refund.amount_paise)} for {order.id}. No real money moved."
        )
    elif operation.kind == "redelivery":
        order.delivery_status = "redelivery_scheduled"
        result = f"SIMULATED courier redelivery scheduled for {order.id}. No real courier booking was made."
    elif operation.kind == "checkout":
        order.paid_paise = order.total_paise
        order.status = "confirmed"
        result = f"SIMULATED payment recorded: {amount(order.total_paise)}. No real money moved."
    elif operation.kind == "replacement":
        release_inventory(db, order, collected=True)
        order.status = "replacement_dispatched"
        result = "SIMULATED replacement dispatched. No physical courier dispatch was made."
    else:
        result = "SIMULATED warranty review completed. No external warranty provider was contacted."
    operation.status = "succeeded"
    operation.updated_at = now()
    operation.detail = {**operation.detail, "result": result}
    audit(
        db,
        case.merchant_id,
        "simulated-provider",
        f"{operation.kind}.succeeded",
        case.id,
        operation_id=operation.id,
    )
    reply(
        db,
        conv,
        result + " You can reply with a rating from 1 to 5 stars.",
        role="system",
        cases=[case],
        completes=True,
    )


def inspect_return(db, case, actor, data):
    item = db.scalar(select(ReturnRecord).where(ReturnRecord.case_id == case.id).with_for_update())
    if not item or item.status != "awaiting_return":
        raise HTTPException(409, "No return is awaiting inspection.")
    order = scoped(db, Order, item.order_id, case.merchant_id, lock=True)
    item.received_at = now()
    item.status = "accepted" if data.accepted else "rejected"
    case.seller_assisted = True
    if data.restock:
        if not data.accepted:
            raise HTTPException(422, "Rejected goods cannot be restocked.")
        product = scoped(db, Product, order.product_id, case.merchant_id, lock=True)
        product.stock += 1
        item.restocked = True
    audit(
        db,
        case.merchant_id,
        actor,
        "return.inspected",
        case.id,
        accepted=data.accepted,
        restock=data.restock,
        note=data.note,
    )
    conv = db.get(Conversation, case.conversation_id)
    if not data.accepted:
        reply(
            db,
            conv,
            f"Store team: Your return inspection was declined. {data.note}",
            role="system",
            cases=[case],
            completes=True,
        )
        return
    current = policy(db, case.merchant_id)
    value = order.paid_paise - order.refunded_paise - pending_refunds(db, order)
    if value <= 0:
        raise HTTPException(409, "No refundable balance remains.")
    case.details = {**case.details, "action": "refund", "amount_paise": value, "return_inspected": True}
    case.policy_version = current.version
    case.seller_approved = False
    if current.rules["refund_permission"] != "automatic":
        flag(db, case, "Return accepted; the published refund permission requires seller review.")
        reply(
            db,
            conv,
            "Your return was accepted. The refund needs store review under the published policy.",
            role="system",
            cases=[case],
        )
    elif value + order.refunded_paise + pending_refunds(db, order) > current.rules["auto_refund_limit_paise"]:
        flag(db, case, "Return accepted; refund exceeds the automatic limit and needs seller approval.")
        reply(
            db,
            conv,
            "Your return was accepted. The refund amount needs seller approval.",
            role="system",
            cases=[case],
        )
    else:
        issue_proposal(db, case, order)
        reply(db, conv, confirmation_text(db, case), role="system", cases=[case])


def pickup_action(db, reservation_id, merchant_id, actor, action, code=None):
    reservation = db.scalar(
        select(Reservation)
        .join(Order)
        .where(Reservation.id == reservation_id, Order.merchant_id == merchant_id)
        .with_for_update()
    )
    if not reservation:
        raise HTTPException(404, "Reservation not found")
    case = scoped(db, Case, reservation.case_id, merchant_id, lock=True)
    conv = db.get(Conversation, case.conversation_id)
    order = scoped(db, Order, reservation.order_id, merchant_id, lock=True)
    if action == "ready":
        if reservation.status != "reserved":
            raise HTTPException(409, "Pickup must be reserved.")
        reservation.status = "ready"
        transition(db, case, "ongoing", "pickup_ready")
        reply(
            db,
            conv,
            "Store team: Your order is ready. Bring your private collection code.",
            role="system",
            cases=[case],
        )
    elif action == "cancel":
        if reservation.status not in {"reserved", "ready"}:
            raise HTTPException(409, "No active pickup to cancel.")
        reservation.status = "cancelled"
        release_inventory(db, order)
        slot = scoped(db, PickupSlot, reservation.slot_id, merchant_id, lock=True)
        slot.reserved -= 1
        order.delivery_status = "not_shipped"
        reply(
            db,
            conv,
            "Store team: Your pickup reservation was cancelled. Stock and slot capacity were released.",
            role="system",
            cases=[case],
            completes=True,
        )
    else:
        if reservation.status != "ready" or reservation.attempts >= 5:
            raise HTTPException(409, "Pickup must be ready and code attempts must remain.")
        if not secrets.compare_digest(
            reservation.code_hash, hashlib.sha256((code or "").encode()).hexdigest()
        ):
            reservation.attempts += 1
            audit(db, merchant_id, actor, "pickup.invalid_code", case.id, attempts=reservation.attempts)
            db.commit()
            raise HTTPException(422, "Incorrect collection code.")
        release_inventory(db, order, collected=True)
        slot = scoped(db, PickupSlot, reservation.slot_id, merchant_id, lock=True)
        slot.reserved -= 1
        reservation.status = "collected"
        order.status = "delivered"
        order.delivery_status = "delivered"
        order.delivered_at = now()
        balance = order.total_paise - order.paid_paise
        order.paid_paise = order.total_paise
        db.add(
            Operation(
                id=f"collect:{reservation.id}",
                merchant_id=merchant_id,
                case_id=case.id,
                kind="collection_payment",
                status="succeeded",
                detail={"amount_paise": balance, "simulated": True},
            )
        )
        reply(
            db,
            conv,
            f"Pickup complete. SIMULATED collection payment: {amount(balance)}. No real money moved. Please rate your experience from 1 to 5 stars.",
            role="system",
            cases=[case],
            completes=True,
        )
    audit(db, merchant_id, actor, f"pickup.{action}", case.id, reservation_id=reservation.id)
    return reservation
