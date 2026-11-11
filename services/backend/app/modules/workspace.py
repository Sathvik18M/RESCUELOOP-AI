from sqlalchemy import select
from app.core.config import get_settings
from app.agents.specialists import insight_summary
from app.db.models import (
    Merchant,
    Product,
    Order,
    Customer,
    Conversation,
    Message,
    Case,
    Policy,
    PickupSlot,
    Reservation,
    Review,
    Evidence,
    AuditLog,
    Refund,
)
from app.modules.common import record


def workspace(db, merchant_id):
    def rows(model):
        return list(db.scalars(select(model).where(model.merchant_id == merchant_id)))

    products, orders, customers, conversations = (
        rows(Product),
        rows(Order),
        rows(Customer),
        rows(Conversation),
    )
    cases, reviews = rows(Case), rows(Review)
    customer_map = {c.id: c for c in customers}
    product_map = {p.id: p for p in products}
    conversation_ids = [c.id for c in conversations]
    order_ids = [o.id for o in orders]
    messages = list(
        db.scalars(
            select(Message).where(Message.conversation_id.in_(conversation_ids)).order_by(Message.created_at)
        )
    )
    conv_data = [
        {
            **record(c),
            "customer_name": customer_map[c.customer_id].name,
            "messages": [record(m) for m in messages if m.conversation_id == c.id],
        }
        for c in conversations
    ]
    order_data = [
        {
            **record(o),
            "customer_name": customer_map[o.customer_id].name,
            "product_name": product_map[o.product_id].name,
        }
        for o in orders
    ]
    evidence = [
        {key: value for key, value in record(e).items() if key != "object_key"} for e in rows(Evidence)
    ]
    reservations = [
        {key: value for key, value in record(r).items() if key != "code_hash"}
        for r in db.scalars(select(Reservation).where(Reservation.order_id.in_(order_ids)))
    ]
    logs = list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.merchant_id == merchant_id)
            .order_by(AuditLog.created_at.desc())
            .limit(100)
        )
    )
    settings = get_settings()
    return {
        "merchant": record(db.get(Merchant, merchant_id)),
        "products": [record(p) for p in products],
        "orders": order_data,
        "conversations": conv_data,
        "cases": [record(c) for c in sorted(cases, key=lambda c: c.created_at, reverse=True)],
        "policies": [record(p) for p in sorted(rows(Policy), key=lambda p: p.version, reverse=True)],
        "slots": [record(s) for s in rows(PickupSlot)],
        "reservations": reservations,
        "reviews": [record(r) for r in reviews],
        "evidence": evidence,
        "audit_logs": [record(log) for log in logs],
        "refunds": [record(r) for r in db.scalars(select(Refund).where(Refund.order_id.in_(order_ids)))],
        "metrics": {
            "orders": len(orders),
            "pending": sum(c.status == "pending_seller" for c in cases),
            "completed": sum(c.status == "completed" for c in cases),
            "open": sum(c.status in {"pending_seller", "pending_customer", "needs_details"} for c in cases),
            "rating": round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else 0,
            "paid_paise": sum(o.paid_paise for o in orders),
        },
        "insights": insight_summary(reviews, cases),
        "mode": {
            "demo": settings.demo_mode,
            "ai": settings.ai_mode,
            "whatsapp": bool(settings.whatsapp_access_token),
            "storage": "supabase" if settings.supabase_url else "local_private",
        },
    }
