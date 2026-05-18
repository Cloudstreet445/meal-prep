"""JWT helpers and FastAPI auth dependencies."""

import os
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30


def create_jwt(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def get_current_user(request: Request) -> dict | None:
    """Return user payload from JWT cookie, or None if unauthenticated."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    return decode_jwt(token)


def require_user(request: Request) -> dict:
    """FastAPI dependency — raises 401 if not authenticated."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user
