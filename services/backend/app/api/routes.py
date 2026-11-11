import hashlib
import secrets
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.auth import Principal, seller, owner, demo_only
from app.core.config import get_settings
from app.db.session import get_db
from app.db.models import (
    Case,
    Conversation,
    Evidence,
    Merchant,
    Order,
    Policy,
    Product,
    PickupSlot,
    Reservation,
    now,
)
from app.modules.schemas import (
    DecisionInput,
    MessageInput,
    HandoffInput,
    ProductUpdate,
    PolicyRules,
    PolicyDraftInput,
    SettingsInput,
    CollectionInput,
    WorkspaceView,
)
from app.modules.common import audit, policy, record, reply, scoped
from app.modules.commerce import decision
from app.modules.conversations import receive
from app.modules.evidence import save_evidence
from app.modules.workspace import workspace
from app.agents.specialists import policy_draft
from app.integrations.storage import MAX_BYTES, local_path, signed_url

router = APIRouter(prefix="/api", tags=["seller"])


@router.post("/insights/analyze")
def analyze_feedback(principal: Principal = Depends(seller), db: Session = Depends(get_db)):
    from app.agents.specialists import analyze_insights
    from app.db.models import Review

    merchant = db.get(Merchant, principal.merchant_id)
    reviews = list(db.scalars(select(Review).where(Review.merchant_id == principal.merchant_id)))
    cases = list(db.scalars(select(Case).where(Case.merchant_id == principal.merchant_id)))
    try:
        report = analyze_insights(reviews, cases)
    except Exception as exc:
        raise HTTPException(503, "Insights analysis is unavailable. Source counts remain available.") from exc
    merchant.settings = {
        **merchant.settings,
        "insight_report": {**report, "generated_at": now().isoformat(), "mode": get_settings().ai_mode},
    }
    audit(db, principal.merchant_id, "insights", "insights.generated", merchant.id)
    db.commit()
    return report


@router.get("/workspace", response_model=WorkspaceView)
def get_workspace(principal: Principal = Depends(seller), db: Session = Depends(get_db)):
    return workspace(db, principal.merchant_id)


@router.get("/orders/{order_id}")
def get_order(order_id: str, principal: Principal = Depends(seller), db: Session = Depends(get_db)):
    return record(scoped(db, Order, order_id, principal.merchant_id))


@router.get("/products")
def get_products(principal: Principal = Depends(seller), db: Session = Depends(get_db)):
    return [
        record(p) for p in db.scalars(select(Product).where(Product.merchant_id == principal.merchant_id))
    ]


@router.patch("/products/{product_id}")
def update_product(
    product_id: str, data: ProductUpdate, principal: Principal = Depends(owner), db: Session = Depends(get_db)
):
    product = scoped(db, Product, product_id, principal.merchant_id, lock=True)
    product.price_paise, product.stock = data.price_paise, data.stock
    audit(db, principal.merchant_id, principal.user_id, "product.updated", product.id, **data.model_dump())
    db.commit()
    return record(product)


@router.post("/cases/{case_id}/decision")
def decide(
    case_id: str, data: DecisionInput, principal: Principal = Depends(owner), db: Session = Depends(get_db)
):
    case = decision(db, case_id, principal.merchant_id, principal.user_id, data)
    db.commit()
    return record(case)


@router.patch("/conversations/{conversation_id}/handoff")
def handoff(
    conversation_id: str,
    data: HandoffInput,
    principal: Principal = Depends(seller),
    db: Session = Depends(get_db),
):
    conv = scoped(db, Conversation, conversation_id, principal.merchant_id, lock=True)
    conv.handoff = data.enabled
    audit(db, principal.merchant_id, principal.user_id, "conversation.handoff", conv.id, enabled=data.enabled)
    db.commit()
    return record(conv)


@router.post("/conversations/{conversation_id}/reply")
def seller_reply(
    conversation_id: str,
    data: MessageInput,
    principal: Principal = Depends(seller),
    db: Session = Depends(get_db),
):
    from app.db.models import Message

    conv = scoped(db, Conversation, conversation_id, principal.merchant_id, lock=True)
    # Scope idempotency to this conversation and actor role.
    duplicate = db.get(Message, data.message_id)
    if duplicate:
        if duplicate.conversation_id != conv.id or duplicate.role != "seller":
            raise HTTPException(409, "Message identifier already used")
        return record(duplicate)
    if not conv.handoff:
        raise HTTPException(409, "Take over the conversation before replying")
    msg = reply(db, conv, data.text, role="seller", message_id=data.message_id)
    audit(db, principal.merchant_id, principal.user_id, "seller.replied", msg.id)
    db.commit()
    return record(msg)


@router.post("/demo/conversations/{conversation_id}/messages")
def demo_message(
    conversation_id: str,
    data: MessageInput,
    principal: Principal = Depends(demo_only),
    db: Session = Depends(get_db),
):
    conv = scoped(db, Conversation, conversation_id, principal.merchant_id, lock=True)
    if conv.channel != "demo":
        raise HTTPException(403, "The simulator only accepts demo conversations")
    result = receive(db, conv, data.text, data.message_id)
    db.commit()
    return result


@router.post("/demo/scenarios/delivered")
def delivered(principal: Principal = Depends(demo_only), db: Session = Depends(get_db)):
    order = scoped(db, Order, "ORD1042", principal.merchant_id, lock=True)
    if order.refunded_paise or order.status in {"return_requested", "replacement_requested", "cancelled"}:
        raise HTTPException(409, "Use a fresh demo database before restarting this scenario")
    order.status = "delivered"
    order.delivery_status = "delivered"
    order.delivered_at = now() - timedelta(days=1)
    audit(db, principal.merchant_id, principal.user_id, "demo.scenario.delivered", order.id)
    db.commit()
    return record(order)


