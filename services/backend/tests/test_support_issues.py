import json

import httpx
import pytest
from sqlalchemy import func, select

from app.agents import router
from app.core.config import get_settings
from app.domain.conversations import receive
from app.domain.support_issues import BY_CODE, ISSUES
from app.persistence.models import AuditLog, Case, Conversation, Customer, Job, Message, Operation, Order
from app.workers.worker import fail_job


def unverified_conversation(db):
    customer = Customer(id="TEST-UNKNOWN", merchant_id="SELLER001", name="Unknown tester", phone=None)
    conv = Conversation(
        id="TEST-SUPPORT",
        merchant_id="SELLER001",
        customer_id=customer.id,
        channel="demo",
        messaging_provider="360dialog_sandbox",
    )
    db.add(customer)
    db.flush()
    db.add(conv)
    db.flush()
    return conv


@pytest.mark.parametrize("issue", ISSUES, ids=lambda i: i.code + "-" + i.key)
def test_every_issue_gets_a_saved_next_step_without_unverified_effects(db, monkeypatch, issue):
    monkeypatch.setattr(get_settings(), "ai_mode", "demo")
    conv = unverified_conversation(db)
    before = {
        o.id: (o.status, o.total_paise, o.paid_paise, o.refunded_paise) for o in db.scalars(select(Order))
    }
    operations = db.scalar(select(func.count()).select_from(Operation))
    receive(db, conv, issue.example, "issue-" + issue.code)
    db.flush()
    outputs = list(
        db.scalars(select(Message).where(Message.conversation_id == conv.id, Message.role != "customer"))
    )
    assert outputs and all(m.body.strip() for m in outputs)
    cases = list(db.scalars(select(Case).where(Case.conversation_id == conv.id)))
    assert len(cases) == 1
    assert cases[0].details["issue_code"] == issue.code
    assert cases[0].resolution_attempts == 0
    assert cases[0].primary_status != "resolved"
    assert conv.handoff is (issue.code == "35")
    assert db.scalar(select(func.count()).select_from(Operation)) == operations
    assert before == {
        o.id: (o.status, o.total_paise, o.paid_paise, o.refunded_paise) for o in db.scalars(select(Order))
    }
    if issue.code in {"13", "14", "15", "17", "18", "30", "31"}:
        assert "cannot retrieve" in " ".join(m.body for m in outputs)


def test_wrong_item_complaint_cannot_be_promoted_to_replacement(monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_mode", "groq")
    proposal = router.demo_classify(BY_CODE["15"].example)
    proposal["intent"] = "replacement"
    monkeypatch.setattr(
        router, "generate", lambda *a, **kw: router.ProposalBatch(proposals=[router.Proposal(**proposal)])
    )
    result = router.classify_many("i have got the wrong order", "{}")
    assert result[0]["intent"] == "wrong_item" and result[0]["issue_code"] == "15"


def test_wrong_item_live_answer_is_grounded_audited_and_preserves_other_counters(db, monkeypatch):
    from app.agents.workflows import wrong_item

    conv = unverified_conversation(db)
    prior = db.get(Case, "CASE1043")
    prior.resolution_attempts = 2
    monkeypatch.setattr(get_settings(), "ai_mode", "groq")
    calls = []

    def generate(model, **kwargs):
        calls.append(json.loads(kwargs["text"]))
        return model(
            order_id=None,
            ordered_product=None,
            received_product=None,
            complaint_type="wrong_item",
            requested_resolution=None,
            resolution_message_id=None,
        )

    monkeypatch.setattr(wrong_item, "generate", generate)
    receive(db, conv, "i have got the wrong order", "wrong-item-test")
    db.flush()
    assert len(calls) == 1 and calls[0]["customer_messages"][0]["text"] == "i have got the wrong order"
    audit = db.scalar(
        select(AuditLog).where(
            AuditLog.action == "tool.resolution_extract_completed",
            AuditLog.detail["input_message_id"].as_string() == "wrong-item-test",
        )
    )
    assert audit and audit.detail["ai_provider"] == "groq"
    assert prior.resolution_attempts == 2
    assert db.get(Message, "wrong-item-test").case_ids


@pytest.mark.parametrize("handoff", [False, True])
def test_processing_failure_saves_case_and_sends_one_honest_notice_unless_handoff(db, handoff):
    conv = unverified_conversation(db)
    conv.handoff = handoff
    msg = Message(
        id="failed-support-input",
        conversation_id=conv.id,
        role="customer",
        body="Wrong order",
        processed=False,
    )
    job = Job(
        id="failed-support-job",
        kind="incoming_message",
        attempts=3,
        payload={"message_id": msg.id, "conversation_id": conv.id},
    )
    db.add_all([msg, job])
    db.flush()
    fail_job(db, job, httpx.ConnectError("Temporary outage"))
    db.flush()
    fail_job(db, job, httpx.ConnectError("Temporary outage"))
    db.flush()
    notices = list(db.scalars(select(Message).where(Message.id == "processing-error:" + msg.id)))
    assert len(notices) == (0 if handoff else 1)
    if notices:
        assert notices[0].role == "system" and "trouble processing" in notices[0].body
    assert job.status == "failed" and msg.processed and len(msg.case_ids) == 1
    case = db.get(Case, msg.case_ids[0])
    assert case.primary_status == "flagged" and case.resolution_attempts == 0
    assert db.scalar(
        select(AuditLog).where(AuditLog.action == "message.processing_failed", AuditLog.entity_id == msg.id)
    )


def test_wrong_product_photo_stays_with_its_support_case(db, monkeypatch, tmp_path):
    from io import BytesIO

    from PIL import Image

    from app.domain.evidence import save_evidence

    conv = unverified_conversation(db)
    conv.messaging_provider = "twilio"
    monkeypatch.setattr(get_settings(), "ai_mode", "demo")
    monkeypatch.setattr(get_settings(), "evidence_root", str(tmp_path))
    monkeypatch.setattr(
        "app.domain.evidence.assess_image",
        lambda *a: {"quality": "unclear", "observation": "Product label cannot be read."},
    )
    receive(db, conv, BY_CODE["15"].example, "wrong-photo-request")
    case_id = db.get(Message, "wrong-photo-request").case_ids[0]
    data = BytesIO()
    Image.new("RGB", (20, 20)).save(data, "PNG")
    evidence = save_evidence(db, conv, data.getvalue(), "wrong-item.png")
    assert evidence.case_id == case_id
    case = db.get(Case, case_id)
    assert case.kind == "wrong_product" and case.primary_status == "flagged"
    assert case.resolution_attempts == 0 and not evidence.verified
