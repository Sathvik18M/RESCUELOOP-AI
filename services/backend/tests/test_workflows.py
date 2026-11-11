from uuid import uuid4
from datetime import timedelta
import re
import pytest
from sqlalchemy import select
from app.persistence.models import (
    Case,
    Order,
    Product,
    Conversation,
    Message,
    Job,
    Operation,
    Refund,
    Reservation,
    Policy,
    Evidence,
    Review,
    ReturnRecord,
    AuditLog,
    now,
)
from app.domain.common import reply, utc
from app.domain.schemas import DecisionInput
from app.domain.commerce import decision, confirm_case, complete_operation
from app.workers.worker import execute_job, fail_job, permanent
from app.core.config import get_settings


def send(client, auth, text, conv="CONV002", message_id=None):
    r = client.post(
        f"/api/demo/conversations/{conv}/messages",
        headers=auth,
        json={"text": text, "message_id": message_id or str(uuid4())},
    )
    assert r.status_code == 200, r.text
    return r.json()


def approve(client, auth, cid, **extra):
    r = client.post(
        f"/api/cases/{cid}/decision",
        headers=auth,
        json={"decision": "approve", "quote_paise": 19900, **extra},
    )
    assert r.status_code == 200, r.text
    return r.json()


def latest(db, kind):
    return db.scalar(select(Case).where(Case.kind == kind).order_by(Case.created_at.desc()))


def complete(db):
    for job in list(db.scalars(select(Job).where(Job.kind == "operation", Job.status == "pending"))):
        execute_job(db, job)
    db.commit()


def accepted_wallet(client, auth, db):
    c = approve(client, auth, "CASE1043")
    send(client, auth, "CONFIRM " + c["proposal_ref"])
    return db.get(Order, "ORD1043")


def pickup(client, auth, db):
    accepted_wallet(client, auth, db)
    send(client, auth, "Can I collect the wallet tomorrow afternoon?")
    case = latest(db, "pickup")
    approve(client, auth, case.id)
    result = send(client, auth, "CONFIRM " + case.proposal_ref)
    code = re.search(r"Collection code: (\d{6})", result["reply"]).group(1)
    return case, db.scalar(select(Reservation).where(Reservation.case_id == case.id)), code


def test_seed_distribution(client, auth, db):
    # Check the full seeded cohort even near midnight, when its oldest row can
    # precede the default calendar-day window by one hour.
    data = client.get(
        "/api/workspace", headers=auth,
        params={"date_from": (now() - timedelta(days=14)).date().isoformat()},
    ).json()
    assert {k: data["metrics"][k] for k in ["total", "resolved", "ongoing", "flagged"]} == {
        "total": 12,
        "resolved": 6,
        "ongoing": 4,
        "flagged": 2,
    }
    assert data["metrics"]["resolution_rate"] == 50
    assert data["metrics"]["ai_share"] == 66.7
    assert len(data["products"]) == 3
    from app.domain.seed import seed

    assert seed(db) is False
    assert all(s["starts_at"] and "Tomorrow" not in s["label"] for s in data["slots"])


def test_consent_changes_price_once(client, auth, db):
    q = approve(client, auth, "CASE1043")
    assert re.fullmatch("R[0-9A-F]{6}", q["proposal_ref"])
    assert db.get(Order, "ORD1043").total_paise == 79900
    send(client, auth, "yes")
    assert db.get(Order, "ORD1043").total_paise == 79900
    send(client, auth, "CONFIRM " + q["proposal_ref"])
    send(client, auth, "CONFIRM " + q["proposal_ref"])
    assert db.get(Order, "ORD1043").total_paise == 114700
    assert db.get(Order, "ORD1043").paid_paise == 0
    assert db.get(Case, "CASE1043").primary_status == "resolved"


@pytest.mark.parametrize("quote,expected_total", [(None, 114700), (0, 94800)])
def test_approval_preserves_an_omitted_quote_and_honors_zero(client, auth, db, quote, expected_total):
    payload = {"decision": "approve"}
    if quote is not None:
        payload["quote_paise"] = quote
    result = client.post("/api/cases/CASE1043/decision", headers=auth, json=payload)
    assert result.status_code == 200
    assert db.get(Order, "ORD1043").total_paise == 79900
    send(client, auth, "CONFIRM " + result.json()["proposal_ref"])
    assert db.get(Order, "ORD1043").total_paise == expected_total
    assert db.get(Order, "ORD1043").paid_paise == 0


