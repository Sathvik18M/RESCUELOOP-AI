import secrets
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.persistence.models import Membership
from app.persistence.session import get_db

bearer = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


@dataclass
class Principal:
    merchant_id: str
    user_id: str
    role: str = "owner"


@lru_cache
def jwks_client(url: str):
    return jwt.PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json")


def supabase_claims(credentials: BearerCredentials) -> dict:
    settings = get_settings()
    if not credentials:
        raise HTTPException(401, "Sign in to continue")
    token = credentials.credentials
    if not settings.supabase_url:
        raise HTTPException(401, "Invalid credentials")
    try:
        key = jwks_client(settings.supabase_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256", "ES256"],
            audience="authenticated",
            issuer=f"{settings.supabase_url}/auth/v1",
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Session expired or invalid") from exc
    if claims.get("is_anonymous"):
        raise HTTPException(401, "Sign in with a seller account")
    return claims


def supabase_user(credentials: BearerCredentials) -> str:
    return supabase_claims(credentials)["sub"]


def recently_authenticated_user(claims: Annotated[dict, Depends(supabase_claims)]) -> str:
    now = time.time()
    for proof in claims.get("amr", []):
        timestamp = proof.get("timestamp")
        if proof.get("method") == "password" and isinstance(timestamp, (float, int)) and 0 <= now - timestamp <= 120:
            return claims["sub"]
    raise HTTPException(403, "Confirm your current password to replace your recovery codes.")


def seller(
    credentials: BearerCredentials, db: Annotated[Session, Depends(get_db)]
) -> Principal:
    settings = get_settings()
    if (
        credentials and settings.demo_mode and settings.app_env != "production"
        and secrets.compare_digest(credentials.credentials, settings.demo_token)
    ):
        return Principal("SELLER001", "demo-seller")
    membership = db.get(Membership, supabase_user(credentials))
    if not membership:
        raise HTTPException(403, "No store membership")
    return Principal(membership.merchant_id, membership.user_id, membership.role)


def owner(principal: Annotated[Principal, Depends(seller)]):
    if principal.role != "owner":
        raise HTTPException(403, "Owner permission required")
    return principal


def demo_only(principal: Annotated[Principal, Depends(seller)]):
    if not get_settings().demo_mode or get_settings().app_env == "production":
        raise HTTPException(404, "Not found")
    return principal
