from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.auth import Principal, seller, owner, demo_only
from app.core.config import get_settings
from app.persistence.session import get_db
from app.persistence.models import (
    Case,
    Conversation,
    Evidence,
    Merchant,
    Order,
    Policy,
    Product,
    Message,
    Customer,
    Review,
    InsightReport,
    Operation,
    ReturnRecord,
    now,
)
from app.domain.schemas import (
    DecisionInput,
    MessageInput,
    HandoffInput,
    ProductUpdate,
    PolicyRules,
    PolicyDraftInput,
    CollectionInput,
    WorkspaceView,
    InspectionInput,
    ResolveInput,
    LinkCustomerInput,
    ReportInput,
)
from app.domain.common import audit, policy, record, reply, scoped
from app.domain.cases import flag
from app.domain.commerce import decision, pickup_action, inspect_return
from app.domain.conversations import receive, set_handoff
from app.domain.evidence import save_evidence
from app.domain.workspace import workspace, cohort, topic_insights
from app.agents.specialists import policy_draft, analyze_insights
from app.integrations.storage import MAX_BYTES, local_path, signed_url

router = APIRouter(prefix="/api", tags=["seller"])


@router.get("/workspace", response_model=WorkspaceView)
def get_workspace(
    date_from: str | None = None,
    date_to: str | None = None,
    principal: Principal = Depends(seller),
    db: Session = Depends(get_db),
):
    return workspace(db, principal.merchant_id, date_from, date_to)


@router.get("/cases/{case_id}")
def get_case(case_id: str, principal: Principal = Depends(seller), db: Session = Depends(get_db)):
    return record(scoped(db, Case, case_id, principal.merchant_id))


@router.get("/conversations/{conversation_id}/orders/{order_id}")
def get_owned_conversation_order(
    conversation_id: str, order_id: str,
    principal: Principal = Depends(seller), db: Session = Depends(get_db),
):
    from app.domain.store_tools import lookup_owned_order

    conv = scoped(db, Conversation, conversation_id, principal.merchant_id)
    _, result = lookup_owned_order(db, conv, order_id, conv.id, None)
    db.commit()
    if result is None:
        raise HTTPException(404, "Order is unavailable for this conversation")
    return result


@router.get("/conversations/{conversation_id}/orders/{order_id}/shipment")
def get_owned_shipment(
    conversation_id: str, order_id: str,
    principal: Principal = Depends(seller), db: Session = Depends(get_db),
):
    from app.domain.store_tools import lookup_shipment
    conv = scoped(db, Conversation, conversation_id, principal.merchant_id)
    result = lookup_shipment(db, conv, order_id, conv.id, None)
    db.commit()
    if result is None:
        raise HTTPException(404, "Shipment is unavailable for this conversation")
    return result


@router.post("/cases/{case_id}/decision")
def decide(
    case_id: str, data: DecisionInput, principal: Principal = Depends(owner), db: Session = Depends(get_db)
):
    item = decision(db, case_id, principal.merchant_id, principal.user_id, data)
    db.commit()
    return record(item)


@router.post("/cases/{case_id}/resolve")
def resolve(
    case_id: str, data: ResolveInput, principal: Principal = Depends(owner), db: Session = Depends(get_db)
):
    case = scoped(db, Case, case_id, principal.merchant_id, lock=True)
    if case.kind not in {"tracking", "catalog", "policy", "complaint", "unknown", "handoff", "technical", "wrong_product", "delivery_dispute", "customization_inquiry", "pickup_inquiry", "refund_inquiry", "return_inquiry", "replacement_inquiry", "redelivery_inquiry", "cancellation_inquiry", "warranty_inquiry", "checkout_inquiry"}:
        raise HTTPException(409, "Complete this case through its recorded business workflow.")
    case.seller_assisted = True
    reply(
        db,
        db.get(Conversation, case.conversation_id),
        "Store team: " + data.note,
        role="seller",
        cases=[case],
        completes=True,
    )
    audit(db, principal.merchant_id, principal.user_id, "case.seller_resolved", case.id, note=data.note)
    db.commit()
    return record(case)


@router.post("/cases/{case_id}/inspection")
def inspection(
    case_id: str, data: InspectionInput, principal: Principal = Depends(owner), db: Session = Depends(get_db)
):
    case = scoped(db, Case, case_id, principal.merchant_id, lock=True)
    inspect_return(db, case, principal.user_id, data)
    db.commit()
    return record(case)