def test_duplicate_inbound_does_not_repeat_response(client, auth, db):
    mid = str(uuid4())
    send(client, auth, "What is the return policy?", message_id=mid)
    before = len(list(db.scalars(select(Message))))
    assert send(client, auth, "What is the return policy?", message_id=mid)["duplicate"]
    assert len(list(db.scalars(select(Message)))) == before


def test_pickup_stock_handover_and_payment(client, auth, db):
    case, res, code = pickup(client, auth, db)
    p = db.get(Product, "WALLET001")
    assert (p.stock, p.reserved_stock) == (18, 1)
    assert case.primary_status == "ongoing"
    assert client.post(f"/api/pickups/{res.id}/ready", headers=auth, json={}).status_code == 200
    assert client.post(f"/api/pickups/{res.id}/collect", headers=auth, json={}).status_code == 422
    bad = client.post(
        f"/api/pickups/{res.id}/collect",
        headers=auth,
        json={"code": "000000" if code != "000000" else "111111"},
    )
    assert bad.status_code == 422
    assert (p.stock, p.reserved_stock) == (18, 1)
    good = client.post(f"/api/pickups/{res.id}/collect", headers=auth, json={"code": code})
    assert good.status_code == 200, good.text
    assert (p.stock, p.reserved_stock) == (17, 0)
    assert db.get(Order, "ORD1043").paid_paise == 114700
    assert case.primary_status == "resolved"
    assert client.post(f"/api/pickups/{res.id}/collect", headers=auth, json={"code": code}).status_code == 409


def test_pickup_cancel_releases_both_holds(client, auth, db):
    case, res, code = pickup(client, auth, db)
    assert client.post(f"/api/pickups/{res.id}/cancel", headers=auth).status_code == 200
    p = db.get(Product, "WALLET001")
    assert (p.stock, p.reserved_stock) == (18, 0)


def test_stale_terms_and_expiry_require_new_consent(client, auth, db):
    q = approve(client, auth, "CASE1043")
    old = q["proposal_ref"]
    db.get(Order, "ORD1043").total_paise += 100
    db.commit()
    assert "terms changed" in send(client, auth, "CONFIRM " + old)["reply"]
    assert db.get(Case, "CASE1043").primary_status == "flagged"
    new = approve(client, auth, "CASE1043")
    assert new["proposal_ref"] != old
    assert "unavailable" in send(client, auth, "CONFIRM " + old)["reply"]
    db.get(Case, "CASE1043").expires_at = now() - timedelta(seconds=1)
    db.commit()
    assert "expired" in send(client, auth, "CONFIRM " + new["proposal_ref"])["reply"]


def test_cable_refund_follows_inspection_and_consent(client, auth, db):
    r = client.post(
        "/api/cases/HIST009/inspection",
        headers=auth,
        json={"accepted": True, "restock": False, "note": "Cable inspected and accepted."},
    )
    assert r.status_code == 200, r.text
    c = db.get(Case, "HIST009")
    assert c.status == "pending_customer"
    assert db.get(Order, "ORD1044").refunded_paise == 0
    send(client, auth, "CONFIRM " + c.proposal_ref, "CONV003")
    refund = db.scalar(select(Refund).where(Refund.case_id == c.id))
    assert refund.status == "pending"
    assert c.primary_status == "ongoing"
    complete(db)
    assert refund.status == "succeeded"
    assert db.get(Order, "ORD1044").refunded_paise == 19900
    assert c.primary_status == "resolved"


def test_above_limit_requires_photo_and_explicit_waiver(client, auth, db):
    r = client.post("/api/cases/CASE1042/decision", headers=auth, json={"decision": "approve"})
    assert r.status_code == 409
    e = Evidence(
        merchant_id="SELLER001",
        conversation_id="CONV001",
        case_id="CASE1042",
        object_key="fake",
        filename="photo.jpg",
        mime_type="image/jpeg",
        assessment="Unclear",
    )
    db.add(e)
    db.commit()
    assert client.post(f"/api/evidence/{e.id}/verify", headers=auth).status_code == 200
    assert (
        client.post("/api/cases/CASE1042/decision", headers=auth, json={"decision": "approve"}).status_code
        == 409
    )
    c = approve(
        client, auth, "CASE1042", waive_return=True, note="Demo inspection accepted; waive physical return."
    )
    send(client, auth, "CONFIRM " + c["proposal_ref"], "CONV001")
    assert db.get(Order, "ORD1042").refunded_paise == 0
    complete(db)
    assert db.get(Order, "ORD1042").refunded_paise == 199900


