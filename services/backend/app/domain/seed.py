import json
from datetime import timedelta, datetime, time
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.core.config import ROOT, get_settings
from app.persistence.models import (
    Customer,
    Merchant,
    Membership,
    Product,
    Order,
    Policy,
    Conversation,
    Review,
    PickupSlot,
    Case,
    Message,
    now,
    ReturnRecord,
)
from app.domain.schemas import PolicyRules
from app.domain.common import audit


def seed(db):
    if db.get(Merchant, "SELLER001"):
        return False
    if not get_settings().demo_mode:
        raise ValueError("Synthetic seed requires DEMO_MODE=true.")
    fixture = json.loads((ROOT / "data/demo/seeds/store.json").read_text(encoding="utf-8"))
    db.add(Merchant(**fixture["merchant"]))
    db.flush()
    merchant = "SELLER001"
    stamp = now()
    for row in fixture["customers"]:
        db.add(Customer(merchant_id=merchant, **row))
    for row in fixture["products"]:
        db.add(Product(merchant_id=merchant, **row))
    db.flush()
    for row in fixture["orders"]:
        values = {**row}
        if values["status"] == "delivered":
            values["delivered_at"] = stamp - timedelta(days=2)
        db.add(Order(merchant_id=merchant, **values))
    db.add(
        Policy(
            id="POLICY001", merchant_id=merchant, version=1, rules=PolicyRules().model_dump(), published=True
        )
    )
    tomorrow = (stamp.astimezone(ZoneInfo("Asia/Kolkata")) + timedelta(days=1)).date()
    for sid, hour in [("SLOT-AM", 11), ("SLOT-PM", 15)]:
        start = datetime.combine(tomorrow, time(hour), ZoneInfo("Asia/Kolkata"))
        end = start + timedelta(hours=2)
        label = (
            f"{start.strftime('%d %b %Y')} · {start.strftime('%I:%M %p')} – {end.strftime('%I:%M %p')} IST"
        )
        db.add(
            PickupSlot(
                id=sid,
                merchant_id=merchant,
                label=label,
                location="Loop & Co., Indiranagar",
                capacity=5,
                starts_at=start,
                ends_at=end,
            )
        )
    if get_settings().seller_user_id:
        db.add(Membership(user_id=get_settings().seller_user_id, merchant_id=merchant, role="owner"))
    db.flush()
    for cid, customer, oid in [
        ("CONV001", "CUS001", "ORD1042"),
        ("CONV002", "CUS002", "ORD1043"),
        ("CONV003", "CUS003", "ORD1044"),
    ]:
        db.add(Conversation(id=cid, merchant_id=merchant, customer_id=customer, order_id=oid, channel="demo"))
    db.flush()
    flagged = [
        (
            "CASE1042",
            "CONV001",
            "ORD1042",
            "refund",
            "Headphones arrived damaged — refund requested",
            {"reason": "damaged", "amount_paise": 199900},
            "Refund exceeds automatic limit; evidence and return inspection or waiver required.",
        ),
        (
            "CASE1043",
            "CONV002",
            "ORD1043",
            "customization",
            "Name engraving + birthday gift wrap",
            {"engraving": "Aarav", "gift_wrap": True, "gift_wrap_paise": 14900, "preparation_days": 1},
            "New engraving requires a seller decision.",
        ),
    ]
    for cid, conv, oid, kind, summary, details, reason in flagged:
        db.add(
            Case(
                id=cid,
                merchant_id=merchant,
                conversation_id=conv,
                order_id=oid,
                kind=kind,
                status="pending_seller",
                primary_status="flagged",
                summary=summary,
                details=details,
                flag_reason=reason,
                policy_version=1,
                quote_paise=19900 if kind == "customization" else 0,
                expires_at=stamp + timedelta(hours=24),
                created_at=stamp - timedelta(hours=2),
                checks=[
                    {"label": "Customer owns this order", "passed": True},
                    {"label": "Published policy v1 checked", "passed": True},
                ],
            )
        )
    for i in range(10):
        resolved = i < 6
        created = stamp - timedelta(days=13 - i, hours=1)
        kind = [
            "tracking",
            "tracking",
            "tracking",
            "catalog",
            "policy",
            "complaint",
            "complaint",
            "redelivery",
            "return",
            "tracking",
        ][i]
        db.add(
            Case(
                id=f"HIST{i + 1:03}",
                merchant_id=merchant,
                conversation_id="CONV003",
                order_id="ORD1044",
                kind=kind,
                summary=[
                    "Delivery status checked",
                    "Courier status explained",
                    "Tracking follow-up",
                    "Cable availability question",
                    "Return policy explained",
                    "Cable connection issue resolved",
                    "Customer is checking the connection",
                    "Customer preparing an address",
                    "Cable returned; awaiting receipt",
                    "Waiting for an order detail",
                ][i],
                status="completed" if resolved else "awaiting_return" if i == 8 else "needs_customer_details",
                primary_status="resolved" if resolved else "ongoing",
                policy_version=1,
                seller_assisted=i in {2, 5},
                created_at=created,
                updated_at=created + timedelta(hours=i + 1),
                resolved_at=created + timedelta(hours=i + 1) if resolved else None,
                expires_at=stamp + timedelta(hours=24),
                details={"reason": "defective"} if kind == "return" else {},
            )
        )
    db.flush()
    db.add(
        ReturnRecord(
            id="RETURN-DEMO-CABLE",
            merchant_id=merchant,
            case_id="HIST009",
            order_id="ORD1044",
            reason="defective",
        )
    )
    for i, rating in enumerate([4, 5, 3, 5]):
        db.add(
            Review(
                id=f"REV{i + 1:03}",
                merchant_id=merchant,
                case_id=f"HIST{i + 1:03}",
                product_id="CABLE001",
                author="Synthetic demo customer",
                rating=rating,
                body=[
                    "Tracking was clear.",
                    "Quick reply, thank you.",
                    "Delivery took longer than expected.",
                    "Helpful product details.",
                ][i],
                topic="tracking" if i < 3 else "catalog",
                source="demo",
            )
        )
    db.add_all(
        [
            Message(
                id="seed-message-1",
                conversation_id="CONV001",
                role="customer",
                body="My headphones arrived damaged. I want a refund.",
                status="received",
                case_ids=["CASE1042"],
            ),
            Message(
                id="seed-message-2",
                conversation_id="CONV001",
                role="assistant",
                body="Your refund request is saved for store review. Please send a clear photo of the damage.",
                status="demo_delivered",
                case_ids=["CASE1042"],
            ),
            Message(
                id="seed-message-3",
                conversation_id="CONV002",
                role="customer",
                body="Please engrave Aarav on the wallet and gift-wrap it for his birthday.",
                status="received",
                case_ids=["CASE1043"],
            ),
            Message(
                id="seed-message-4",
                conversation_id="CONV002",
                role="assistant",
                body="Gift wrapping is ₹149. The store is reviewing the ₹199 engraving quote before you accept the ₹1,147 total.",
                status="demo_delivered",
                case_ids=["CASE1043"],
            ),
            Message(
                id="seed-message-5",
                conversation_id="CONV003",
                role="customer",
                body="My cable is defective. I have sent it back.",
                status="received",
                case_ids=["HIST009"],
            ),
            Message(
                id="seed-message-6",
                conversation_id="CONV003",
                role="assistant",
                body="Your return is awaiting receipt and inspection. Courier operations are simulated.",
                status="demo_delivered",
                case_ids=["HIST009"],
            ),
        ]
    )
    audit(
        db,
        merchant,
        "system",
        "demo.seeded",
        merchant,
        synthetic=True,
        cases=12,
        resolved=6,
        ongoing=4,
        flagged=2,
    )
    db.commit()
    return True
