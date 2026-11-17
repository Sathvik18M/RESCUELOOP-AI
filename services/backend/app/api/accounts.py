"""Seller registration and email-free password recovery backed by Supabase Auth."""

import hashlib
import re
import secrets
from collections import deque
from time import monotonic
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, SecretStr
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import BearerCredentials, recently_authenticated_user
from app.core.config import get_settings
from app.persistence.models import RecoveryCode
from app.persistence.session import get_db

router = APIRouter(prefix="/api/auth", tags=["accounts"])
USERNAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_]{2,31}")
SIGNUP_DOMAIN = "usernames.rescueloop.invalid"
signup_attempts: deque[tuple[float, str]] = deque()
reset_attempts: deque[tuple[float, str]] = deque()
DatabaseSession = Annotated[Session, Depends(get_db)]


class UsernameSignup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str
    password: SecretStr


class RecoveryCodes(BaseModel):
    recovery_codes: list[str]


class RegisteredAccount(RecoveryCodes):
    username: str


class PasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recovery_code: SecretStr
    new_password: SecretStr


def limit_attempts(attempts: deque, request: Request, action: str) -> None:
    # Called on the API event loop before any await. Bound both work and memory,
    # including when many clients share a proxy or use different addresses.
    now = monotonic()
    peer = request.client.host if request.client else "unknown"
    while attempts and attempts[0][0] <= now - 60:
        attempts.popleft()
    if len(attempts) >= 120 or sum(ip == peer for _, ip in attempts) >= 12:
        raise HTTPException(
            429, f"Too many {action} attempts. Try again in a minute.", headers={"Retry-After": "60"}
        )
    attempts.append((now, peer))


def checked_password(value: SecretStr) -> str:
    password = value.get_secret_value()
    if len(password) < 8 or len(password.encode("utf-8")) > 72:
        raise HTTPException(422, "Use at least 8 characters and at most 72 bytes for your password.")
    return password


def auth_client() -> httpx.AsyncClient:
    settings = get_settings()
    key = settings.supabase_service_role_key
    if settings.demo_mode or not settings.supabase_url or not key:
        raise HTTPException(503, "Account service is unavailable in this environment.")
    return httpx.AsyncClient(
        base_url=settings.supabase_url.rstrip("/") + "/auth/v1/",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=10,
    )


def replace_codes(db: Session, user_id: str) -> list[str]:
    codes = [secrets.token_hex(16).upper() for _ in range(3)]
    rows = [
        {
            "user_id": user_id,
            "slot": slot,
            "digest": hashlib.sha256(code.encode()).hexdigest(),
            "spent": False,
        }
        for slot, code in enumerate(codes)
    ]
    insert = sqlite_insert if db.get_bind().dialect.name == "sqlite" else pg_insert
    stmt = insert(RecoveryCode).values(rows)
    db.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "slot"], set_={"digest": stmt.excluded.digest, "spent": False}
        )
    )
    db.commit()
    return ["-".join(code[n : n + 4] for n in range(0, len(code), 4)) for code in codes]


@router.post("/signup", status_code=201)
async def register_username(
    data: UsernameSignup, request: Request, response: Response, db: DatabaseSession
) -> RegisteredAccount:
    username = data.username.strip()
    if USERNAME.fullmatch(username) is None:
        raise HTTPException(422, "Use 3–32 letters, digits or underscores, starting with a letter or digit.")
    username = username.lower()
    password = checked_password(data.password)

    limit_attempts(signup_attempts, request, "signup")
    # The service key only confirms identifiers in our reserved, non-deliverable
    # namespace. Real email addresses can never be supplied to the admin endpoint.
    try:
        async with auth_client() as auth:
            availability = await auth.get("settings")
            availability.raise_for_status()
            config = availability.json()
            if config.get("disable_signup") is not False:
                raise HTTPException(403, "New account registration is turned off.")
            if not config.get("external", {}).get("email"):
                raise HTTPException(503, "Password sign-in is unavailable.")
            result = await auth.post(
                "admin/users",
                json={
                    "email": f"{username}@{SIGNUP_DOMAIN}",
                    "email_confirm": True,
                    "password": password,
                    "user_metadata": {"username": username},
                },
            )
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Account service unavailable. Please try again.") from None

    if not result.is_success:
        code = result.headers.get("x-sb-error-code")
        if not code and "application/json" in result.headers.get("content-type", ""):
            code = result.json().get("error_code")
        if code in {"email_exists", "user_already_exists"}:
            raise HTTPException(409, "That username is taken. Sign in or choose another.")
        if code == "weak_password":
            raise HTTPException(422, "Choose a stronger password and try again.")
        if result.status_code == 429:
            raise HTTPException(429, "Too many signup attempts. Please try again later.")
        raise HTTPException(503, "Could not create the account. Please try again.")
    response.headers["Cache-Control"] = "no-store"
    try:
        codes = replace_codes(db, result.json()["id"])
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            503, "Account created. Sign in and open Recovery codes to finish setup."
        ) from None
    return RegisteredAccount(username=username, recovery_codes=codes)


@router.post("/recovery-codes")
async def generate_recovery_codes(
    response: Response,
    user_id: Annotated[str, Depends(recently_authenticated_user)],
    credentials: BearerCredentials,
    db: DatabaseSession,
) -> RecoveryCodes:
    # A locally valid access token can outlive a sign-out or a password reset.
    try:
        async with auth_client() as auth:
            user = await auth.get("user", headers={"Authorization": "Bearer " + credentials.credentials})
            if user.status_code in (401, 403):
                raise HTTPException(403, "Sign in again to replace your recovery codes.")
            user.raise_for_status()
            if user.json().get("id") != user_id:
                raise HTTPException(403, "Sign in again to replace your recovery codes.")
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Could not confirm your session. Please try again.") from None
    response.headers["Cache-Control"] = "no-store"
    return RecoveryCodes(recovery_codes=replace_codes(db, user_id))


@router.post("/reset-password", status_code=204)
async def reset_password(data: PasswordReset, request: Request, db: DatabaseSession) -> Response:
    limit_attempts(reset_attempts, request, "recovery")
    password = checked_password(data.new_password)
    code = re.sub(r"[\s-]", "", data.recovery_code.get_secret_value()).upper()
    invalid = "That recovery code is invalid or has already been used."
    if not re.fullmatch(r"[0-9A-F]{32}", code):
        raise HTTPException(400, invalid)
    digest = hashlib.sha256(code.encode()).hexdigest()
    async with auth_client() as auth:
        claim = update(RecoveryCode).where(RecoveryCode.digest == digest, RecoveryCode.spent.is_(False))
        user_id = db.scalar(claim.values(spent=True).returning(RecoveryCode.user_id))
        if not user_id:
            raise HTTPException(400, invalid)
        # Commit before the external side effect. Two simultaneous uses cannot both reset the password.
        db.commit()
        try:
            result = await auth.put(f"admin/users/{user_id}", json={"password": password})
        except httpx.HTTPError:
            result = None
    if result is not None and result.is_success:
        return Response(status_code=204, headers={"Cache-Control": "no-store"})
    if (
        result is not None
        and result.status_code in (400, 422)
        and result.headers.get("x-sb-error-code") in {"weak_password", "same_password"}
    ):
        # The provider definitively refused this password. A concurrent rotation changes the digest.
        db.execute(update(RecoveryCode).where(RecoveryCode.digest == digest).values(spent=False))
        db.commit()
        raise HTTPException(422, "Choose a different, stronger password and try the same code again.")
    raise HTTPException(
        503,
        "This code was used. Try signing in with your new password. If needed, reset with another saved code.",
    )