@router.post("/demo/conversations/{conversation_id}/evidence")
async def evidence_upload(
    conversation_id: str,
    file: UploadFile,
    principal: Principal = Depends(demo_only),
    db: Session = Depends(get_db),
):
    conv = scoped(db, Conversation, conversation_id, principal.merchant_id, lock=True)
    if conv.channel != "demo":
        raise HTTPException(403, "Demo uploads require a demo conversation")
    raw = await file.read(MAX_BYTES + 1)
    item = save_evidence(db, conv, raw, file.filename or "photo.jpg")
    db.commit()
    return {key: value for key, value in record(item).items() if key != "object_key"}


@router.get("/evidence/{evidence_id}/image")
def evidence_image(evidence_id: str, principal: Principal = Depends(seller), db: Session = Depends(get_db)):
    item = scoped(db, Evidence, evidence_id, principal.merchant_id)
    if get_settings().supabase_url:
        return RedirectResponse(signed_url(item.object_key))
    return FileResponse(
        local_path(item.object_key), media_type=item.mime_type, headers={"Cache-Control": "private, no-store"}
    )


@router.get("/policies")
def get_policy(principal: Principal = Depends(seller), db: Session = Depends(get_db)):
    return record(policy(db, principal.merchant_id))


@router.post("/policies/draft")
def draft_policy(
    data: PolicyDraftInput, principal: Principal = Depends(owner), db: Session = Depends(get_db)
):
    try:
        rules = policy_draft(data.instruction, policy(db, principal.merchant_id).rules)
    except Exception as exc:
        raise HTTPException(503, "Policy drafting is unavailable; use the editable rule fields") from exc
    return {"rules": rules, "published": False}


@router.post("/policies/publish")
def publish_policy(data: PolicyRules, principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    db.scalar(select(Merchant).where(Merchant.id == principal.merchant_id).with_for_update())
    current = policy(db, principal.merchant_id)
    new = Policy(
        merchant_id=principal.merchant_id,
        version=current.version + 1,
        rules=data.model_dump(),
        published=True,
    )
    db.add(new)
    for case in db.scalars(
        select(Case).where(
            Case.merchant_id == principal.merchant_id,
            Case.status.in_(["pending_seller", "pending_customer", "needs_details"]),
        )
    ):
        case.status = "expired"
        reply(
            db,
            db.get(Conversation, case.conversation_id),
            "The store updated its policy. Please submit your pending request again so we can check the new rules.",
        )
    audit(db, principal.merchant_id, principal.user_id, "policy.published", str(new.version))
    db.commit()
    return record(new)


@router.post("/pickups/{reservation_id}/ready")
def pickup_ready(reservation_id: str, principal: Principal = Depends(seller), db: Session = Depends(get_db)):
    reservation = db.scalar(
        select(Reservation)
        .join(Order)
        .where(Reservation.id == reservation_id, Order.merchant_id == principal.merchant_id)
        .with_for_update()
    )
    if not reservation:
        raise HTTPException(404, "Reservation not found")
    if reservation.status != "reserved":
        raise HTTPException(409, "Only reserved pickups can be marked ready")
    reservation.status = "ready"
    case = db.get(Case, reservation.case_id)
    reply(
        db,
        db.get(Conversation, case.conversation_id),
        "Your order is ready for pickup. Bring your collection code to the store.",
    )
    audit(db, principal.merchant_id, principal.user_id, "pickup.ready", reservation.id)
    db.commit()
    return {"status": reservation.status}


@router.post("/pickups/{reservation_id}/collect")
def collect(
    reservation_id: str,
    data: CollectionInput,
    principal: Principal = Depends(seller),
    db: Session = Depends(get_db),
):
    reservation = db.scalar(
        select(Reservation)
        .join(Order)
        .where(Reservation.id == reservation_id, Order.merchant_id == principal.merchant_id)
        .with_for_update()
    )
    if not reservation:
        raise HTTPException(404, "Reservation not found")
    if reservation.status != "ready" or reservation.attempts >= 5:
        raise HTTPException(409, "Pickup must be ready and collection-code attempts must remain")
    if not secrets.compare_digest(reservation.code_hash, hashlib.sha256(data.code.encode()).hexdigest()):
        reservation.attempts += 1
        db.commit()
        raise HTTPException(422, "Incorrect collection code")
    reservation.status = "collected"
    order = scoped(db, Order, reservation.order_id, principal.merchant_id, lock=True)
    order.status = "delivered"
    order.delivery_status = "delivered"
    order.delivered_at = now()
    order.paid_paise = order.total_paise  # Demo collection records a simulated payment only.
    slot = scoped(db, PickupSlot, reservation.slot_id, principal.merchant_id, lock=True)
    slot.reserved = max(0, slot.reserved - 1)
    case = db.get(Case, reservation.case_id)
    reply(
        db,
        db.get(Conversation, case.conversation_id),
        "Your pickup is complete. We'd love your feedback—reply with a rating from 1 to 5 stars.",
    )
    audit(db, principal.merchant_id, principal.user_id, "pickup.collected", reservation.id)
    db.commit()
    return {"status": reservation.status}


@router.patch("/settings")
def settings_update(
    data: SettingsInput, principal: Principal = Depends(owner), db: Session = Depends(get_db)
):
    merchant = db.get(Merchant, principal.merchant_id)
    merchant.name = data.name
    merchant.settings = {**merchant.settings, "location": data.location, "support_email": data.support_email}
    audit(db, principal.merchant_id, principal.user_id, "settings.updated", merchant.id)
    db.commit()
    return record(merchant)
