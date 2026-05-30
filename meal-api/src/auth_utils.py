"""JWT helpers and FastAPI auth dependencies."""

import os
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
import jwt

import logging as _logging
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    _logging.getLogger(__name__).critical(
        "JWT_SECRET not set — all auth endpoints will fail"
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
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
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
