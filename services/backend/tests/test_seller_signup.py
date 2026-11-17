from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import func, select

from app.core import auth
from app.core.config import get_settings
from app.persistence.models import Membership, Merchant, Policy, now


@pytest.fixture
def seller_account(monkeypatch):
    project = "https://auth.example.invalid"
    monkeypatch.setattr(get_settings(), "supabase_url", project)
    key = ec.generate_private_key(ec.SECP256R1())
    keys = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key()))
    monkeypatch.setattr(auth, "jwks_client", lambda url: keys)
    user_id = str(uuid4())
    token = jwt.encode(
        {"sub": user_id, "aud": "authenticated", "iss": project + "/auth/v1", "exp": now() + timedelta(hours=1)},
        key, algorithm="ES256",
    )
    return user_id, {"Authorization": "Bearer " + token}


def test_first_login_creates_one_private_workspace(client, db, seller_account):
    user_id, headers = seller_account
    assert client.get("/api/workspace", headers=headers).status_code == 403
    for name in ("   ", "x" * 121):
        assert client.post("/api/workspace", headers=headers, json={"name": name}).status_code == 422

    response = client.post("/api/workspace", headers=headers, json={"name": "  Maple Books  "})
    assert response.status_code == 200
    merchant_id = response.json()["merchant_id"]
    assert merchant_id != "SELLER001"
    db.expire_all()
    member = db.get(Membership, user_id)
    assert (member.merchant_id, member.role) == (merchant_id, "owner")
    retry = client.post("/api/workspace", headers=headers, json={"name": "Another name"})
    assert retry.json() == response.json()
    assert db.scalar(select(func.count()).select_from(Merchant)) == 2
    assert db.scalar(select(func.count()).select_from(Policy).where(Policy.merchant_id == merchant_id)) == 1

    workspace = client.get("/api/workspace", headers=headers).json()
    assert workspace["merchant"]["name"] == "Maple Books"
    assert workspace["cases"] == workspace["customers"] == workspace["orders"] == []
    assert workspace["policies"][0]["published"] is True


def test_existing_membership_keeps_assigned_store_and_role(client, db, seller_account):
    user_id, headers = seller_account
    db.add(Membership(user_id=user_id, merchant_id="SELLER001", role="staff"))
    db.commit()
    response = client.post("/api/workspace", headers=headers, json={"name": "Another store"})
    assert response.json() == {"merchant_id": "SELLER001"}
    assert db.get(Membership, user_id).role == "staff"
    assert db.scalar(select(func.count()).select_from(Merchant)) == 1


def test_workspace_creation_requires_supabase_account(client, auth):
    for headers in ({}, auth):
        assert client.post("/api/workspace", headers=headers, json={"name": "Maple Books"}).status_code == 401
