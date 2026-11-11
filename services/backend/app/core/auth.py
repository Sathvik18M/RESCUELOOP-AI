import secrets
from dataclasses import dataclass
from functools import lru_cache
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.persistence.models import Membership
from app.persistence.session import get_db

bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    merchant_id: str
    user_id: str
    role: str = "owner"


@lru_cache
def jwks_client(url: str):
    return jwt.PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json")


def seller(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> Principal:
    settings = get_settings()
    if not credentials:
        raise HTTPException(401, "Sign in to continue")
    token = credentials.credentials
    if (
        settings.demo_mode
        and settings.app_env != "production"
        and secrets.compare_digest(token, settings.demo_token)
    ):
        return Principal("SELLER001", "demo-seller")
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
        membership = db.get(Membership, claims["sub"])
        if not membership:
            raise HTTPException(403, "No store membership")
        return Principal(membership.merchant_id, membership.user_id, membership.role)
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Session expired or invalid") from exc


def owner(principal: Principal = Depends(seller)):
    if principal.role != "owner":
        raise HTTPException(403, "Owner permission required")
    return principal


def demo_only(principal: Principal = Depends(seller)):
    if not get_settings().demo_mode or get_settings().app_env == "production":
        raise HTTPException(404, "Not found")
    return principal
