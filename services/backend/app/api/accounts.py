"""Public username registration for seller accounts backed by Supabase Auth."""

import re
from collections import deque
from time import monotonic

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, SecretStr

from app.core.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["accounts"])
USERNAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_]{2,31}")
SIGNUP_DOMAIN = "usernames.rescueloop.invalid"
signup_attempts: deque[tuple[float, str]] = deque()


class UsernameSignup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str
    password: SecretStr


def limit_registrations(peer: str) -> None:
    # Called on the API event loop before any await. Bound both work and memory,
    # including when many clients share a proxy or use different addresses.
    now = monotonic()
    while signup_attempts and signup_attempts[0][0] <= now - 60:
        signup_attempts.popleft()
    if len(signup_attempts) >= 120 or sum(ip == peer for _, ip in signup_attempts) >= 12:
        raise HTTPException(
            429, "Too many signup attempts. Try again in a minute.", headers={"Retry-After": "60"}
        )
    signup_attempts.append((now, peer))


@router.post("/signup", status_code=201)
async def register_username(data: UsernameSignup, request: Request) -> dict[str, str]:
    settings = get_settings()
    if settings.demo_mode or not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(503, "Account registration is unavailable in this environment.")
    username = data.username.strip()
    if USERNAME.fullmatch(username) is None:
        raise HTTPException(422, "Use 3–32 letters, digits or underscores, starting with a letter or digit.")
    username = username.lower()
    password = data.password.get_secret_value()
    if len(password) < 8 or len(password.encode("utf-8")) > 72:
        raise HTTPException(422, "Use at least 8 characters and at most 72 bytes for your password.")

    limit_registrations(request.client.host if request.client else "unknown")
    # The service key only confirms identifiers in our reserved, non-deliverable
    # namespace. Real email addresses can never be supplied to the admin endpoint.
    key = settings.supabase_service_role_key
    try:
        async with httpx.AsyncClient(
            base_url=settings.supabase_url.rstrip("/") + "/auth/v1/",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=10,
        ) as auth:
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
    return {"username": username}
