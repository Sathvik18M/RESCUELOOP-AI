"""Audited reads used by the seller store API and Resolution AI workflow."""

from sqlalchemy import select

from app.domain.common import audit
from app.persistence.models import AuditLog, Order, Policy, Product, ShipmentEvent


def lookup_owned_order(db, conv, order_id, case_id, message_id):
    order = db.scalar(
        select(Order).where(
            Order.id == order_id,
            Order.merchant_id == conv.merchant_id,
            Order.customer_id == conv.customer_id,
        )
    )
    result = None
    if order:
        product = db.get(Product, order.product_id)
        result = {
            "order_id": order.id,
            "product_id": product.id,
            "product_name": product.name,
            "order_status": order.status,
            "delivery_status": order.delivery_status,
            "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        }
    audit(
        db,
        conv.merchant_id,
        "store-api",
        "tool.order_lookup",
        case_id,
        input_message_id=message_id,
        requested_order_id=order_id,
        ownership_verified=bool(order),
        result=result,
    )
    return order, result


def lookup_replacement_policy(db, conv, case_id, message_id):
    current = db.scalar(
        select(Policy)
        .where(Policy.merchant_id == conv.merchant_id, Policy.published.is_(True))
        .order_by(Policy.version.desc())
    )
    result = None
    if current:
        rules = current.rules
        result = {
            "version": current.version,
            # Existing replacements always require seller review; no policy is published here.
            "replacement_permission": rules.get("replacement_permission", "approval_required"),
            "seller_review_required": True,
            "window_days": rules.get("return_window_days"),
            "eligible_reasons": rules.get("return_reasons", []),
            "require_photo": rules.get("require_photo", True),
        }
    audit(
        db,
        conv.merchant_id,
        "store-api",
        "tool.replacement_policy_lookup",
        case_id,
        input_message_id=message_id,
        result=result,
    )
    return current, result


def lookup_shipment(db, conv, order_id, case_id, message_id):
    order, record = lookup_owned_order(db, conv, order_id, case_id, message_id)
    if not order:
        return None
    events = list(
        db.scalars(
            select(ShipmentEvent)
            .where(ShipmentEvent.merchant_id == conv.merchant_id, ShipmentEvent.order_id == order.id)
            .order_by(ShipmentEvent.occurred_at, ShipmentEvent.id)
        )
    )
    trail = [
        {
            "id": e.id,
            "status": e.status,
            "occurred_at": e.occurred_at.isoformat(),
            "source": e.source,
            "location": e.location,
            "proof": e.proof,
        }
        for e in events
    ]
    conflicts = []
    if events and events[-1].status.casefold() != order.delivery_status.casefold():
        conflicts.append(
            f"Order says {order.delivery_status}; latest shipment event says {events[-1].status}."
        )
    if order.status.casefold() == "delivered" and order.delivery_status.casefold() != "delivered":
        conflicts.append("Order fulfillment status and shipment status disagree.")
    source_records = list(
        db.scalars(
            select(AuditLog).where(
                AuditLog.merchant_id == conv.merchant_id,
                AuditLog.entity_id == order.id,
                AuditLog.action == "order.source_discrepancy_detected",
            )
        )
    )
    conflicts.extend(a.detail["summary"] for a in source_records if a.detail.get("summary"))
    delivery = next((e for e in reversed(events) if e.status.casefold() == "delivered"), None)
    result = {
        **record,
        "events": trail,
        "conflicting_evidence": list(dict.fromkeys(conflicts)),
        "history_available": bool(events),
        "delivery_location": delivery.location if delivery else None,
        "proof_of_delivery": delivery.proof if delivery and delivery.proof else None,
    }
    audit(
        db,
        conv.merchant_id,
        "store-api",
        "tool.shipment_lookup",
        case_id,
        input_message_id=message_id,
        result=result,
    )
    return result