def test_return_does_not_automatically_restock(client, auth, db):
    p = db.get(Product, "CABLE001")
    before = p.stock
    client.post(
        "/api/cases/HIST009/inspection",
        headers=auth,
        json={"accepted": True, "restock": False, "note": "Damaged cable, do not restock"},
    )
    assert p.stock == before


def test_two_unsuccessful_solutions_not_two_messages(client, auth, db):
    send(client, auth, "Where is ORD1044?", "CONV003")
    c = latest(db, "tracking")
    first_solution = c.details["last_solution"]
    send(client, auth, "That didn't work", "CONV003")
    assert c.resolution_attempts == 1
    assert not db.get(Conversation, "CONV003").handoff
    send(client, auth, "That still didn't work", "CONV003")
    assert c.resolution_attempts == 1
    send(client, auth, "Where is ORD1044?", "CONV003")
    second_solution = c.details["last_solution"]
    send(client, auth, "That did not solve it", "CONV003")
    assert c.resolution_attempts == 2
    assert c.primary_status == "flagged"
    assert db.get(Conversation, "CONV003").handoff
    logs = list(db.scalars(select(AuditLog).where(
        AuditLog.action == "case.resolution_failed", AuditLog.entity_id == c.id
    ).order_by(AuditLog.created_at)))
    assert [a.detail["resolution_attempts"] for a in logs] == [1, 2]
    assert [a.detail["solution_message_id"] for a in logs] == [first_solution, second_solution]
    assert first_solution != second_solution
    assert all(db.get(Message, a.detail["input_message_id"]).role == "customer" for a in logs)
    count = len(list(db.scalars(select(Message).where(
        Message.conversation_id == "CONV003", Message.role == "assistant"
    ))))
    send(client, auth, "Where is ORD1044?", "CONV003")
    assert c.resolution_attempts == 2
    assert len(list(db.scalars(select(Message).where(
        Message.conversation_id == "CONV003", Message.role == "assistant"
    )))) == count
    assert db.scalar(select(AuditLog).where(AuditLog.action == "message.held_for_seller"))


def test_human_handoff_pauses_customer_automation(client, auth, db):
    send(client, auth, "I want a human", "CONV002")
    assert db.get(Conversation, "CONV002").handoff
    count = len(list(db.scalars(select(Message).where(Message.role == "assistant"))))
    send(client, auth, "Where is my order?", "CONV002")
    assert len(list(db.scalars(select(Message).where(Message.role == "assistant")))) == count
    assert (
        client.patch("/api/conversations/CONV002/handoff", headers=auth, json={"enabled": False}).status_code
        == 200
    )


def test_published_policy_invalidates_old_proposals(client, auth, db):
    q = approve(client, auth, "CASE1043")
    rules = db.get(Policy, "POLICY001").rules
    d = client.post(
        "/api/policies/drafts", headers=auth, json={**rules, "auto_refund_limit_paise": 10000}
    ).json()
    assert not d["published"]
    assert db.get(Case, "CASE1043").status == "pending_customer"
    assert client.post(f"/api/policies/{d['id']}/publish", headers=auth).status_code == 200
    send(client, auth, "CONFIRM " + q["proposal_ref"])
    assert db.get(Order, "ORD1043").total_paise == 79900


def test_feedback_updates_same_case_and_audits_correction(client, auth, db):
    accepted_wallet(client, auth, db)
    send(client, auth, "5 stars, lovely gift wrapping!")
    send(client, auth, "4 stars, correction")
    reviews = list(db.scalars(select(Review).where(Review.case_id == "CASE1043")))
    assert len(reviews) == 1 and reviews[0].rating == 4


