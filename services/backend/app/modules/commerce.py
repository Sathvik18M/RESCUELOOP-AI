import hashlib
import secrets
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from app.db.models import Case, Conversation, Order, Product, PickupSlot, Reservation, Refund, Job, now
from app.modules.common import audit, policy, reply, scoped, utc

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
    if order.status != "draft":
        return order.total_paise
    # Integer arithmetic rounds half a paise up, avoiding binary floating-point money calculations.
    tax = (order.total_paise * rules["tax_basis_points"] + 5000) // 10000
    return order.total_paise + tax + (0 if pickup else rules["delivery_fee_paise"])


def eligible(order, kind, rules):
    if kind in {"return", "replacement", "refund", "warranty"}:
        if kind == "refund" and order.status == "cancelled" and order.paid_paise > order.refunded_paise:
            return
        if order.delivered_at is None or order.delivery_status != "delivered":
            raise HTTPException(409, "This action requires a delivered order. Check delivery first.")
        days = rules["warranty_days"] if kind == "warranty" else rules["return_window_days"]
        if now() - utc(order.delivered_at) > timedelta(days=days):
            raise HTTPException(
                409, "The configured eligibility window has ended. Ask the seller for assistance."
            )
    if kind == "cancellation" and (
        not rules["cancellation_before_shipping"] or order.status not in {"draft", "confirmed"}
    ):
        raise HTTPException(409, "This order can no longer be automatically cancelled.")
    if kind == "redelivery" and order.delivery_status != "failed_attempt":
        raise HTTPException(409, "A redelivery request requires a failed delivery attempt.")
    if kind in {"customization", "checkout"} and order.status != "draft":
        raise HTTPException(409, "Only a draft order can be changed or checked out.")
    if kind == "pickup":
        if rules["pickup"] == "prohibited":
            raise HTTPException(409, "Store pickup is not available under the current policy.")
        if order.status not in {"draft", "confirmed"}:
            raise HTTPException(409, "Pickup is available before shipping only.")


def create_case(db, conv, kind, summary, details=None):
    if kind not in KINDS:
        raise HTTPException(422, "Unsupported action")
    order = scoped(db, Order, conv.order_id, conv.merchant_id, lock=True)
    if order.customer_id != conv.customer_id:
        raise HTTPException(403, "Order ownership could not be verified")
    existing = db.scalar(
        select(Case).where(
            Case.order_id == order.id,
            Case.kind == kind,
            Case.status.in_(["pending_seller", "pending_customer", "needs_details"]),
        )
    )
    if existing and utc(existing.expires_at) > now():
        return existing
    if existing:
        existing.status = "expired"
    current = policy(db, conv.merchant_id)
    eligible(order, kind, current.rules)
    details = dict(details or {})
    product = db.get(Product, order.product_id)
    needs_seller = kind in {"customization", "warranty", "replacement"}
    if kind == "customization":
        if details.get("gift_wrap") and any(c.get("gift_wrap") for c in order.customizations):
            raise HTTPException(409, "Gift wrapping has already been added to this order")
        details["gift_wrap_paise"] = (
            product.options.get("gift_wrap_paise", 0) if details.get("gift_wrap") else 0
        )
        needs_seller = bool(details.get("engraving") or details.get("special_request"))
    if kind == "pickup":
        needs_seller = current.rules["pickup"] == "approval_required"
        slot_id = details.get("slot_id", "SLOT-PM")
        slot = scoped(db, PickupSlot, slot_id, conv.merchant_id)
        if slot.reserved >= slot.capacity:
            raise HTTPException(409, "This pickup slot is full")
        if db.scalar(
            select(Reservation).where(Reservation.order_id == order.id, Reservation.status != "cancelled")
        ):
            raise HTTPException(409, "This order already has a pickup reservation")
        details["slot_id"] = slot.id
        details["slot_label"] = slot.label
    if kind == "refund":
        remaining = order.paid_paise - order.refunded_paise
        requested = details.get("amount_paise") or remaining
        if not isinstance(requested, int) or requested <= 0 or requested > remaining:
            raise HTTPException(409, "Refund must be within the remaining paid amount")
        details["amount_paise"] = requested
        needs_seller = order.refunded_paise + requested > current.rules["auto_refund_limit_paise"]
    case = Case(
        merchant_id=conv.merchant_id,
        conversation_id=conv.id,
        order_id=order.id,
        kind=kind,
        summary=summary[:2000],
        details=details,
        policy_version=current.version,
        status="pending_seller" if needs_seller else "pending_customer",
        expires_at=now() + timedelta(hours=24),
    )
    db.add(case)
    db.flush()
    db.add(
        Job(
            id=f"expire:{case.id}",
            kind="case_expire",
            payload={"case_id": case.id},
            available_at=case.expires_at,
        )
    )
    audit(
        db,
        conv.merchant_id,
        "orchestrator",
        "case.created",
        case.id,
        kind=kind,
        status=case.status,
        policy_version=current.version,
    )
    return case


