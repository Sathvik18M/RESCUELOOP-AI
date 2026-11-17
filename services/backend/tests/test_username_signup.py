import json
from collections import deque

import httpx
import pytest

from app.api import accounts
from app.core.config import get_settings


@pytest.fixture
def provider(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "supabase_url", "https://project.example.invalid")
    monkeypatch.setattr(settings, "supabase_service_role_key", "server-test-key")
    monkeypatch.setattr(accounts, "signup_attempts", deque())
    state = {"settings": {"disable_signup": False, "external": {"email": True}}, "users": {}}

    async def send(_client, request, **kwargs):
        assert request.url.host == "project.example.invalid"
        assert request.headers["apikey"] == "server-test-key"
        if request.url.path == "/auth/v1/settings":
            return httpx.Response(200, request=request, json=state["settings"])
        assert request.method == "POST" and request.url.path == "/auth/v1/admin/users"
        body = json.loads(request.content)
        if body["email"] in state["users"]:
            return httpx.Response(422, request=request, json={"error_code": "email_exists"})
        state["users"][body["email"]] = body
        return httpx.Response(200, request=request, json={"id": "test-id"})

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    return state


def test_username_signup_and_case_insensitive_uniqueness(client, provider):
    password = "Test passphrase "
    response = client.post("/api/auth/signup", json={"username": "  Maple_123  ", "password": password})
    assert response.status_code == 201
    assert response.json() == {"username": "maple_123"}
    identifier = "maple_123@usernames.rescueloop.invalid"
    assert provider["users"][identifier] == {
        "email": identifier,
        "email_confirm": True,
        "password": password,
        "user_metadata": {"username": "maple_123"},
    }
    duplicate = client.post("/api/auth/signup", json={"username": "MAPLE_123", "password": "another-pass"})
    assert duplicate.status_code == 409
    assert provider["users"][identifier]["password"] == password


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("seller@example.org", "password123"),
        ("ab", "password123"),
        ("maple", "short"),
        ("maple", "☀" * 25),
    ],
)
def test_invalid_credentials_do_not_create_an_account(client, provider, username, password):
    assert (
        client.post("/api/auth/signup", json={"username": username, "password": password}).status_code == 422
    )
    assert not provider["users"]


def test_provider_signup_switch(client, provider):
    provider["settings"]["disable_signup"] = True
    response = client.post("/api/auth/signup", json={"username": "maple", "password": "test-password"})
    assert response.status_code == 403
    assert not provider["users"]


def test_registration_attempts_are_limited(client, provider):
    for i in range(12):
        response = client.post(
            "/api/auth/signup", json={"username": f"seller_{i}", "password": "test-password"}
        )
        assert response.status_code == 201
    response = client.post("/api/auth/signup", json={"username": "another", "password": "test-password"})
    assert response.status_code == 429
    assert len(provider["users"]) == 12
