import hashlib
import hmac
import json
from contextlib import contextmanager
from datetime import timedelta
from sqlalchemy import select
from app.core.config import get_settings
from app.db.models import Case, Conversation, Job, Message, Order, Product, now
from app.modules.common import reply
from app.jobs import worker
from test_workflows import send, approve, latest


def test_feedback_rating_is_not_mistaken_for_a_customization_request(client, auth, db):
    result = send(client, auth, "5 stars, lovely gift wrapping!")
    assert result["intent"] == "feedback"
    data = client.get("/api/workspace", headers=auth).json()
    assert any(r["body"] == "5 stars, lovely gift wrapping!" for r in data["reviews"])


def test_signed_webhook_is_persisted_and_deduplicated(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_app_secret", "test-secret")
    monkeypatch.setattr(get_settings(), "whatsapp_phone_number_id", "test-phone")
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "test-phone"},
                            "messages": [
                                {
                                    "id": "wamid.test-message",
                                    "from": "910000000001",
                                    "type": "text",
                                    "text": {"body": "Track my order"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()
    for _ in range(2):
        r = client.post(
            "/webhooks/whatsapp",
            content=raw,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
        )
        assert r.status_code == 200, r.text
    assert len(list(db.scalars(select(Job).where(Job.kind == "incoming_message")))) == 1


def test_insights_report_is_saved_with_demo_label(client, auth):
    result = client.post("/api/insights/analyze", headers=auth)
    assert result.status_code == 200, result.text
    workspace = client.get("/api/workspace", headers=auth).json()
    assert workspace["merchant"]["settings"]["insight_report"]["mode"] == "demo"
    assert "small sample" in result.json()["summary"]


def test_stale_pickup_quote_cannot_change_order(client, auth, db):
    send(client, auth, "Pickup tomorrow afternoon")
    case = latest(db, "pickup")
    approve(client, auth, case.id)
    order = db.get(Order, "ORD1043")
    order.total_paise += 10000
    db.commit()
    result = send(client, auth, f"CONFIRM {case.id}")
    assert "total changed" in result["reply"]
    assert db.get(Product, "WALLET001").stock == 18


def test_rejected_request_cannot_execute(client, auth, db):
    r = client.post(
        "/api/cases/CASE1043/decision", headers=auth, json={"decision": "reject", "note": "Unavailable"}
    )
    assert r.status_code == 200
    send(client, auth, "CONFIRM CASE1043")
    assert db.get(Case, "CASE1043").status == "rejected"
    assert db.get(Order, "ORD1043").total_paise == 79900


def test_expiration_job_persists_case_transition(client, auth, db, monkeypatch):
    send(client, auth, "Pickup tomorrow afternoon")
    case = latest(db, "pickup")
    job = db.get(Job, f"expire:{case.id}")
    job.available_at = now() - timedelta(seconds=1)
    db.commit()

    @contextmanager
    def session():
        yield db

    monkeypatch.setattr(worker, "SessionLocal", session)
    assert worker.run_once()
    assert db.get(Case, case.id).status == "expired"
    assert db.get(Job, job.id).status == "done"


def test_ambiguous_outbound_delivery_is_not_automatically_retried(client, auth, db, monkeypatch):
    conv = db.get(Conversation, "CONV001")
    conv.channel = "whatsapp"
    msg = reply(db, conv, "A test update")
    db.commit()
    calls = []

    def uncertain(*args):
        calls.append(args)
        raise TimeoutError("Simulated uncertain provider result")

    @contextmanager
    def session():
        yield db

    monkeypatch.setattr(worker, "SessionLocal", session)
    monkeypatch.setattr(worker, "send_text", uncertain)
    assert worker.run_once()
    assert db.get(Message, msg.id).status == "uncertain"
    assert db.get(Job, f"send:{msg.id}").status == "needs_review"
    assert not worker.run_once()
    assert len(calls) == 1