def decision(db, case_id, merchant_id, actor, data):
    case = scoped(db, Case, case_id, merchant_id, lock=True)
    if case.status not in {"pending_seller", "needs_details"}:
        raise HTTPException(409, "This request has already been decided or is awaiting customer confirmation")
    if utc(case.expires_at) <= now():
        raise HTTPException(409, "This request has expired; ask the customer to submit it again")
    conv = db.get(Conversation, case.conversation_id)
    if data.decision == "reject":
        case.status = "rejected"
        text = f"The seller could not approve your {case.kind} request. {data.note}"
    elif data.decision == "request_details":
        case.status = "needs_details"
        text = f"The seller needs a little more information: {data.note or 'Please describe your request in more detail.'}"
    else:
        case.status = "pending_customer"
        case.seller_approved = True
        case.quote_paise = data.quote_paise if case.kind == "customization" else 0
        case.details = {**case.details, "seller_note": data.note, "preparation_days": data.preparation_days}
        text = confirmation_text(db, case)
    audit(
        db, merchant_id, actor, f"case.{data.decision}", case.id, quote_paise=case.quote_paise, note=data.note
    )
    reply(db, conv, text)
    return case


def confirmation_text(db, case):
    order = db.get(Order, case.order_id)
    details = case.details
    if case.kind == "customization":
        extra = case.quote_paise + details.get("gift_wrap_paise", 0)
        total = order.total_paise + extra
        text = f"Your customization is available. Additional cost: {amount(extra)}. Updated subtotal: {amount(total)}. Preparation: {details.get('preparation_days', 1)} day(s)."
    elif case.kind == "refund":
        text = f"A simulated refund of {amount(details['amount_paise'])} is ready for confirmation."
    elif case.kind == "pickup":
        total = final_total(order, policy(db, order.merchant_id).rules, pickup=True)
        case.details = {**case.details, "confirmed_total_paise": total}
        text = f"Pickup is available at {details['slot_label']}. Total including configured tax: {amount(total)}. Any unpaid balance is due at collection; payment is simulated."
    elif case.kind == "checkout":
        current = policy(db, order.merchant_id).rules
        total = final_total(order, current)
        case.details = {**case.details, "confirmed_total_paise": total}
        text = f"Your complete order total is {amount(total)} including configured tax and delivery. Payment is simulated in this demo."
    else:
        text = f"Your {case.kind} request for {case.order_id} is ready."
    return f"{text} Reply CONFIRM {case.id} to accept, or DECLINE {case.id}."


def reserve_inventory(db, order):
    if order.inventory_reserved:
        return
    product = scoped(db, Product, order.product_id, order.merchant_id, lock=True)
    if product.stock <= 0:
        raise HTTPException(409, "This product is now out of stock")
    product.stock -= 1
    order.inventory_reserved = True


