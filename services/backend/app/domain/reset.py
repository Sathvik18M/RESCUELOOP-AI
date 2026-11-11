"""Explicit, store-scoped synthetic reset. Stop API and worker before invoking."""

from datetime import timedelta
from sqlalchemy import select, delete, text, inspect
from app.core.config import get_settings
from app.persistence.models import (
    Merchant,
    Membership,
    Customer,
    Product,
    Order,
    Policy,
    Conversation,
    Message,
    Case,
    Reservation,
    Refund,
    PickupSlot,
    Evidence,
    Review,
    AuditLog,
    Operation,
    ReturnRecord,
    InsightReport,
    Job,
    ServiceState,
    DeliveryReceipt,
    now,
)
from app.domain.common import utc, audit
from app.integrations.storage import delete_store_evidence


def reset_demo(db, merchant_id, confirmation):
    s = get_settings()
    if (
        not s.demo_mode
        or s.app_env == "production"
        or merchant_id != "SELLER001"
        or confirmation != merchant_id
    ):
        raise ValueError(
            "Reset requires DEMO_MODE=true, the seeded SELLER001 store and matching --confirm-store."
        )
    merchant = db.scalar(select(Merchant).where(Merchant.id == merchant_id).with_for_update())
    if not merchant:
        raise ValueError("Seeded store does not exist.")
    seeded = db.scalar(
        select(AuditLog).where(AuditLog.merchant_id == merchant_id, AuditLog.action == "demo.seeded")
    )
    if not seeded or not seeded.detail.get("synthetic"):
        raise ValueError("Refusing to reset a store without synthetic seed provenance.")
    worker = db.get(ServiceState, "worker")
    if worker and now() - utc(worker.updated_at) < timedelta(seconds=30):
        raise ValueError("Stop the API and worker, then wait 30 seconds before resetting.")
    conv_ids = list(db.scalars(select(Conversation.id).where(Conversation.merchant_id == merchant_id)))
    case_ids = list(db.scalars(select(Case.id).where(Case.merchant_id == merchant_id)))
    order_ids = list(db.scalars(select(Order.id).where(Order.merchant_id == merchant_id)))
    msg_ids = list(db.scalars(select(Message.id).where(Message.conversation_id.in_(conv_ids))))
    op_ids = list(db.scalars(select(Operation.id).where(Operation.merchant_id == merchant_id)))
    jobs = [
        j
        for j in db.scalars(select(Job))
        if j.payload.get("conversation_id") in conv_ids
        or j.payload.get("message_id") in msg_ids
        or j.payload.get("case_id") in case_ids
        or j.payload.get("operation_id") in op_ids
    ]
    if any(j.status == "processing" and j.locked_until and utc(j.locked_until) > now() for j in jobs):
        raise ValueError(
            "An operation still holds a lease. Stop its worker and let the lease expire before reset."
        )
    # Delete objects before their references. A storage failure aborts DB removal and can be retried.
    delete_store_evidence(merchant_id)
    if db.bind.dialect.name == "postgresql":
        inspector = inspect(db.connection())
        if inspector.has_schema("rescueloop_agents"):
            for table in ["checkpoint_writes", "checkpoint_blobs", "checkpoints"]:
                if inspector.has_table(table, schema="rescueloop_agents"):
                    for cid in conv_ids:
                        db.execute(
                            text(
                                f"DELETE FROM rescueloop_agents.{table} WHERE left(thread_id,length(:prefix))=:prefix"
                            ),
                            {"prefix": cid + ":"},
                        )
    for job in jobs:
        db.delete(job)
    for model, condition in [
        (DeliveryReceipt, DeliveryReceipt.merchant_id == merchant_id),
        (Refund, Refund.order_id.in_(order_ids)),
        (Reservation, Reservation.order_id.in_(order_ids)),
        (ReturnRecord, ReturnRecord.merchant_id == merchant_id),
        (Operation, Operation.merchant_id == merchant_id),
        (Evidence, Evidence.merchant_id == merchant_id),
        (Review, Review.merchant_id == merchant_id),
        (Message, Message.conversation_id.in_(conv_ids)),
        (Case, Case.merchant_id == merchant_id),
        (Conversation, Conversation.merchant_id == merchant_id),
        (Order, Order.merchant_id == merchant_id),
        (Product, Product.merchant_id == merchant_id),
        (Customer, Customer.merchant_id == merchant_id),
        (PickupSlot, PickupSlot.merchant_id == merchant_id),
        (Policy, Policy.merchant_id == merchant_id),
        (InsightReport, InsightReport.merchant_id == merchant_id),
        (Membership, Membership.merchant_id == merchant_id),
        (AuditLog, AuditLog.merchant_id == merchant_id),
    ]:
        db.execute(delete(model).where(condition))
    db.delete(merchant)
    audit(
        db,
        merchant_id,
        "local-operator",
        "demo.reset",
        merchant_id,
        removed_cases=len(case_ids),
        private_evidence_removed=True,
    )
    db.commit()