def test_cross_customer_confirmation_and_order_lookup(client, auth, db):
    q = approve(client, auth, "CASE1043")
    send(client, auth, "CONFIRM " + q["proposal_ref"], "CONV001")
    assert db.get(Order, "ORD1043").total_paise == 79900
    result = send(client, auth, "Where is ORD1043?", "CONV001")
    assert "could not verify" in result["reply"]
    assert "wallet" not in result["reply"].lower()


def test_empty_cohort_has_null_rates(client, auth):
    d = client.get("/api/workspace?date_from=2000-01-01&date_to=2000-01-02", headers=auth).json()
    assert d["metrics"]["total"] == 0
    assert d["metrics"]["resolution_rate"] is None
    assert d["metrics"]["rating"] is None


def test_insights_sources_and_range_are_saved(client, auth, db):
    w = client.get("/api/workspace", headers=auth).json()
    r = client.post(
        "/api/insights/analyze",
        headers=auth,
        json={"date_from": w["date_range"]["from"], "date_to": w["date_range"]["to"]},
    )
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["mode"] == "demo"
    assert all(
        set(x["case_ids"]).issubset({c["id"] for c in w["cases"]}) and x["count"] == len(set(x["case_ids"]))
        for x in report["body"]["recommendations"]
    )


def test_pickup_exhausted_capacity_rolls_back_stock(client, auth, db):
    from app.persistence.models import PickupSlot

    accepted_wallet(client, auth, db)
    send(client, auth, "Pickup wallet tomorrow afternoon")
    c = latest(db, "pickup")
    approve(client, auth, c.id)
    db.get(PickupSlot, "SLOT-PM").reserved = 5
    db.commit()
    send(client, auth, "CONFIRM " + c.proposal_ref)
    p = db.get(Product, "WALLET001")
    assert (p.stock, p.reserved_stock) == (18, 0)


def test_rejection_needs_reason_and_preserves_order(client, auth, db):
    assert (
        client.post("/api/cases/CASE1043/decision", headers=auth, json={"decision": "reject"}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/cases/CASE1043/decision",
            headers=auth,
            json={"decision": "reject", "note": "Engraving unavailable"},
        ).status_code
        == 200
    )
    assert db.get(Case, "CASE1043").primary_status == "resolved"
    assert db.get(Order, "ORD1043").total_paise == 79900


def test_short_clarification_reuses_waiting_request(client, auth, db):
    db.add(
        Conversation(
            id="CONV-CLARIFY",
            merchant_id="SELLER001",
            customer_id="CUS003",
            order_id="ORD1044",
            channel="demo",
        )
    )
    db.commit()
    send(client, auth, "Refund my cable", "CONV-CLARIFY")
    c = latest(db, "refund")
    assert c.status == "needs_customer_details"
    send(client, auth, "It is defective", "CONV-CLARIFY")
    assert c.details["reason"] == "defective"
    assert c.primary_status == "flagged"
    assert len(list(db.scalars(select(Case).where(Case.kind == "refund", Case.order_id == "ORD1044")))) == 1


def test_seller_question_answer_returns_same_case_to_review(client, auth, db):
    client.post(
        "/api/cases/CASE1043/decision",
        headers=auth,
        json={"decision": "request_details", "note": "What initials should be engraved?"},
    )
    send(client, auth, "A R please")
    c = db.get(Case, "CASE1043")
    assert c.primary_status == "flagged"
    assert c.details["customer_clarification"] == "A R please"


def test_return_inspection_obeys_refund_permission(client, auth, db):
    p = db.get(Policy, "POLICY001")
    p.rules = {**p.rules, "refund_permission": "approval_required"}
    db.commit()
    r = client.post(
        "/api/cases/HIST009/inspection",
        headers=auth,
        json={"accepted": True, "restock": False, "note": "Cable inspected."},
    )
    assert r.status_code == 200
    assert db.get(Case, "HIST009").primary_status == "flagged"
    assert db.get(Case, "HIST009").proposal_ref is None


def test_refund_pending_uncertain_and_failed_balance(db):
    from app.domain.commerce import pending_refunds

    o = db.get(Order, "ORD1044")
    r = Refund(case_id="HIST009", order_id=o.id, amount_paise=19900, status="pending", provider="simulated")
    db.add(r)
    db.flush()
    assert pending_refunds(db, o) == 19900
    r.status = "uncertain"
    db.flush()
    assert pending_refunds(db, o) == 19900
    r.status = "failed"
    db.flush()
    assert pending_refunds(db, o) == 0
    assert o.refunded_paise == 0


