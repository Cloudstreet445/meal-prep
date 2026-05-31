"""JWT helpers and FastAPI auth dependencies."""

import os
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "")
# Fail closed: an empty, placeholder, or too-short secret means tokens are
# trivially forgeable (PyJWT will still sign AND verify with a weak key, so
# auth doesn't "fail" — it silently becomes spoofable). Refuse to start.
_PLACEHOLDER_SECRETS = {"change-me-to-a-random-secret", "test-secret-change-me", "secret", "changeme"}
if not JWT_SECRET or JWT_SECRET in _PLACEHOLDER_SECRETS or len(JWT_SECRET) < 32:
    raise ValueError(
        "JWT_SECRET must be set to a strong random value of at least 32 characters "
        "(generate with `openssl rand -hex 32`). Refusing to start with a weak or "
        "placeholder secret, which would make authentication tokens forgeable."
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30


def create_jwt(user_id: str, email: str, session_id: str) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": user_id,
        "email": email,
        "sid": session_id,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "sid"]},
        )
    except jwt.PyJWTError:
        return None


def get_current_user(request: Request) -> dict | None:
    """Return decoded JWT payload from cookie, or None. No DB check — use for optional auth."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    return decode_jwt(token)


def require_user(request: Request) -> dict:
    """FastAPI dependency — decodes JWT and verifies the session still exists in DB."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    sid = payload.get("sid")
    if sid:
        from .database import get_db
        db = get_db()
        session = db["sessions"].find_one({"sessionId": sid, "userId": payload["sub"]})
        if not session:
            raise HTTPException(status_code=401, detail="Session has been revoked")
        db["sessions"].update_one({"sessionId": sid}, {"$set": {"lastSeenAt": datetime.utcnow()}})

    return payload


def household_id_for(db, user: dict) -> str:
    """Resolve the caller's household id. Bundles/plans are scoped per household
    so members share a plan and households never see each other's. ``db`` is
    passed in so the caller's (test-patchable) connection is used."""
    doc = db["users"].find_one({"userId": user["sub"]}, {"householdId": 1})
    hid = (doc or {}).get("householdId")
    if not hid:
        raise HTTPException(status_code=400, detail="User has no household")
    return hid
