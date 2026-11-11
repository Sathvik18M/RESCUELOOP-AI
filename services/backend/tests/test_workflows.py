from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select
from app.db.models import (
    Case,
    Conversation,
    Order,
    Product,
    Refund,
    Reservation,
    PickupSlot,
    Policy,
    Message,
    Merchant,
    now,
)
from app.modules.commerce import create_case


def send(client, auth, text, conv="CONV002", message_id=None):
    response = client.post(
        f"/api/demo/conversations/{conv}/messages",
        headers=auth,
        json={"text": text, "message_id": message_id or str(uuid4())},
    )
    assert response.status_code == 200, response.text
    return response.json()


def approve(client, auth, case_id, quote=0):
    response = client.post(
        f"/api/cases/{case_id}/decision",
        headers=auth,
        json={"decision": "approve", "quote_paise": quote, "note": "Approved", "preparation_days": 1},
    )
    assert response.status_code == 200, response.text


def latest(db, kind):
    return db.scalar(select(Case).where(Case.kind == kind).order_by(Case.created_at.desc()))


def delivered(client, auth):
    assert client.post("/api/demo/scenarios/delivered", headers=auth).status_code == 200


def test_auth_is_required(client):
    assert client.get("/api/workspace").status_code == 401
    assert client.get("/api/workspace", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_seed_workspace_and_private_fields(client, auth):
    r = client.get("/api/workspace", headers=auth)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["orders"]) == 2
    assert data["metrics"]["pending"] == 1
    assert "code_hash" not in r.text and "object_key" not in r.text


def test_approval_does_not_apply_customization_until_customer_confirms(client, auth, db):
    approve(client, auth, "CASE1043", 19900)
    assert db.get(Order, "ORD1043").total_paise == 79900
    send(client, auth, "CONFIRM CASE1043")
    assert db.get(Order, "ORD1043").total_paise == 114700
    assert db.get(Case, "CASE1043").status == "completed"
    send(client, auth, "CONFIRM CASE1043")
    assert db.get(Order, "ORD1043").total_paise == 114700


def test_pickup_confirmation_reserves_stock_and_capacity(client, auth, db):
    send(client, auth, "Can I collect the wallet tomorrow afternoon?")
    case = latest(db, "pickup")
    assert case.status == "pending_seller"
    approve(client, auth, case.id)
    assert db.get(Product, "WALLET001").stock == 18
    send(client, auth, f"CONFIRM {case.id}")
    assert db.get(Product, "WALLET001").stock == 17
    assert db.get(PickupSlot, "SLOT-PM").reserved == 1
    assert len(list(db.scalars(select(Reservation)))) == 1
    send(client, auth, f"CONFIRM {case.id}")
    assert db.get(Product, "WALLET001").stock == 17


def test_full_pickup_slot_blocks_confirmation_without_stock_change(client, auth, db):
    send(client, auth, "Store pickup afternoon")
    case = latest(db, "pickup")
    approve(client, auth, case.id)
    db.get(PickupSlot, "SLOT-PM").reserved = 5
    db.commit()
    result = send(client, auth, f"CONFIRM {case.id}")
    assert "full" in result["reply"]
    assert db.get(Product, "WALLET001").stock == 18


def test_refund_cap_and_paid_amount(client, auth, db):
    delivered(client, auth)
    send(client, auth, "I want a refund", conv="CONV001")
    case = latest(db, "refund")
    assert case.status == "pending_seller"
    send(client, auth, f"CONFIRM {case.id}", conv="CONV001")
    assert db.get(Order, "ORD1042").refunded_paise == 0
    approve(client, auth, case.id)
    send(client, auth, f"CONFIRM {case.id}", conv="CONV001")
    assert db.get(Order, "ORD1042").refunded_paise == 199900
    assert len(list(db.scalars(select(Refund)))) == 1
    result = send(client, auth, "Refund again", conv="CONV001")
    assert "remaining paid" in result["reply"]


def test_split_refunds_cannot_bypass_limit(client, auth, db):
    delivered(client, auth)
    send(client, auth, "Refund ₹200 please", conv="CONV001")
    first = latest(db, "refund")
    assert first.status == "pending_customer"
    send(client, auth, f"CONFIRM {first.id}", conv="CONV001")
    send(client, auth, "Refund ₹200 please", conv="CONV001")
    second = latest(db, "refund")
    assert second.id != first.id
    assert second.status == "pending_seller"


def test_refund_requires_delivery(client, auth, db):
    result = send(client, auth, "I want a refund", conv="CONV001")
    assert "delivered order" in result["reply"]
    assert latest(db, "refund") is None