@router.post("/evidence/{evidence_id}/verify")
def verify_photo(evidence_id: str, principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    item = scoped(db, Evidence, evidence_id, principal.merchant_id, lock=True)
    item.verified = True
    if item.case_id:
        db.get(Case, item.case_id).seller_assisted = True
    audit(
        db,
        principal.merchant_id,
        principal.user_id,
        "evidence.verified",
        item.case_id or item.id,
        evidence_id=item.id,
    )
    db.commit()
    return {"verified": True}


@router.get("/evidence/{evidence_id}/image")
def image(evidence_id: str, principal: Principal = Depends(seller), db: Session = Depends(get_db)):
    item = scoped(db, Evidence, evidence_id, principal.merchant_id)
    if get_settings().supabase_url:
        return RedirectResponse(signed_url(item.object_key), headers={"Cache-Control": "private, no-store"})
    return FileResponse(
        local_path(item.object_key), media_type=item.mime_type, headers={"Cache-Control": "private, no-store"}
    )


@router.patch("/conversations/{conversation_id}/handoff")
def handoff(
    conversation_id: str,
    data: HandoffInput,
    principal: Principal = Depends(seller),
    db: Session = Depends(get_db),
):
    conv = scoped(db, Conversation, conversation_id, principal.merchant_id, lock=True)
    set_handoff(db, conv, data.enabled, principal.user_id)
    reply(
        db,
        conv,
        "Store team is now handling this conversation."
        if data.enabled
        else "Store team has resumed AI assistance.",
        role="system",
    )
    db.commit()
    return record(conv)


@router.post("/conversations/{conversation_id}/reply")
def seller_reply(
    conversation_id: str,
    data: MessageInput,
    principal: Principal = Depends(seller),
    db: Session = Depends(get_db),
):
    conv = scoped(db, Conversation, conversation_id, principal.merchant_id, lock=True)
    duplicate = db.get(Message, data.message_id)
    if duplicate:
        if duplicate.conversation_id != conv.id or duplicate.role != "seller":
            raise HTTPException(409, "Message identifier already used")
        return record(duplicate)
    if not conv.handoff:
        raise HTTPException(409, "Take over before replying.")
    cases = list(
        db.scalars(select(Case).where(Case.conversation_id == conv.id, Case.primary_status != "resolved"))
    )
    for c in cases:
        c.seller_assisted = True
    msg = reply(db, conv, "Store team: " + data.text, role="seller", message_id=data.message_id, cases=cases)
    audit(db, principal.merchant_id, principal.user_id, "seller.replied", msg.id)
    db.commit()
    return record(msg)


@router.post("/messages/{message_id}/reconcile")
def reconcile(message_id: str, principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    from app.integrations.whatsapp import fetch_status, CapabilityUnavailable
    from app.api.webhooks import apply_delivery
    from app.domain.messaging import apply_receipts

    msg = db.get(Message, message_id)
    if not msg:
        raise HTTPException(404, "Message unavailable")
    conv = scoped(db, Conversation, msg.conversation_id, principal.merchant_id)
    if not msg.provider_id:
        raise HTTPException(
            409,
            "Provider ID is unknown. Verify this send with its messaging provider before taking further action.",
        )
    try:
        if conv.messaging_provider == "360dialog_sandbox":
            if not apply_receipts(db, msg):
                raise CapabilityUnavailable("No delivery receipt has arrived")
        else:
            apply_delivery(db, msg, fetch_status(msg.provider_id, conv.messaging_provider))
    except CapabilityUnavailable as exc:
        raise HTTPException(409, "No verified delivery receipt is available. Do not resend an uncertain message.") from exc
    except Exception as exc:
        raise HTTPException(503, "Provider status verification is unavailable") from exc
    audit(db, principal.merchant_id, principal.user_id, "message.reconciled", msg.id, status=msg.status)
    db.commit()
    return record(msg)


@router.patch("/products/{product_id}")
def update_product(
    product_id: str, data: ProductUpdate, principal: Principal = Depends(owner), db: Session = Depends(get_db)
):
    p = scoped(db, Product, product_id, principal.merchant_id, lock=True)
    if data.stock < p.reserved_stock:
        raise HTTPException(409, "Physical stock cannot be lower than reserved stock.")
    p.price_paise, p.stock = data.price_paise, data.stock
    audit(db, principal.merchant_id, principal.user_id, "product.updated", p.id, **data.model_dump())
    db.commit()
    return record(p)


def save_draft(db, principal, rules):
    db.scalar(select(Merchant).where(Merchant.id == principal.merchant_id).with_for_update())
    version = (
        db.scalar(select(func.max(Policy.version)).where(Policy.merchant_id == principal.merchant_id)) or 0
    ) + 1
    draft = Policy(merchant_id=principal.merchant_id, version=version, rules=rules, published=False)
    db.add(draft)
    db.flush()
    audit(db, principal.merchant_id, principal.user_id, "policy.draft_saved", draft.id, version=version)
    db.commit()
    return record(draft)


@router.post("/policies/drafts")
def manual_draft(data: PolicyRules, principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    return save_draft(db, principal, data.model_dump())


@router.post("/policies/draft")
def ai_draft(data: PolicyDraftInput, principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    current = db.scalar(
        select(Policy)
        .where(Policy.merchant_id == principal.merchant_id, Policy.published.is_(True))
        .order_by(Policy.version.desc())
        .limit(1)
    )
    try:
        rules = policy_draft(data.instruction, current.rules if current else PolicyRules().model_dump())
    except Exception as exc:
        raise HTTPException(503, "AI drafting is unavailable; edit the structured fields.") from exc
    return save_draft(db, principal, PolicyRules.model_validate(rules).model_dump())


@router.post("/policies/{policy_id}/publish")
def publish(policy_id: str, principal: Principal = Depends(owner), db: Session = Depends(get_db)):
    db.scalar(select(Merchant).where(Merchant.id == principal.merchant_id).with_for_update())
    draft = scoped(db, Policy, policy_id, principal.merchant_id, lock=True)
    if draft.published:
        raise HTTPException(409, "This version is already published.")
    latest = (
        db.scalar(
            select(func.max(Policy.version)).where(
                Policy.merchant_id == principal.merchant_id, Policy.published.is_(True)
            )
        )
        or 0
    )
    if draft.version < latest:
        raise HTTPException(409, "This draft is stale. Save a new draft against the current rules.")
    draft.published = True
    for case in db.scalars(
        select(Case).where(Case.merchant_id == principal.merchant_id, Case.status == "pending_customer")
    ):
        flag(db, case, "Published policy changed. Fresh terms and consent are required.")
        reply(
            db,
            db.get(Conversation, case.conversation_id),
            "The store policy changed. Your pending proposal needs a fresh review.",
            role="system",
            cases=[case],
        )
    audit(db, principal.merchant_id, principal.user_id, "policy.published", draft.id, version=draft.version)
    db.commit()
    return record(draft)


@router.post("/pickups/{reservation_id}/{action}")
def pickup(
    reservation_id: str,
    action: str,
    data: CollectionInput | None = None,
    principal: Principal = Depends(seller),
    db: Session = Depends(get_db),
):
    if action not in {"ready", "collect", "cancel"}:
        raise HTTPException(404, "Action unavailable")
    if action == "collect" and (data is None or not data.code):
        raise HTTPException(422, "Enter the customer's six-digit collection code.")
    item = pickup_action(
        db, reservation_id, principal.merchant_id, principal.user_id, action, data.code if data else None
    )
    db.commit()
    return {"status": item.status}


@router.post("/insights/analyze")
def insights(data: ReportInput, principal: Principal = Depends(seller), db: Session = Depends(get_db)):
    start, end, cases = cohort(db, principal.merchant_id, data.date_from, data.date_to)
    reviews = list(db.scalars(select(Review).where(Review.case_id.in_([c.id for c in cases]))))
    try:
        body = analyze_insights(reviews, cases)
    except Exception as exc:
        raise HTTPException(
            503, "Insight generation is unavailable. Factual metrics remain available."
        ) from exc
    item = InsightReport(
        merchant_id=principal.merchant_id,
        date_from=start.isoformat(),
        date_to=end.isoformat(),
        body=body,
        mode=get_settings().ai_mode,
    )
    db.add(item)
    db.flush()
    audit(db, principal.merchant_id, "insights", "report.generated", item.id)
    db.commit()
    return record(item)


@router.post("/customers/link")
def link_customer(
    data: LinkCustomerInput, principal: Principal = Depends(owner), db: Session = Depends(get_db)
):
    target = scoped(db, Customer, data.customer_id, principal.merchant_id, lock=True)
    existing = db.scalar(
        select(Customer)
        .where(Customer.merchant_id == principal.merchant_id, Customer.phone == data.phone)
        .with_for_update()
    )
    if existing and existing.id != target.id:
        if db.scalar(select(Order.id).where(Order.customer_id == existing.id)):
            raise HTTPException(409, "That phone already owns order records.")
        for conv in db.scalars(select(Conversation).where(Conversation.customer_id == existing.id)):
            conv.customer_id = target.id
        db.delete(existing)
        db.flush()
    target.phone = data.phone
    audit(db, principal.merchant_id, principal.user_id, "customer.identity_linked", target.id)
    db.commit()
    return {"linked": True}


# Authenticated fixture endpoints are used by automated tests/CLI, never the seller UI.
@router.post("/demo/conversations/{conversation_id}/messages")
def fixture_message(
    conversation_id: str,
    data: MessageInput,
    principal: Principal = Depends(demo_only),
    db: Session = Depends(get_db),
):
    conv = scoped(db, Conversation, conversation_id, principal.merchant_id, lock=True)
    if conv.channel != "demo":
        raise HTTPException(403, "Fixture endpoint only accepts synthetic conversations.")
    result = receive(db, conv, data.text, data.message_id)
    db.commit()
    return result


@router.post("/demo/conversations/{conversation_id}/evidence")
async def fixture_photo(
    conversation_id: str,
    file: UploadFile,
    principal: Principal = Depends(demo_only),
    db: Session = Depends(get_db),
):
    conv = scoped(db, Conversation, conversation_id, principal.merchant_id, lock=True)
    if conv.channel != "demo":
        raise HTTPException(403, "Fixture endpoint only accepts synthetic conversations.")
    item = save_evidence(db, conv, await file.read(MAX_BYTES + 1), file.filename or "photo.jpg")
    db.commit()
    return {k: v for k, v in record(item).items() if k != "object_key"}
