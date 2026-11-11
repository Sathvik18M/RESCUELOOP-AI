from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from statistics import median
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings
from app.persistence.models import (
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
    Operation,
    ReturnRecord,
    InsightReport,
    ServiceState,
    Job,
    now,
)
from app.domain.common import record, utc


def date_window(date_from=None, date_to=None):
    today = now().astimezone(ZoneInfo("Asia/Kolkata")).date()
    try:
        end = date.fromisoformat(date_to) if date_to else today
        start = date.fromisoformat(date_from) if date_from else today - timedelta(days=13)
        if start > end or (end - start).days > 366:
            raise ValueError()
    except ValueError:
        raise HTTPException(422, "Choose a valid date range of up to one year.")
    tz = ZoneInfo("Asia/Kolkata")
    return (
        start,
        end,
        datetime.combine(start, time.min, tz).astimezone(timezone.utc),
        datetime.combine(end + timedelta(days=1), time.min, tz).astimezone(timezone.utc),
    )


def cohort(db, merchant_id, date_from=None, date_to=None):
    start, end, lower, upper = date_window(date_from, date_to)
    cases = list(
        db.scalars(
            select(Case)
            .where(Case.merchant_id == merchant_id, Case.created_at >= lower, Case.created_at < upper)
            .order_by(Case.created_at.desc())
        )
    )
    return start, end, cases


def metrics(cases, reviews):
    counts = Counter(c.primary_status for c in cases)
    resolved = [c for c in cases if c.primary_status == "resolved"]
    times = [
        (utc(c.resolved_at) - utc(c.created_at)).total_seconds() / 3600 for c in resolved if c.resolved_at
    ]
    return {
        "total": len(cases),
        "resolved": counts["resolved"],
        "ongoing": counts["ongoing"],
        "flagged": counts["flagged"],
        "resolution_rate": round(100 * len(resolved) / len(cases), 1) if cases else None,
        "ai_share": round(100 * sum(not c.seller_assisted for c in resolved) / len(resolved), 1)
        if resolved
        else None,
        "median_resolution_hours": round(median(times), 1) if times else None,
        "rating": round(sum(r.rating for r in reviews) / len(reviews), 1) if reviews else None,
        "review_count": len(reviews),
    }


def topic_insights(cases):
    groups = {}
    for c in cases:
        groups.setdefault(c.kind, []).append(c.id)
    return [
        {
            "topic": kind,
            "title": kind.replace("_", " ").title(),
            "case_ids": ids,
            "count": len(ids),
            "recurring": len(ids) >= 3,
            "description": f"{len(ids)} distinct case(s) in the selected cohort.",
        }
        for kind, ids in sorted(groups.items(), key=lambda pair: -len(pair[1]))
    ]


def workspace(db, merchant_id, date_from=None, date_to=None):
    def rows(model):
        return list(db.scalars(select(model).where(model.merchant_id == merchant_id)))

    start, end, cases = cohort(db, merchant_id, date_from, date_to)
    all_cases = rows(Case)
    products, orders, customers, conversations = (
        rows(Product),
        rows(Order),
        rows(Customer),
        rows(Conversation),
    )
    customer_map = {c.id: c for c in customers}
    product_map = {p.id: p for p in products}
    cids = [c.id for c in conversations]
    oids = [o.id for o in orders]
    selected = {c.id for c in cases}
    messages = list(
        db.scalars(
            select(Message).where(Message.conversation_id.in_(cids)).order_by(Message.created_at, Message.id)
        )
    )
    reviews = [r for r in rows(Review) if r.case_id in selected]
    heartbeat = db.get(ServiceState, "worker")
    alive = bool(heartbeat and (now() - utc(heartbeat.updated_at)).total_seconds() < 30)
    s = get_settings()
    failed = list(db.scalars(select(Job).where(Job.status.in_(["failed", "needs_review"]))))
    own_message_ids = {m.id for m in messages}
    related_failures = [
        j
        for j in failed
        if j.payload.get("message_id") in own_message_ids
        or j.payload.get("operation_id") in {o.id for o in rows(Operation)}
    ]
    from app.integrations.whatsapp import is_configured
    status = (
        "integration_unavailable"
        if not alive
        else "local_verification"
        if s.ai_mode == "demo"
        else "configured"
        if s.groq_api_key and is_configured(s)
        else "integration_unavailable"
    )
    if related_failures:
        status = "processing_delayed"
    return {
        "merchant": record(db.get(Merchant, merchant_id)),
        "customers": [{"id": c.id, "name": c.name, "phone": c.phone} for c in customers],
        "products": [{**record(p), "available_stock": p.stock - p.reserved_stock} for p in products],
        "orders": [
            {
                **record(o),
                "customer_name": customer_map[o.customer_id].name,
                "product_name": product_map[o.product_id].name,
            }
            for o in orders
        ],
        "conversations": [
            {
                **record(c),
                "customer_name": customer_map[c.customer_id].name,
                "messages": [record(m) for m in messages if m.conversation_id == c.id],
            }
            for c in conversations
        ],
        "cases": [record(c) for c in cases],
        "policies": [record(p) for p in sorted(rows(Policy), key=lambda p: p.version, reverse=True)],
        "slots": [record(s) for s in rows(PickupSlot)],
        "reservations": [
            {k: v for k, v in record(r).items() if k != "code_hash"}
            for r in db.scalars(select(Reservation).where(Reservation.order_id.in_(oids)))
        ],
        "reviews": [record(r) for r in reviews],
        "evidence": [{k: v for k, v in record(e).items() if k != "object_key"} for e in rows(Evidence)],
        "audit_logs": [
            record(a)
            for a in db.scalars(
                select(AuditLog)
                .where(AuditLog.merchant_id == merchant_id)
                .order_by(AuditLog.created_at.desc())
                .limit(500)
            )
        ],
        "refunds": [record(r) for r in db.scalars(select(Refund).where(Refund.order_id.in_(oids)))],
        "returns": [record(r) for r in rows(ReturnRecord)],
        "operations": [record(o) for o in rows(Operation)],
        "metrics": metrics(cases, reviews),
        "insights": topic_insights(cases),
        "reports": [
            record(r) for r in sorted(rows(InsightReport), key=lambda r: r.generated_at, reverse=True)[:10]
        ],
        "date_range": {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "timezone": "Asia/Kolkata",
            "basis": "Created during period · current status",
        },
        "mode": {
            "demo": s.demo_mode,
            "ai": s.ai_mode,
            "whatsapp": is_configured(s),
            "whatsapp_provider": s.whatsapp_provider,
            "storage": "supabase" if s.supabase_url else "local_private",
            "service_status": status,
            "worker_alive": alive,
            "failed_jobs": len(related_failures),
        },
    }
