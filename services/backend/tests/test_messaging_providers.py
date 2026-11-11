import hashlib
import logging
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.domain.common import reply
from app.domain.messaging import apply_receipts
from app.integrations.whatsapp import ProviderDisabled, SandboxQuotaExceeded, WindowClosed, get_provider
from app.persistence.models import AuditLog, Case, Conversation, Customer, DeliveryReceipt, Job, Message, now
from app.workers.worker import execute_job, fail_job


def configure(monkeypatch):
    s = get_settings()
    for key, value in {
        "whatsapp_provider": "360dialog_sandbox",
        "d360_api_key": "fake-test-key",
        "d360_sandbox_recipient": "919999999999",
        "d360_recipient_type": "phone",
        "d360_webhook_secret": "test-secret-" * 4,
        "public_webhook_url": "https://example.test",
    }.items():
        monkeypatch.setattr(s, key, value)
    return s


def incoming(s, pid="wamid.inbound", text="What is your return policy?", **extra):
    m = {
        "from": s.d360_sandbox_recipient,
        "id": pid,
        "timestamp": str(int(now().timestamp())),
        "type": "text",
        "text": {"body": text},
        **extra,
    }
    return {"entry": [{"changes": [{"field": "messages", "value": {"messages": [m]}}]}]}


def post(client, s, payload):
    return client.post("/webhooks/360dialog/" + s.d360_webhook_secret, json=payload)


def test_provider_disabled_by_default_and_no_cross_provider_fallback(monkeypatch):
    assert Settings(_env_file=None, whatsapp_provider="disabled").whatsapp_provider == "disabled"
    configure(monkeypatch)
    with pytest.raises(ProviderDisabled):
        get_provider("twilio")


def test_webhook_authentication_recipient_isolation_and_dedup(client, db, monkeypatch):
    s = configure(monkeypatch)
    assert client.post("/webhooks/360dialog/wrong", json=incoming(s)).status_code == 403
    assert post(client, s, incoming(s, from_user_id="unknown", **{"from": "918888888888"})).status_code == 403
    assert client.post("/webhooks/twilio/incoming", data={}).status_code == 404
    for _ in range(2):
        assert post(client, s, incoming(s)).status_code == 200
    jobs = list(db.scalars(select(Job).where(Job.kind == "incoming_message")))
    assert len(jobs) == 1
    conv = db.get(Conversation, jobs[0].payload["conversation_id"])
    assert conv.messaging_provider == "360dialog_sandbox" and conv.order_id is None
    execute_job(db, jobs[0])
    db.commit()
    assert db.scalar(select(func.count()).select_from(Message).where(Message.conversation_id == conv.id)) == 2


