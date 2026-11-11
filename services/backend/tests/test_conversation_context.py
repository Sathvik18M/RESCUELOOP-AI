from datetime import timedelta

from sqlalchemy import func, select

from app.agents.router import classify_many
from app.domain.cases import support_case, transition
from app.domain.conversations import receive
from app.persistence.models import AuditLog, Case, Conversation, Message, Operation, Order, ShipmentEvent, now


def send(db, text, mid, conv_id="CONV001"):
    conv = db.get(Conversation, conv_id)
    result = receive(db, conv, text, mid)
    db.flush()
    replies = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id, Message.role != "customer")
            .order_by(Message.created_at, Message.id)
        )
    )
    return result, replies[-1].body, conv


def test_plain_status_is_not_a_tracking_dispute(db):
    _, answer, conv = send(db, "Status of the order", "status-001")
    case = db.get(Case, conv.context["active_case_id"])
    assert case.kind == "tracking"
    assert "incorrect" not in answer and "DELIVERED" in answer
    assert "no shipment event history" in answer
    assert conv.context["active_order_id"] == "ORD1042"


def test_nonreceipt_then_location_reuses_dispute_and_does_not_invent_proof(db):
    _, first, conv = send(db, "Order not yet delivered expected delivery date", "dispute-001")
    cid = conv.context["active_case_id"]
    assert "PENDING_VERIFICATION" in first and "date is not available" in first
    _, second, _ = send(db, "I have not received", "dispute-002")
    assert conv.context["active_case_id"] == cid
    _, third, _ = send(db, "I need you to tell the location where the order was delivered", "dispute-003")
    assert conv.context["active_case_id"] == cid
    assert "No delivery location" in third and "No proof of delivery" in third
    assert "multiple" not in second and "Please include" not in second
    case = db.get(Case, cid)
    assert case.kind == "delivery_dispute" and case.status == "pending_verification"
    assert case.details["verified_store_facts"]["proof_of_delivery"] is None
    assert case.details["suggested_action"] and case.resolution_attempts == 0
    before = db.scalar(select(func.count()).select_from(Message))
    result, _, _ = send(db, "I have not received", "dispute-002")
    assert result["duplicate"] and db.scalar(select(func.count()).select_from(Message)) == before
    assert db.scalar(select(func.count()).select_from(Case).where(Case.kind == "delivery_dispute")) == 1
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.entity_id == cid)))
    assert {"tool.order_lookup", "tool.shipment_lookup", "case.escalated", "case.delivery_checked"} <= actions


def test_conflicting_shipment_status_is_flagged_without_overwriting_order(db):
    order = db.get(Order, "ORD1042")
    before = (order.status, order.delivery_status, order.delivered_at)
    db.add(
        ShipmentEvent(
            merchant_id="SELLER001",
            order_id=order.id,
            status="failed_attempt",
            occurred_at=now(),
            source="test_courier",
        )
    )
    _, answer, conv = send(db, "Status of the order", "conflict-001")
    case = db.get(Case, conv.context["active_case_id"])
    assert case.status == "pending_verification" and case.kind == "delivery_dispute"
    assert "sources conflict" in answer
    assert "failed_attempt" in case.details["conflicting_evidence"][0]
    assert (order.status, order.delivery_status, order.delivered_at) == before


def test_failed_attempt_followed_by_delivered_event_is_valid_history(db):
    for offset, status in [(2, "failed_attempt"), (1, "delivered")]:
        db.add(
            ShipmentEvent(
                merchant_id="SELLER001",
                order_id="ORD1042",
                status=status,
                occurred_at=now() - timedelta(days=offset),
                source="test_courier",
                location="Reception" if status == "delivered" else None,
                proof={"reference": "proof-42"} if status == "delivered" else {},
            )
        )
    _, answer, conv = send(db, "Where was my order delivered?", "proof-001")
    case = db.get(Case, conv.context["active_case_id"])
    assert not case.details["conflicting_evidence"]
    assert "Reception" in answer and "evidence is available" in answer
    assert case.status == "pending_verification"  # proof still requires seller review


def test_customization_on_delivered_order_checks_before_mutation(db, monkeypatch):
    from app.domain import customization_intake

    monkeypatch.setattr(
        customization_intake,
        "configure_request",
        lambda *a: (_ for _ in ()).throw(AssertionError("must not mutate")),
    )
    before = db.scalar(select(func.count()).select_from(Operation))
    _, answer, conv = send(db, "Can I get my order customized", "custom-blocked")
    case = db.get(Case, conv.context["active_case_id"])
    assert case.kind == "customization_inquiry" and case.status == "pending_verification"
    assert "can't submit" in answer and "request has been saved" not in answer
    assert not case.proposal_ref and not case.seller_approved
    assert db.scalar(select(func.count()).select_from(Operation)) == before
    assert db.get(Order, "ORD1042").customizations == []