def test_multiple_requests_keep_independent_consent(client, auth, db):
    send(client, auth, "Engrave my wallet and pickup the wallet tomorrow")
    custom = db.get(Case, "CASE1043")
    p = latest(db, "pickup")
    approve(client, auth, custom.id)
    approve(client, auth, p.id)
    assert custom.proposal_ref != p.proposal_ref
    send(client, auth, "CONFIRM " + custom.proposal_ref)
    assert custom.consented_at
    assert not p.consented_at
    # Changed order total invalidates the still-pending pickup terms.
    send(client, auth, "CONFIRM " + p.proposal_ref)
    assert p.primary_status == "flagged"
    assert not db.get(Order, "ORD1043").inventory_reserved


def test_memory_has_source_ids_and_keeps_twelve_recent(client, auth, db):
    from app.domain.cases import remember

    c = db.get(Case, "CASE1043")
    for i in range(16):
        db.add(
            Message(
                id="memory-" + str(i),
                conversation_id=c.conversation_id,
                role="customer",
                body="Untrusted context " + str(i),
                case_ids=[c.id],
            )
        )
    db.flush()
    recent = remember(db, c)
    assert len(recent) == 12
    assert len(c.memory["source_message_ids"]) >= 4
    assert all(db.get(Message, item["message_id"]) for item in c.memory["observations"])
    assert c.resolution_attempts == 0


def test_clear_photo_can_continue_eligible_return_without_seller(client, auth, db, monkeypatch, tmp_path):
    from app.domain.evidence import save_evidence
    from app.domain.cases import support_case
    from PIL import Image
    from io import BytesIO

    monkeypatch.setattr(get_settings(), "evidence_root", str(tmp_path))
    monkeypatch.setattr(
        "app.domain.evidence.assess_image",
        lambda *args: {"quality": "clear", "observation": "Visible broken cable connector."},
    )
    conv = db.get(Conversation, "CONV003")
    c = support_case(db, conv, "return", "Return damaged cable", reuse=False)
    c.details = {"reason": "damaged"}
    image = BytesIO()
    Image.new("RGB", (20, 20)).save(image, "PNG")
    item = save_evidence(db, conv, image.getvalue(), "photo.png", c.id)
    assert item.quality == "clear" and not item.verified
    assert c.status == "pending_customer"
    assert not c.seller_assisted


def test_explicit_demo_reset_removes_only_store_evidence(db, monkeypatch, tmp_path):
    from app.domain.reset import reset_demo
    from app.persistence.models import Merchant

    monkeypatch.setattr(get_settings(), "evidence_root", str(tmp_path))
    private = tmp_path / "SELLER001"
    private.mkdir()
    (private / "orphan.jpg").write_bytes(b"fixture")
    other = tmp_path / "OTHER"
    other.mkdir()
    (other / "keep.jpg").write_bytes(b"other")
    db.add(Merchant(id="OTHER", name="Other store", settings={}))
    db.commit()
    with pytest.raises(ValueError):
        reset_demo(db, "SELLER001", "wrong")
    assert private.exists()
    reset_demo(db, "SELLER001", "SELLER001")
    assert db.get(Merchant, "SELLER001") is None
    assert db.get(Merchant, "OTHER")
    assert not private.exists() and (other / "keep.jpg").exists()
    from app.domain.seed import seed

    assert seed(db)
    assert len(list(db.scalars(select(Case)))) == 12


def test_handoff_preserves_return_operation_stage(client, auth, db):
    c = db.get(Case, "HIST009")
    assert (
        client.patch("/api/conversations/CONV003/handoff", headers=auth, json={"enabled": True}).status_code
        == 200
    )
    assert c.primary_status == "flagged" and c.status == "awaiting_return"
    assert (
        client.patch("/api/conversations/CONV003/handoff", headers=auth, json={"enabled": False}).status_code
        == 200
    )
    assert c.primary_status == "ongoing" and c.status == "awaiting_return"
    assert c.seller_assisted