def test_redelivery_requires_address_and_consent(client, auth, db):
    result = send(client, auth, "Redelivery please", conv="CONV001")
    assert "Address:" in result["reply"]
    send(client, auth, "Address: 12 Demo Road, Bengaluru", conv="CONV001")
    case = latest(db, "redelivery")
    assert db.get(Order, "ORD1042").delivery_status == "failed_attempt"
    send(client, auth, f"CONFIRM {case.id}", conv="CONV001")
    assert db.get(Order, "ORD1042").delivery_status == "redelivery_scheduled"


def test_duplicate_inbound_message_has_one_effect(client, auth, db):
    message_id = str(uuid4())
    send(client, auth, "Store pickup please", message_id=message_id)
    second = send(client, auth, "Store pickup please", message_id=message_id)
    assert second["duplicate"]
    assert len(list(db.scalars(select(Case).where(Case.kind == "pickup")))) == 1


def test_cannot_confirm_another_customers_case(client, auth, db):
    approve(client, auth, "CASE1043", 19900)
    result = send(client, auth, "CONFIRM CASE1043", conv="CONV001")
    assert "different conversation" in result["reply"]
    assert db.get(Order, "ORD1043").total_paise == 79900


def test_order_number_does_not_prove_customer_ownership(client, auth):
    result = send(client, auth, "Track ORD1042", conv="CONV002")
    assert "could not verify" in result["reply"]


def test_handoff_pauses_ai_and_seller_reply_is_idempotent(client, auth, db):
    client.patch("/api/conversations/CONV002/handoff", headers=auth, json={"enabled": True})
    send(client, auth, "Store pickup please")
    assert latest(db, "pickup") is None
    key = str(uuid4())
    for _ in range(2):
        response = client.post(
            "/api/conversations/CONV002/reply",
            headers=auth,
            json={"text": "Hello from the seller", "message_id": key},
        )
        assert response.status_code == 200, response.text
    assert len(list(db.scalars(select(Message).where(Message.body == "Hello from the seller")))) == 1


def test_policy_publish_invalidates_pending_requests(client, auth, db):
    current = client.get("/api/policies", headers=auth).json()["rules"]
    current["return_window_days"] = 14
    r = client.post("/api/policies/publish", headers=auth, json=current)
    assert r.status_code == 200, r.text
    assert db.get(Case, "CASE1043").status == "expired"
    assert len(list(db.scalars(select(Policy)))) == 2


def test_expired_approval_does_not_execute(client, auth, db):
    approve(client, auth, "CASE1043", 19900)
    db.get(Case, "CASE1043").expires_at = now() - timedelta(hours=1)
    db.commit()
    result = send(client, auth, "CONFIRM CASE1043")
    assert "expired" in result["reply"]
    assert db.get(Order, "ORD1043").total_paise == 79900


def test_store_isolation(client, auth, db):
    db.add(Merchant(id="OTHER", name="Other store", settings={}))
    db.flush()
    db.add(
        Product(
            id="OTHER-PRODUCT",
            merchant_id="OTHER",
            name="Secret",
            description="",
            price_paise=100,
            stock=1,
            category="Other",
            options={},
        )
    )
    db.commit()
    response = client.patch(
        "/api/products/OTHER-PRODUCT", headers=auth, json={"stock": 9, "price_paise": 100}
    )
    assert response.status_code == 404
    assert "OTHER-PRODUCT" not in client.get("/api/workspace", headers=auth).text


def test_invalid_image_rejected(client, auth):
    r = client.post(
        "/api/demo/conversations/CONV001/evidence",
        headers=auth,
        files={"file": ("bad.jpg", b"not an image", "image/jpeg")},
    )
    assert r.status_code == 422


def test_webhook_rejects_unsigned_requests(client):
    assert client.post("/webhooks/whatsapp", json={}).status_code == 403


def test_out_of_stock_does_not_complete_checkout(client, auth, db):
    db.get(Product, "WALLET001").stock = 0
    db.commit()
    send(client, auth, "Checkout please")
    case = latest(db, "checkout")
    result = send(client, auth, f"CONFIRM {case.id}")
    assert "out of stock" in result["reply"]
    assert db.get(Order, "ORD1043").status == "draft"


def test_decline_preserves_order(client, auth, db):
    approve(client, auth, "CASE1043", 19900)
    send(client, auth, "DECLINE CASE1043")
    assert db.get(Case, "CASE1043").status == "declined"
    assert db.get(Order, "ORD1043").total_paise == 79900


def test_request_details_reenters_seller_review(client, auth, db):
    r = client.post(
        "/api/cases/CASE1043/decision",
        headers=auth,
        json={"decision": "request_details", "note": "Which name?"},
    )
    assert r.status_code == 200
    send(client, auth, "Please use the name Aarav")
    case = db.get(Case, "CASE1043")
    assert case.status == "pending_seller"
    assert "Aarav" in case.details["customer_clarification"]
