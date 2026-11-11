from datetime import timedelta
from sqlalchemy import select
from twilio.request_validator import RequestValidator
import httpx
from app.core.config import get_settings
from app.persistence.models import Case, Conversation, Message, Job, Order, Customer, Merchant, now
from app.workers.worker import fail_job, execute_job
from app.domain.common import reply
from app.api.webhooks import apply_delivery


def configure(monkeypatch):
    s = get_settings()
    for k, v in {
        "whatsapp_provider": "twilio",
        "twilio_account_sid": "ACtest",
        "twilio_auth_token": "test-secret",
        "twilio_whatsapp_from": "whatsapp:+14155238886",
        "public_webhook_url": "https://demo.example.test",
    }.items():
        monkeypatch.setattr(s, k, v)
    return s


def post_signed(client, s, path, data):
    sig = RequestValidator(s.twilio_auth_token).compute_signature(s.public_webhook_url + path, data)
    return client.post(path, data=data, headers={"X-Twilio-Signature": sig})


def test_twilio_signature_deduplication_and_processing(client, db, monkeypatch):
    s = configure(monkeypatch)
    payload = {
        "AccountSid": s.twilio_account_sid,
        "To": s.twilio_whatsapp_from,
        "From": "whatsapp:+910000000003",
        "MessageSid": "SMfixture001",
        "Body": "Where is ORD1044?",
        "NumMedia": "0",
    }
    assert client.post("/webhooks/twilio/incoming", data=payload).status_code == 403
    for _ in range(2):
        assert post_signed(client, s, "/webhooks/twilio/incoming", payload).status_code == 200
    jobs = list(db.scalars(select(Job).where(Job.kind == "incoming_message")))
    assert len(jobs) == 1
    assert not db.get(Message, "SMfixture001").processed
    execute_job(db, jobs[0])
    db.commit()
    assert db.get(Message, "SMfixture001").processed
    conv = db.get(Conversation, jobs[0].payload["conversation_id"])
    assert conv.channel == "whatsapp"
    assert any(
        m.status == "queued"
        for m in db.scalars(
            select(Message).where(Message.conversation_id == conv.id, Message.role == "assistant")
        )
    )


def test_unknown_sender_has_no_order(client, db, monkeypatch):
    s = configure(monkeypatch)
    p = {
        "AccountSid": s.twilio_account_sid,
        "To": s.twilio_whatsapp_from,
        "From": "whatsapp:+919999999999",
        "MessageSid": "SMunknown",
        "Body": "Where is ORD1043?",
        "NumMedia": "0",
    }
    assert post_signed(client, s, "/webhooks/twilio/incoming", p).status_code == 200
    job = db.get(Job, "incoming:SMunknown")
    execute_job(db, job)
    db.commit()
    conv = db.get(Conversation, job.payload["conversation_id"])
    assert conv.order_id is None
    assert (
        "could not verify"
        in list(
            db.scalars(select(Message).where(Message.conversation_id == conv.id, Message.role == "assistant"))
        )[-1].body
    )


def test_three_technical_attempts_and_separate_resolution_counter(db):
    c = db.get(Case, "CASE1043")
    msg = Message(
        id="retry-input",
        conversation_id="CONV002",
        role="customer",
        body="Test",
        status="received",
        processed=False,
        case_ids=[c.id],
    )
    db.add(msg)
    db.add(
        Job(id="retry", kind="incoming_message", payload={"message_id": msg.id, "conversation_id": "CONV002"})
    )
    db.flush()
    job = db.get(Job, "retry")
    for attempt in [1, 2, 3]:
        job.attempts = attempt
        before = now()
        fail_job(db, job, httpx.ConnectError("offline"))
        assert c.resolution_attempts == 0
        assert job.status == ("pending" if attempt < 3 else "failed")
        if attempt < 3:
            assert (job.available_at - before).total_seconds() >= (5 if attempt == 1 else 15)
    assert c.primary_status == "flagged"


def test_ambiguous_send_is_not_retried(db):
    msg = Message(
        id="uncertain-send",
        conversation_id="CONV002",
        role="assistant",
        body="Update",
        status="sending",
        case_ids=["CASE1043"],
    )
    db.add(msg)
    db.add(Job(id="uncertain-job", kind="send_message", payload={"message_id": msg.id}, attempts=1))
    db.flush()
    job = db.get(Job, "uncertain-job")
    fail_job(db, job, httpx.ReadTimeout("timeout"))
    assert job.status == "needs_review" and msg.status == "uncertain"


def test_takeover_suppresses_queued_ai_send(db):
    conv = db.get(Conversation, "CONV002")
    conv.channel = "whatsapp"
    msg = reply(db, conv, "Automated answer")
    conv.handoff = True
    job = db.get(Job, "send:" + msg.id)
    execute_job(db, job)
    assert job.status == "held" and msg.status == "held_for_seller"


