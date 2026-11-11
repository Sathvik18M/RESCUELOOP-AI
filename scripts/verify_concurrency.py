"""Exercise real competing transactions. Uses only a dedicated rescueloop_test database."""

import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import create_engine, select, delete
from sqlalchemy.orm import Session
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/backend"))
from app.persistence.models import (
    Merchant,
    Customer,
    Product,
    Order,
    Conversation,
    Case,
    Policy,
    PickupSlot,
    Reservation,
    Refund,
    Operation,
    Job,
    AuditLog,
    now,
)
from app.domain.schemas import PolicyRules
from app.domain.cases import issue_proposal
from app.domain.commerce import confirm_case, pending_refunds

url = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://rescueloop:rescueloop@127.0.0.1:5432/rescueloop_test_rebuild",
)
from sqlalchemy.engine import make_url

if not make_url(url).database.startswith("rescueloop_test"):
    raise RuntimeError("A dedicated rescueloop_test database is required.")
engine = create_engine(url)
prefix = "race-" + uuid4().hex[:8]
merchant = prefix
case_ids = [prefix + str(i) for i in range(4)]
order_ids = [prefix + "o" + str(i) for i in range(3)]
conv_ids = [prefix + "v" + str(i) for i in range(3)]
customer = prefix + "customer"
product = prefix + "product"
slot = prefix + "slot"
try:
    with Session(engine) as db:
        db.add(Merchant(id=merchant, name="Concurrency fixture", settings={}))
        db.flush()
        db.add(
            Customer(
                id=customer,
                merchant_id=merchant,
                name="Test customer",
                phone="+910000009999",
            )
        )
        db.add(
            Product(
                id=product,
                merchant_id=merchant,
                name="One physical unit",
                category="Test",
                price_paise=19900,
                stock=1,
                reserved_stock=0,
                options={},
            )
        )
        rules = PolicyRules(
            require_photo=False, require_return_inspection=False
        ).model_dump()
        db.add(Policy(merchant_id=merchant, version=1, published=True, rules=rules))
        db.add(
            PickupSlot(
                id=slot,
                merchant_id=merchant,
                label="Future test slot",
                location="Test",
                capacity=1,
                reserved=0,
                starts_at=now() + timedelta(hours=2),
                ends_at=now() + timedelta(hours=4),
            )
        )
        db.flush()
        for i in range(3):
            db.add(
                Order(
                    id=order_ids[i],
                    merchant_id=merchant,
                    customer_id=customer,
                    product_id=product,
                    status="draft" if i < 2 else "delivered",
                    delivery_status="not_shipped" if i < 2 else "delivered",
                    total_paise=19900,
                    paid_paise=0 if i < 2 else 19900,
                    delivered_at=now() if i == 2 else None,
                )
            )
        db.flush()
        for i in range(3):
            db.add(
                Conversation(
                    id=conv_ids[i],
                    merchant_id=merchant,
                    customer_id=customer,
                    order_id=order_ids[i],
                    channel="demo",
                )
            )
        db.flush()
        for i in range(4):
            index = i if i < 2 else 2
            case = Case(
                id=case_ids[i],
                merchant_id=merchant,
                conversation_id=conv_ids[index],
                order_id=order_ids[index],
                kind="pickup" if i < 2 else "refund",
                summary="Competing transaction",
                policy_version=1,
                seller_approved=True,
                status="investigating",
                expires_at=now() + timedelta(hours=24),
                details={
                    "slot_id": slot,
                    "slot_label": "Future test slot",
                    "confirmed_total_paise": 19900,
                }
                if i < 2
                else {"amount_paise": 15000, "reason": "defective"},
            )
            db.add(case)
            db.flush()
            issue_proposal(db, case, db.get(Order, order_ids[index]))
        db.commit()

    def race(ids):
        barrier = Barrier(2)

        def submit(cid):
            with Session(engine) as db:
                case = db.get(Case, cid)
                conv = db.get(Conversation, case.conversation_id)
                reference = case.proposal_ref
                barrier.wait(timeout=10)
                try:
                    confirm_case(db, reference, conv)
                    db.commit()
                    return "accepted"
                except HTTPException as exc:
                    db.rollback()
                    return exc.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, ids))
        assert sorted(map(str, results)) == ["409", "accepted"], results

    race(case_ids[:2])
    with Session(engine) as db:
        p = db.get(Product, product)
        s = db.get(PickupSlot, slot)
        assert (p.stock, p.reserved_stock, s.reserved) == (1, 1, 1)
    print("PASS: two competing pickups reserve exactly one stock unit and one slot.")
    race(case_ids[2:])
    with Session(engine) as db:
        order = db.get(Order, order_ids[2])
        assert pending_refunds(db, order) == 15000
        assert order.refunded_paise == 0
    print("PASS: competing refunds cannot reserve more than the paid balance.")
finally:
    with Session(engine) as db:
        for job in db.scalars(select(Job)):
            if job.payload.get("case_id") in case_ids or str(
                job.payload.get("operation_id", "")
            ).startswith("op:" + prefix):
                db.delete(job)
        for model, condition in [
            (Reservation, Reservation.case_id.in_(case_ids)),
            (Refund, Refund.case_id.in_(case_ids)),
            (Operation, Operation.merchant_id == merchant),
            (Case, Case.merchant_id == merchant),
            (Conversation, Conversation.merchant_id == merchant),
            (Order, Order.merchant_id == merchant),
            (Product, Product.merchant_id == merchant),
            (Customer, Customer.merchant_id == merchant),
            (Policy, Policy.merchant_id == merchant),
            (PickupSlot, PickupSlot.merchant_id == merchant),
            (AuditLog, AuditLog.merchant_id == merchant),
            (Merchant, Merchant.id == merchant),
        ]:
            db.execute(delete(model).where(condition))
        db.commit()
    engine.dispose()
