import json
from datetime import timedelta
from sqlalchemy import select
from app.core.config import ROOT, get_settings
from app.db.models import (
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
)
from app.modules.common import audit
from app.db.models import Job


def seed(db):
    if db.get(Merchant, "SELLER001"):
        return False
    if not get_settings().demo_mode:
        raise ValueError("Demo seed is disabled outside demo mode")
    data = json.loads((ROOT / "data/demo/seeds/store.json").read_text(encoding="utf-8"))
    db.add(Merchant(**data["merchant"]))
    db.flush()
    merchant = "SELLER001"
    for name, model in [("customers", Customer), ("products", Product)]:
        for row in data[name]:
            db.add(model(merchant_id=merchant, **row))
    db.flush()
    for row in data["orders"]:
        db.add(Order(merchant_id=merchant, **row))
    db.add(Policy(id="POLICY001", merchant_id=merchant, version=1, rules=data["policy"], published=True))
    for row in data["slots"]:
        db.add(PickupSlot(merchant_id=merchant, **row))
    for row in data["reviews"]:
        db.add(Review(merchant_id=merchant, **row))
    if get_settings().seller_user_id:
        db.add(Membership(user_id=get_settings().seller_user_id, merchant_id=merchant, role="owner"))
    db.flush()
    db.add_all(
        [
            Conversation(id="CONV001", merchant_id=merchant, customer_id="CUS001", order_id="ORD1042"),
            Conversation(id="CONV002", merchant_id=merchant, customer_id="CUS002", order_id="ORD1043"),
        ]
    )
    db.flush()
    db.add_all(
        [
            Message(
                id="seed-message-1",
                conversation_id="CONV001",
                role="customer",
                body="My headphones delivery failed. Can you help me get them?",
                status="received",
            ),
            Message(
                id="seed-message-2",
                conversation_id="CONV001",
                role="assistant",
                body="The courier could not locate your address. I can arrange a new delivery after you confirm your address.",
                status="demo_delivered",
            ),
            Message(
                id="seed-message-3",
                conversation_id="CONV002",
                role="customer",
                body="Can you engrave Aarav on the wallet and gift-wrap it for his birthday?",
                status="received",
            ),
            Message(
                id="seed-message-4",
                conversation_id="CONV002",
                role="assistant",
                body="Gift wrapping is available for ₹149. I’ve asked the seller for an engraving quote; you can review the total before accepting.",
                status="demo_delivered",
            ),
        ]
    )
    db.add(
        Case(
            id="CASE1043",
            merchant_id=merchant,
            conversation_id="CONV002",
            order_id="ORD1043",
            kind="customization",
            status="pending_seller",
            summary="Name engraving + birthday gift wrap",
            policy_version=1,
            details={"engraving": "Aarav", "gift_wrap": True, "gift_wrap_paise": 14900},
            expires_at=now() + timedelta(hours=24),
        )
    )
    audit(db, merchant, "system", "demo.seeded", merchant, orders=2, synthetic=True)
    db.add(
        Job(
            id="expire:CASE1043",
            kind="case_expire",
            payload={"case_id": "CASE1043"},
            available_at=now() + timedelta(hours=24),
        )
    )
    db.commit()
    return True