def test_customization_collects_only_missing_name_then_submits(db):
    # Independent draft order with no pre-existing customization request.
    order = Order(
        id="ORD2043",
        merchant_id="SELLER001",
        customer_id="CUS001",
        product_id="WALLET001",
        status="draft",
        delivery_status="not_shipped",
        total_paise=79900,
    )
    db.add(order)
    db.flush()
    _, answer, conv = send(db, "Can you engrave my name on ORD2043?", "custom-intake")
    cid = conv.context["active_case_id"]
    assert "exact engraving text" in answer
    assert db.get(Case, cid).kind == "customization_inquiry"
    assert conv.context["pending_questions"]
    # There are unrelated waiting cases; the clear active follow-up must win.
    unrelated = support_case(db, conv, "redelivery", "Another inquiry", order_id="ORD1042")
    transition(db, unrelated, "ongoing", "needs_customer_details")
    _, answer, _ = send(db, "Ravi", "custom-name")
    case = db.get(Case, cid)
    assert case.kind == "customization" and case.details["engraving"] == "Ravi"
    assert case.status == "pending_seller" and not case.proposal_ref
    assert "exact engraving text" not in answer and "More than one" not in answer
    assert case.id == conv.context["active_case_id"]
    assert order.customizations == []  # No seller approval/customer consent yet.


def test_product_rules_checked_before_customization_request(db):
    order = db.get(Order, "ORD1042")
    order.status = "draft"
    _, answer, conv = send(db, "Engrave Ravi on ORD1042", "custom-option")
    assert "not listed as an available option" in answer
    assert db.get(Case, conv.context["active_case_id"]).kind == "customization_inquiry"


def test_greeting_does_not_answer_an_unrelated_pending_question(db):
    _, _, conv = send(db, "I have not received", "greet-dispute")
    cid = conv.context["active_case_id"]
    _, answer, _ = send(db, "Hi", "greeting")
    assert answer.startswith("Hello") and "More than one" not in answer
    assert conv.context["active_case_id"] == cid


def test_multi_intent_keeps_wrong_item_facts_and_separate_status(db):
    result, _, conv = send(
        db,
        "I ordered wireless headphones under order ORD1042, but I received a Bluetooth speaker instead. I want a replacement; status of the order",
        "multi-001",
    )
    cases = [db.get(Case, cid) for cid in result["case_ids"]]
    assert {c.kind for c in cases} == {"wrong_product", "tracking"}
    wrong = next(c for c in cases if c.kind == "wrong_product")
    assert (
        wrong.details["received_product"] == "Bluetooth speaker"
        and wrong.details["requested_resolution"] == "replacement"
    )
    assert not wrong.details["missing_details"]
    assert wrong.id in conv.context["known_customer_facts"]


def test_structured_routing_distinguishes_supported_actions():
    for text, intent in [
        ("Status of the order", "tracking"),
        ("I have not received", "delivery_dispute"),
        ("I need human support", "handoff"),
        ("I want a refund", "refund"),
        ("I want a return", "return"),
        ("I want a replacement", "replacement"),
    ]:
        proposal = classify_many(text, "{}")[0]
        assert proposal["intent"] == intent
        assert "missing_fields" in proposal and proposal["requested_action"]


def test_shipment_api_cannot_expose_another_customers_proof(db, client, auth):
    db.add(
        ShipmentEvent(
            merchant_id="SELLER001",
            order_id="ORD1042",
            status="delivered",
            occurred_at=now(),
            source="test",
            location="Private location",
            proof={"reference": "private"},
        )
    )
    db.flush()
    response = client.get("/api/conversations/CONV002/orders/ORD1042/shipment", headers=auth)
    assert response.status_code == 404 and "Private location" not in response.text


def test_ineligible_pickup_does_not_create_an_actionable_request(db):
    conv = db.get(Conversation, "CONV001")
    previous = support_case(db, conv, "pickup", "Earlier blocked pickup", order_id="ORD1042")
    _, answer, conv = send(db, "Can I collect my order from your shop?", "pickup-blocked")
    case = db.get(Case, conv.context["active_case_id"])
    assert case.id == previous.id
    assert case.kind == "pickup_inquiry" and case.status == "pending_verification"
    assert "can't submit" in answer and not case.proposal_ref
    assert not conv.context["last_completed_actions"]


def test_genuinely_ambiguous_followup_names_only_matching_cases(db):
    conv = db.get(Conversation, "CONV001")
    for kind in ("return", "refund"):
        case = support_case(db, conv, kind, "Needs customer details", order_id="ORD1042", reuse=False)
        transition(db, case, "ongoing", "needs_customer_details")
    conv.context = {"active_case_id": "CASE1042", "active_order_id": "ORD1042"}
    _, answer, _ = send(db, "Here is the additional detail", "ambiguous-001")
    assert "Which request" in answer and "return for ORD1042" in answer and "refund for ORD1042" in answer


def test_automatic_wrong_item_reply_is_held_by_seller_takeover(db):
    from app.domain.conversations import set_handoff
    conv = db.get(Conversation, "CONV001")
    conv.channel = "whatsapp"
    send(db, "I ordered wireless headphones under order ORD1042, but received a speaker instead. I want a replacement.", "handoff-queued")
    set_handoff(db, conv, True, "test-seller")
    out = db.scalar(select(Message).where(Message.conversation_id == conv.id,
        Message.status == "held_for_seller"))
    assert out and out.role == "assistant"
