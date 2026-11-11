import pytest
from sqlalchemy import func, select

from app.agents.workflows import wrong_item
from app.core.config import get_settings
from app.domain.conversations import receive
from app.persistence.models import AuditLog, Case, Conversation, Message, Operation, Order, Policy

TEXT = "I ordered wireless headphones under order ORD1042, but I received a Bluetooth speaker instead. I want a replacement."


def run(db, text=TEXT, mid="wrong-item-one", conv_id="CONV001"):
    conv = db.get(Conversation, conv_id)
    result = receive(db, conv, text, mid)
    db.flush()
    return result, db.get(Case, result["case_ids"][0])


@pytest.mark.parametrize("delivery", ["FAILED_ATTEMPT", "failed_attempt", "out_for_delivery"])
def test_received_item_conflicts_with_delivery_and_never_repeats_known_questions(db, delivery):
    order = db.get(Order, "ORD1042")
    order.delivery_status = delivery
    order.delivered_at = None
    before = db.scalar(select(func.count()).select_from(Operation))
    result, case = run(db)
    assert case.order_id == "ORD1042"
    assert case.details["ordered_product"] == "wireless headphones"
    assert case.details["received_product"] == "Bluetooth speaker"
    assert case.details["requested_resolution"] == "replacement"
    assert case.details["complaint_type"] == "wrong_item"
    assert case.details["delivery_discrepancy"]
    assert case.details["ordered_product_comparison"] == "consistent"
    assert case.primary_status == "flagged" and case.status == "pending_verification"
    assert case.details["missing_details"] == []
    assert "Please provide" not in result["reply"] and "describe" not in result["reply"]
    assert "PENDING_VERIFICATION" in result["reply"] and delivery.upper() in result["reply"]
    assert "wireless headphones" in result["reply"] and "Bluetooth speaker" in result["reply"]
    assert order.delivery_status == delivery
    assert case.resolution_attempts == 0
    assert db.scalar(select(func.count()).select_from(Operation)) == before
    actions = {a.action for a in db.scalars(select(AuditLog).where(AuditLog.entity_id == case.id))}
    assert {
        "tool.resolution_extract_requested",
        "tool.resolution_extract_completed",
        "tool.order_lookup",
        "tool.replacement_policy_lookup",
        "case.complaint_updated",
        "case.escalated",
        "case.transition",
        "resolution.reply_composed",
    } <= actions


def test_delivered_order_is_not_changed_or_falsely_reported_as_failed(db):
    result, case = run(db)
    assert case.details["verified_order"]["delivery_status"] == "delivered"
    assert not case.details["delivery_discrepancy"]
    assert "FAILED_ATTEMPT" not in result["reply"]
    assert case.status == "pending_verification"  # Existing photo rule still needs review.


def test_history_supplies_products_and_distinct_repeats_reuse_same_case(db):
    initial = TEXT.split(" I want")[0]
    _, first = run(db, initial)
    first.resolution_attempts = 1
    result, second = run(db, "I want a replacement.", "wrong-item-two")
    assert second.id == first.id
    assert second.details["ordered_product"] == "wireless headphones"
    assert second.details["received_product"] == "Bluetooth speaker"
    assert second.details["requested_resolution"] == "replacement"
    assert not second.details["missing_details"]
    assert "Please provide" not in result["reply"]
    result, third = run(db, TEXT, "wrong-item-three")
    assert third.id == first.id and third.resolution_attempts == 1
    assert (
        db.scalar(
            select(func.count())
            .select_from(Case)
            .where(Case.conversation_id == "CONV001", Case.kind == "wrong_product")
        )
        == 1
    )
    count = db.scalar(select(func.count()).select_from(Message))
    duplicate = receive(db, db.get(Conversation, "CONV001"), TEXT, "wrong-item-three")
    assert duplicate["duplicate"] and db.scalar(select(func.count()).select_from(Message)) == count


def test_unverified_customer_never_receives_stored_order_data(db):
    result, case = run(db, conv_id="CONV002")
    assert case.order_id is None and "verified_order" not in case.details
    assert "Studio Wireless Headphones" not in result["reply"]
    assert "DELIVERED" not in result["reply"]
    assert case.status == "pending_verification"
    audit = db.scalar(
        select(AuditLog).where(AuditLog.entity_id == case.id, AuditLog.action == "tool.order_lookup")
    )
    assert audit.detail["ownership_verified"] is False and audit.detail["result"] is None


def test_store_api_shares_ownership_guard_and_audits_reads(client, auth, db):
    good = client.get("/api/conversations/CONV001/orders/ORD1042", headers=auth)
    assert good.status_code == 200 and good.json()["product_name"] == "Studio Wireless Headphones"
    assert client.get("/api/conversations/CONV002/orders/ORD1042", headers=auth).status_code == 404
    assert client.get("/api/conversations/CONV001/orders/ORD1042").status_code == 401


def test_policy_restriction_is_checked_without_authorizing_a_replacement(db):
    policy = db.get(Policy, "POLICY001")
    policy.rules = {**policy.rules, "replacement_permission": "unavailable"}
    _, case = run(db)
    assert case.details["replacement_policy_check"]["replacement_permission"] == "unavailable"
    assert "unavailable" in case.flag_reason
    assert not case.seller_approved and case.proposal_ref is None


def test_mismatched_order_description_is_audited_for_verification(db):
    _, case = run(db, TEXT.replace("wireless headphones", "a red jacket"))
    assert case.details["ordered_product_comparison"] == "needs_seller_verification"
    assert "differs from the store order" in case.flag_reason


def test_hallucinated_extraction_is_rejected(monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_mode", "groq")
    monkeypatch.setattr(
        wrong_item,
        "generate",
        lambda model, **kw: model(
            order_id=None,
            ordered_product={"value": "laptop", "message_id": "m"},
            received_product=None,
            complaint_type="wrong_item",
            requested_resolution=None,
            resolution_message_id=None,
        ),
    )
    with pytest.raises(ValueError, match="exact customer statement"):
        wrong_item.extract_facts([{"id": "m", "text": TEXT}])


def test_explicit_resolution_is_retained_even_if_model_omits_it(monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_mode", "groq")
    monkeypatch.setattr(
        wrong_item,
        "generate",
        lambda model, **kw: model(
            order_id=None,
            ordered_product=None,
            received_product=None,
            complaint_type="wrong_item",
            requested_resolution=None,
            resolution_message_id=None,
        ),
    )
    facts = wrong_item.extract_facts([{"id": "m", "text": TEXT}])
    assert facts.requested_resolution == "replacement" and facts.resolution_message_id == "m"
    assert facts.ordered_product.value == "wireless headphones"
    assert facts.received_product.value == "Bluetooth speaker"
    assert facts.order_id.value == "ORD1042"


def test_live_model_omissions_never_make_known_products_a_customer_question(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_mode", "groq")
    monkeypatch.setattr(
        wrong_item,
        "generate",
        lambda model, **kw: model(
            order_id=None,
            ordered_product=None,
            received_product=None,
            complaint_type="wrong_item",
            requested_resolution=None,
            resolution_message_id=None,
        ),
    )
    result, case = run(db)
    assert case.details["missing_details"] == []
    assert "Please provide" not in result["reply"]
    assert "wireless headphones" in result["reply"] and "Bluetooth speaker" in result["reply"]