def test_bsuid_never_claims_phone_or_another_customers_orders(client, db, monkeypatch):
    s = configure(monkeypatch)
    monkeypatch.setattr(s, "d360_recipient_type", "bsuid")
    monkeypatch.setattr(s, "d360_sandbox_recipient", "business-user-123")
    p = incoming(s, text="Where is ORD1043?", from_user_id=s.d360_sandbox_recipient)
    del p["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
    assert post(client, s, p).status_code == 200
    job = db.scalar(select(Job).where(Job.kind == "incoming_message"))
    conv = db.get(Conversation, job.payload["conversation_id"])
    assert db.get(Customer, conv.customer_id).phone is None and conv.order_id is None
    execute_job(db, job)
    assert "could not verify" in db.scalar(
        select(Message.body).where(Message.conversation_id == conv.id, Message.role == "assistant")
    )


def test_expired_inbound_does_not_reopen_window_during_agent_processing(client, db, monkeypatch):
    s = configure(monkeypatch)
    old = now() - timedelta(hours=25)
    assert post(client, s, incoming(s, timestamp=str(int(old.timestamp())))).status_code == 200
    job = db.scalar(select(Job).where(Job.kind == "incoming_message"))
    execute_job(db, job)
    send = db.scalar(select(Job).where(Job.kind == "send_message"))
    execute_job(db, send)
    assert send.status == "waiting_window"


def test_delivery_receipt_before_send_association_is_durable(client, db, monkeypatch):
    s = configure(monkeypatch)
    post(client, s, incoming(s))
    job = db.scalar(select(Job).where(Job.kind == "incoming_message"))
    execute_job(db, job)
    conv = db.get(Conversation, job.payload["conversation_id"])
    out = db.scalar(select(Message).where(Message.conversation_id == conv.id, Message.role == "assistant"))
    case = db.get(Case, out.case_ids[0])
    assert case.primary_status == "ongoing"
    value = {
        "statuses": [
            {"id": "wamid.outbound", "recipient_id": s.d360_sandbox_recipient, "status": "delivered"}
        ]
    }
    p = {"entry": [{"changes": [{"field": "messages", "value": value}]}]}
    for _ in range(2):
        assert post(client, s, p).status_code == 200
    assert db.scalar(select(func.count()).select_from(DeliveryReceipt)) == 1
    out.provider_id = "wamid.outbound"
    out.status = "queued"
    assert apply_receipts(db, out)
    assert out.status == "delivered" and case.primary_status == "resolved"
    value["statuses"][0]["status"] = "sent"
    post(client, s, p)
    assert out.status == "delivered"
    assert db.scalar(
        select(AuditLog).where(AuditLog.action == "message.delivery", AuditLog.entity_id == out.id)
    )


def test_actual_transport_freeform_payload_and_no_credentials_in_body(monkeypatch):
    s = configure(monkeypatch)
    captured = []

    def send(url, **kwargs):
        captured.append((url, kwargs))
        return httpx.Response(
            201, json={"messages": [{"id": "wamid.sent"}]}, request=httpx.Request("POST", url)
        )

    monkeypatch.setattr(httpx, "post", send)
    provider = get_provider()
    assert provider.send_text(s.d360_sandbox_recipient, "Generated answer", now(), "local") == "wamid.sent"
    url, args = captured[0]
    assert url == "https://waba-sandbox.360dialog.io/v1/messages"
    assert args["headers"]["D360-API-KEY"] == s.d360_api_key
    assert args["json"] == {
        "messaging_product": "whatsapp",
        "to": s.d360_sandbox_recipient,
        "type": "text",
        "text": {"body": "Generated answer"},
    }
    with pytest.raises(WindowClosed):
        provider.send_text(s.d360_sandbox_recipient, "No send", now() - timedelta(hours=25), "local")
    assert len(captured) == 1


def test_quota_exhaustion_is_definitive_and_not_retried(db, monkeypatch):
    s = configure(monkeypatch)
    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: httpx.Response(429, request=httpx.Request("POST", url))
    )
    with pytest.raises(SandboxQuotaExceeded):
        get_provider().send_text(s.d360_sandbox_recipient, "Test", now(), "local")
    conv = db.get(Conversation, "CONV002")
    conv.channel = "whatsapp"
    msg = reply(db, conv, "Test")
    msg.status = "sending"
    job = db.get(Job, "send:" + msg.id)
    job.attempts = 1
    fail_job(db, job, SandboxQuotaExceeded())
    assert msg.status == "failed" and job.status == "failed"


def test_media_is_flagged_without_download(client, db, monkeypatch):
    s = configure(monkeypatch)
    post(client, s, incoming(s, type="image", image={"id": "image"}))
    job = db.scalar(select(Job).where(Job.kind == "incoming_message"))
    execute_job(db, job)
    msg = db.get(Message, job.payload["message_id"])
    assert msg.processed and db.get(Case, msg.case_ids[0]).primary_status == "flagged"


def test_secret_webhook_urls_are_suppressed_in_access_logs():
    from app.core.logging import WebhookAccessFilter

    record = logging.LogRecord(
        "uvicorn.access",
        20,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("client", "POST", "/webhooks/360dialog/secret", "1.1", 200),
        None,
    )
    assert not WebhookAccessFilter().filter(record)


def test_live_public_answer_is_model_generated_and_audited(client, db, monkeypatch):
    s = configure(monkeypatch)
    post(client, s, incoming(s))
    from app.agents import public_answers

    calls = []

    def generated(model, **kw):
        calls.append(kw)
        return model(
            answer="You can request a return within 7 days after delivery for damaged, defective or incorrect items. Refunds require inspection and store approval."
        )

    monkeypatch.setattr(public_answers, "generate", generated)
    # Keep the classifier fixture deterministic while exercising the live reply boundary.
    from app.agents.workflows import orchestrator

    monkeypatch.setattr(
        orchestrator,
        "classify_many",
        lambda *a, **kw: [{"intent": "policy", "summary": "Return policy", "order_id": None}],
    )
    monkeypatch.setattr(s, "ai_mode", "groq")
    job = db.scalar(select(Job).where(Job.kind == "incoming_message"))
    execute_job(db, job)
    assert len(calls) == 1 and "verified_store_facts" in calls[0]["text"]
    log = db.scalar(select(AuditLog).where(AuditLog.action == "agent.reply_generated"))
    out = db.get(Message, log.entity_id)
    assert (
        log.detail["ai_provider"] == "groq"
        and log.detail["response_sha256"] == hashlib.sha256(out.body.encode()).hexdigest()
    )