def confirm_case(db, case_id, conv, accept=True):
    case = scoped(db, Case, case_id, conv.merchant_id, lock=True)
    if case.conversation_id != conv.id:
        raise HTTPException(403, "This confirmation belongs to a different conversation")
    if case.status == "completed":
        return "This request has already been completed. No duplicate action was taken."
    if case.status != "pending_customer":
        raise HTTPException(409, "This request is not ready for customer confirmation")
    if not accept:
        case.status = "declined"
        audit(db, conv.merchant_id, f"customer:{conv.customer_id}", "case.declined", case.id)
        return "Your request was declined. Your order was not changed."
    if utc(case.expires_at) <= now():
        raise HTTPException(409, "This quotation has expired. Please request a new one.")
    order = scoped(db, Order, case.order_id, conv.merchant_id, lock=True)
    current = policy(db, conv.merchant_id)
    if current.version != case.policy_version:
        raise HTTPException(409, "The store policy changed. Please submit a new request for review.")
    eligible(order, case.kind, current.rules)
    result = ""
    if case.kind == "customization":
        if (
            case.details.get("engraving") or case.details.get("special_request")
        ) and not case.seller_approved:
            raise HTTPException(403, "Seller approval is required")
        order.customizations = [
            *order.customizations,
            {"case_id": case.id, **case.details, "quote_paise": case.quote_paise},
        ]
        order.total_paise += case.quote_paise + case.details.get("gift_wrap_paise", 0)
        result = f"Customization added. Order subtotal: {amount(order.total_paise)}. You can now request pickup or checkout."
    elif case.kind == "pickup":
        if current.rules["pickup"] == "approval_required" and not case.seller_approved:
            raise HTTPException(403, "Seller approval is required")
        total = final_total(order, current.rules, pickup=True)
        if total != case.details.get("confirmed_total_paise"):
            raise HTTPException(
                409, "The order total changed. Request a new pickup quotation before confirming."
            )
        if db.scalar(
            select(Reservation).where(Reservation.order_id == order.id, Reservation.status != "cancelled")
        ):
            raise HTTPException(409, "A pickup already exists for this order")
        slot = scoped(db, PickupSlot, case.details["slot_id"], conv.merchant_id, lock=True)
        if slot.reserved >= slot.capacity:
            raise HTTPException(409, "The pickup slot is now full. Please choose another slot.")
        reserve_inventory(db, order)
        code = f"{secrets.randbelow(1000000):06d}"
        slot.reserved += 1
        reservation = Reservation(
            case_id=case.id,
            order_id=order.id,
            slot_id=slot.id,
            code_hash=hashlib.sha256(code.encode()).hexdigest(),
        )
        db.add(reservation)
        db.flush()
        order.status = "confirmed"
        order.total_paise = total
        order.delivery_status = "pickup_reserved"
        result = f"Pickup reserved: {reservation.id}. {slot.label}. Collection code: {code}. Keep this code private."
    elif case.kind == "refund":
        value = case.details["amount_paise"]
        if value <= 0 or order.refunded_paise + value > order.paid_paise:
            raise HTTPException(409, "Refund exceeds the remaining paid amount")
        if (
            order.refunded_paise + value > current.rules["auto_refund_limit_paise"]
            and not case.seller_approved
        ):
            raise HTTPException(403, "Refund limit exceeded; seller approval is required")
        refund = Refund(case_id=case.id, order_id=order.id, amount_paise=value)
        db.add(refund)
        db.flush()
        order.refunded_paise += value
        result = f"Simulated refund completed: {refund.id}, {amount(value)}. No real money was transferred."
    elif case.kind == "redelivery":
        if not case.details.get("address"):
            raise HTTPException(409, "Please provide the redelivery address first")
        order.delivery_status = "redelivery_scheduled"
        result = "Redelivery scheduled with DemoCourier. The simulated courier request is saved."
    elif case.kind == "checkout":
        reserve_inventory(db, order)
        total = final_total(order, current.rules)
        if total != case.details.get("confirmed_total_paise"):
            raise HTTPException(409, "The total changed. Please request a fresh order summary.")
        order.total_paise = total
        order.paid_paise = total
        order.status = "confirmed"
        result = f"Order {order.id} confirmed. Simulated payment: {amount(total)}."
    elif case.kind == "cancellation":
        order.status = "cancelled"
        for reservation in db.scalars(
            select(Reservation).where(
                Reservation.order_id == order.id, Reservation.status.in_(["reserved", "ready"])
            )
        ):
            slot = scoped(db, PickupSlot, reservation.slot_id, conv.merchant_id, lock=True)
            slot.reserved = max(0, slot.reserved - 1)
            reservation.status = "cancelled"
        if order.inventory_reserved:
            product = scoped(db, Product, order.product_id, conv.merchant_id, lock=True)
            product.stock += 1
            order.inventory_reserved = False
        result = "Order cancelled. If a payment is due back, request a refund for review."
    elif case.kind == "return":
        order.status = "return_requested"
        result = f"Return request created: {case.id}. The seller will arrange the next steps."
    elif case.kind == "replacement":
        if not case.seller_approved:
            raise HTTPException(403, "Seller approval is required")
        product = scoped(db, Product, order.product_id, conv.merchant_id, lock=True)
        if product.stock <= 0:
            raise HTTPException(409, "Replacement stock is unavailable")
        product.stock -= 1
        order.status = "replacement_requested"
        result = f"Replacement reserved: {case.id}. The seller will arrange the exchange."
    elif case.kind == "warranty":
        if not case.seller_approved:
            raise HTTPException(403, "Seller approval is required")
        result = f"Warranty claim opened: {case.id}. Your seller will coordinate service."
    case.status = "completed"
    audit(
        db,
        conv.merchant_id,
        f"customer:{conv.customer_id}",
        f"{case.kind}.executed",
        case.id,
        order_id=order.id,
        policy_version=current.version,
        simulated=case.kind in {"refund", "checkout", "redelivery"},
    )
    return result
