import json
from collections import deque
from time import time
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.api import accounts
from app.core.auth import supabase_claims
from app.core.config import get_settings
from app.main import app
from app.persistence.models import RecoveryCode


@pytest.fixture
def provider(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "supabase_url", "https://project.example.invalid")
    monkeypatch.setattr(settings, "supabase_service_role_key", "server-test-key")
    monkeypatch.setattr(accounts, "signup_attempts", deque())
    monkeypatch.setattr(accounts, "reset_attempts", deque())
    state = {
        "settings": {"disable_signup": False, "external": {"email": True}},
        "users": {},
        "updates": [],
        "ids": {},
    }

    async def send(_client, request, **kwargs):
        assert request.url.host == "project.example.invalid"
        assert request.headers["apikey"] == "server-test-key"
        if request.url.path == "/auth/v1/settings":
            return httpx.Response(200, request=request, json=state["settings"])
        if request.url.path == "/auth/v1/user":
            assert request.headers["Authorization"] == "Bearer recent-session"
            if not state.get("active_user"):
                return httpx.Response(403, request=request)
            return httpx.Response(200, request=request, json={"id": state["active_user"]})
        if request.method == "PUT":
            uid = request.url.path.removeprefix("/auth/v1/admin/users/")
            assert uid in state["ids"].values()
            if state.get("timeout"):
                raise httpx.ReadTimeout("response lost", request=request)
            if state.get("weak"):
                return httpx.Response(422, headers={"x-sb-error-code": "weak_password"}, request=request)
            state["updates"].append((uid, json.loads(request.content)))
            return httpx.Response(200, request=request, json={"id": uid})
        assert request.method == "POST" and request.url.path == "/auth/v1/admin/users"
        body = json.loads(request.content)
        if body["email"] in state["users"]:
            return httpx.Response(422, request=request, json={"error_code": "email_exists"})
        state["users"][body["email"]] = body
        uid = str(uuid4())
        state["ids"][body["email"]] = uid
        return httpx.Response(200, request=request, json={"id": uid})

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    return state


def test_username_signup_and_case_insensitive_uniqueness(client, provider):
    password = "Test passphrase "
    response = client.post("/api/auth/signup", json={"username": "  Maple_123  ", "password": password})
    assert response.status_code == 201
    assert response.json()["username"] == "maple_123"
    assert len(set(response.json()["recovery_codes"])) == 3
    assert response.headers["cache-control"] == "no-store"
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


def register(client, username):
    result = client.post("/api/auth/signup", json={"username": username, "password": "initial-password"})
    assert result.status_code == 201
    return result.json()["recovery_codes"]


def reset(client, code, password="replacement-password"):
    return client.post("/api/auth/reset-password", json={"recovery_code": code, "new_password": password})


def test_recovery_is_one_time_and_bound_to_owner(client, db, provider):
    maple, other = register(client, "maple"), register(client, "other")
    assert all(len(v) == 64 and v not in maple + other for v in db.scalars(select(RecoveryCode.digest)))
    assert reset(client, maple[0], "short").status_code == 422
    assert reset(client, maple[0].lower().replace("-", " ")).status_code == 204
    assert reset(client, maple[0]).status_code == 400
    assert reset(client, "0" * 32).status_code == 400
    assert provider["updates"] == [
        (provider["ids"]["maple@" + accounts.SIGNUP_DOMAIN], {"password": "replacement-password"})
    ]
    assert reset(client, other[0]).status_code == 204
    assert reset(client, maple[1]).status_code == 204


def test_only_recent_password_proof_can_replace_own_codes(client, provider):
    old, other = register(client, "maple"), register(client, "other")
    assert client.post("/api/auth/recovery-codes").status_code == 401
    uid = provider["ids"]["maple@" + accounts.SIGNUP_DOMAIN]
    claims = {"sub": uid, "amr": []}
    app.dependency_overrides[supabase_claims] = lambda: claims
    for method, timestamp in [("password", time() - 200), ("token_refresh", time())]:
        claims["amr"] = [{"method": method, "timestamp": timestamp}]
        assert client.post("/api/auth/recovery-codes").status_code == 403
    claims["amr"] = [{"method": "password", "timestamp": int(time())}]
    headers = {"Authorization": "Bearer recent-session"}
    assert client.post("/api/auth/recovery-codes", headers=headers).status_code == 403
    provider["active_user"] = uid
    response = client.post("/api/auth/recovery-codes", headers=headers)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    for code in old:
        assert reset(client, code).status_code == 400
    assert reset(client, response.json()["recovery_codes"][0]).status_code == 204
    assert reset(client, other[0]).status_code == 204


def test_provider_errors_do_not_allow_ambiguous_replay(client, provider):
    codes = register(client, "maple")
    provider["weak"] = True
    assert reset(client, codes[0]).status_code == 422
    provider["weak"] = False
    assert reset(client, codes[0]).status_code == 204
    provider["timeout"] = True
    assert reset(client, codes[1]).status_code == 503
    provider["timeout"] = False
    assert reset(client, codes[1]).status_code == 400
    assert reset(client, codes[2]).status_code == 204


def test_reset_attempts_are_limited(client, provider):
    for _ in range(12):
        assert reset(client, "invalid").status_code == 400
    assert reset(client, "invalid").status_code == 429