def test_completion_waits_for_delivery(db):
    c = db.get(Case, "HIST001")
    conv = db.get(Conversation, c.conversation_id)
    conv.channel = "whatsapp"
    msg = reply(db, conv, "Outcome", cases=[c], completes=True)
    assert c.primary_status == "ongoing"
    apply_delivery(db, msg, "sent")
    assert c.primary_status == "ongoing"
    apply_delivery(db, msg, "delivered")
    assert c.primary_status == "resolved"
    apply_delivery(db, msg, "sent")
    assert msg.status == "delivered"


def test_store_scope_rejects_foreign_evidence(client, auth, db):
    from app.persistence.models import Evidence

    db.add(Merchant(id="OTHER", name="Other", settings={}))
    db.flush()
    # Foreign evidence cannot be reached even with an otherwise valid seller session.
    db.add(
        Evidence(
            id="FOREIGN",
            merchant_id="OTHER",
            conversation_id="CONV001",
            object_key="hidden",
            filename="x.jpg",
            mime_type="image/jpeg",
            assessment="private",
        )
    )
    db.commit()
    assert client.get("/api/evidence/FOREIGN/image", headers=auth).status_code == 404


def test_private_photo_normalization():
    from app.integrations.storage import normalize_image
    from PIL import Image
    from io import BytesIO

    output = BytesIO()
    Image.new("RGB", (40, 40)).save(output, format="PNG")
    assert normalize_image(output.getvalue()).startswith(b"\xff\xd8")


def test_late_delivery_reconciles_only_the_pending_outcome(db):
    c = db.get(Case, "HIST001")
    conv = db.get(Conversation, c.conversation_id)
    conv.channel = "whatsapp"
    msg = reply(db, conv, "Outcome", cases=[c], completes=True)
    apply_delivery(db, msg, "undelivered")
    assert c.primary_status == "flagged"
    apply_delivery(db, msg, "delivered")
    assert c.primary_status == "resolved"
    from app.domain.cases import transition

    transition(db, c, "ongoing", "investigating")
    apply_delivery(db, msg, "read")
    assert c.primary_status == "ongoing"


def test_invalid_mime_and_oversize_photo_are_rejected():
    import pytest
    from fastapi import HTTPException
    from app.integrations.storage import normalize_image, MAX_BYTES

    for raw in [b"not a photo", b"x" * (MAX_BYTES + 1)]:
        with pytest.raises(HTTPException):
            normalize_image(raw)


def test_retry_after_and_permanent_provider_failures():
    from app.workers.worker import delay_for, permanent

    req = httpx.Request("POST", "https://provider.test")
    response = httpx.Response(429, headers={"Retry-After": "40"}, request=req)
    err = httpx.HTTPStatusError("Rate limit", request=req, response=response)
    assert delay_for(1, err) == 40
    assert not permanent(err)
    rejected = httpx.HTTPStatusError("Denied", request=req, response=httpx.Response(403, request=req))
    assert permanent(rejected)


def test_local_verification_cannot_use_configured_provider_credentials():
    from app.core.config import Settings

    settings = Settings(
        _env_file=None,
        local_verification_only=True,
        app_env="production",
        ai_mode="groq",
        demo_mode=False,
        database_url="postgresql://example.invalid/live",
        groq_api_key="test-only",
        supabase_url="https://example.invalid",
        supabase_service_role_key="test-only",
        twilio_account_sid="test-only",
        twilio_auth_token="test-only",
        twilio_whatsapp_from="whatsapp:+910000000000",
        public_webhook_url="https://example.invalid",
    )
    settings.validate_runtime()
    assert settings.demo_mode and settings.ai_mode == "demo"
    assert settings.database_url.endswith("/rescueloop_rebuild")
    assert not any(
        [
            settings.groq_api_key,
            settings.supabase_url,
            settings.supabase_service_role_key,
            settings.twilio_account_sid,
            settings.twilio_auth_token,
            settings.twilio_whatsapp_from,
            settings.public_webhook_url,
        ]
    )


def test_media_redirect_does_not_forward_credentials(monkeypatch):
    from app.integrations.whatsapp import download_media

    s = configure(monkeypatch)
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.host == "api.twilio.com":
            return httpx.Response(302, headers={"Location": "https://media.twiliocdn.com/test.jpg"})
        return httpx.Response(200, content=b"photo fixture")

    client_type = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs)
    )
    url = f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_account_sid}/Messages/SMtest/Media/MEtest"
    assert download_media(url) == b"photo fixture"
    assert "authorization" in requests[0].headers
    assert "authorization" not in requests[1].headers


def test_public_gateway_has_no_seller_api_and_requires_signatures(db, monkeypatch):
    from fastapi.testclient import TestClient
    from app.webhook_gateway import app as gateway
    from app.persistence.session import get_db

    configure(monkeypatch)
    gateway.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(gateway) as client:
            for path in ["/api/workspace", "/docs", "/openapi.json"]:
                assert client.get(path).status_code == 404
            assert client.get("/health").status_code == 200
            assert client.get("/webhooks/twilio/incoming").status_code == 405
            assert client.post("/webhooks/twilio/incoming", data={"Body": "untrusted"}).status_code == 403
            assert (
                client.post("/webhooks/twilio/status", data={"MessageStatus": "delivered"}).status_code == 403
            )
    finally:
        gateway.dependency_overrides.clear()
