"""Auth endpoints — password auth, sessions, password reset, magic link (legacy)."""

import os
import re
import uuid
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, Request, Query
from pydantic import BaseModel
from passlib.context import CryptContext
from ..database import get_db
from ..auth_utils import create_jwt, decode_jwt, get_current_user, require_user
from ..limiter import limiter as _limiter

router = APIRouter()

MAGIC_TOKEN_TTL_MINUTES = 30
RESET_TOKEN_TTL_HOURS = 1
SESSION_TTL_DAYS = 30
APP_URL = os.getenv("APP_URL", "http://localhost:3000")
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ── Pydantic models ────────────────────────────────────────────────

class EmailRequest(BaseModel):
    email: str

class PasswordAuthRequest(BaseModel):
    email: str
    password: str

class ResetPasswordRequest(BaseModel):
    token: str
    password: str


# ── Internal helpers ───────────────────────────────────────────────

def _send_email(to: str, subject: str, body: str):
    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        print(f"[AUTH] Email to {to}:\n  Subject: {subject}\n  {body[:200]}")
        return
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASS", "")
    from_addr = os.getenv("SMTP_FROM", user)
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    with smtplib.SMTP(smtp_host, port) as s:
        if port != 465:
            s.starttls()
        if user:
            s.login(user, password)
        s.sendmail(from_addr, [to], msg.as_string())


def _create_user_and_household(db, email: str) -> tuple[str, str]:
    user_id = str(uuid.uuid4())
    household_id = str(uuid.uuid4())
    now = datetime.utcnow()
    db["users"].insert_one({
        "userId": user_id,
        "email": email,
        "createdAt": now,
        "householdId": household_id,
        "lastLoginAt": now,
        "isNewUser": True,
    })
    db["households"].insert_one({
        "householdId": household_id,
        "name": email.split("@")[0].title() + "'s Household",
        "createdBy": user_id,
        "members": [{"userId": user_id, "role": "owner", "joinedAt": now}],
        "settings": {"budget": 60.0, "serves": 2, "storeId": "paknsave-lower-hutt"},
        "createdAt": now,
    })
    return user_id, household_id


def _create_session(db, user_id: str, request: Request) -> str:
    session_id = str(uuid.uuid4())
    ua = request.headers.get("user-agent", "Unknown Device")
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "Unknown")
    now = datetime.utcnow()
    db["sessions"].insert_one({
        "sessionId": session_id,
        "userId": user_id,
        "userAgent": ua,
        "ipAddress": ip,
        "createdAt": now,
        "lastSeenAt": now,
        "expiresAt": now + timedelta(days=SESSION_TTL_DAYS),
    })
    return session_id


def _set_auth_cookie(response: Response, user_id: str, email: str, session_id: str):
    token = create_jwt(user_id, email, session_id)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_TTL_DAYS * 86400,
        path="/",
    )
    return token


# ── Register ───────────────────────────────────────────────────────

@router.post("/register")
@_limiter.limit("3/minute")
def register(body: PasswordAuthRequest, response: Response, request: Request):
    email = body.email.lower().strip()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Invalid email address")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    db = get_db()
    if db["users"].find_one({"email": email}):
        raise HTTPException(409, "An account with that email already exists")

    user_id, household_id = _create_user_and_household(db, email)
    db["users"].update_one({"userId": user_id}, {"$set": {"passwordHash": _pwd.hash(body.password)}})

    session_id = _create_session(db, user_id, request)
    _set_auth_cookie(response, user_id, email, session_id)
    return {"ok": True, "userId": user_id, "email": email, "isNewUser": True,
            "householdId": household_id, "sessionId": session_id}


# ── Login ──────────────────────────────────────────────────────────

@router.post("/login")
@_limiter.limit("5/minute")
def login(body: PasswordAuthRequest, response: Response, request: Request):
    email = body.email.lower().strip()
    db = get_db()
    user = db["users"].find_one({"email": email})

    if not user or not user.get("passwordHash") or not _pwd.verify(body.password, user["passwordHash"]):
        raise HTTPException(401, "Invalid email or password")

    db["users"].update_one({"email": email}, {"$set": {"lastLoginAt": datetime.utcnow()}})
    session_id = _create_session(db, user["userId"], request)
    _set_auth_cookie(response, user["userId"], email, session_id)
    return {"ok": True, "userId": user["userId"], "email": email, "isNewUser": False,
            "householdId": user.get("householdId"), "sessionId": session_id}


# ── Forgot / Reset password ────────────────────────────────────────

@router.post("/forgot-password")
@_limiter.limit("3/minute")
def forgot_password(body: EmailRequest, request: Request):
    email = body.email.lower().strip()
    db = get_db()
    user = db["users"].find_one({"email": email}, {"userId": 1})
    if user:
        token = str(uuid.uuid4())
        db["password_reset_tokens"].insert_one({
            "token": token,
            "userId": user["userId"],
            "email": email,
            "expiresAt": datetime.utcnow() + timedelta(hours=RESET_TOKEN_TTL_HOURS),
            "used": False,
        })
        link = f"{APP_URL}/reset-password?token={token}"
        try:
            _send_email(
                email,
                "Reset your Kai Planner password",
                f"Hi,\n\nClick the link below to reset your password:\n\n{link}\n\n"
                "This link expires in 1 hour. If you didn't request this, ignore it.",
            )
        except Exception as exc:
            print(f"[AUTH] Reset email failed ({exc}); link: {link}")
    # Always return 200 — no user enumeration
    return {"sent": True}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, response: Response, request: Request):
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    db = get_db()
    doc = db["password_reset_tokens"].find_one({"token": body.token, "used": False})
    if not doc or doc["expiresAt"] < datetime.utcnow():
        raise HTTPException(400, "Invalid or expired reset link")

    db["password_reset_tokens"].update_one({"token": body.token}, {"$set": {"used": True}})
    db["users"].update_one({"userId": doc["userId"]}, {"$set": {"passwordHash": _pwd.hash(body.password)}})
    db["sessions"].delete_many({"userId": doc["userId"]})

    session_id = _create_session(db, doc["userId"], request)
    _set_auth_cookie(response, doc["userId"], doc["email"], session_id)
    return {"ok": True, "email": doc["email"]}


# ── Sessions ───────────────────────────────────────────────────────

@router.get("/sessions")
def list_sessions(user: dict = Depends(require_user)):
    db = get_db()
    docs = list(db["sessions"].find(
        {"userId": user["sub"]},
        {"_id": 0, "sessionId": 1, "userAgent": 1, "ipAddress": 1, "createdAt": 1, "lastSeenAt": 1}
    ).sort("createdAt", -1))
    current_sid = user.get("sid")
    for s in docs:
        s["isCurrent"] = s["sessionId"] == current_sid
        for key in ("createdAt", "lastSeenAt"):
            if hasattr(s.get(key), "isoformat"):
                s[key] = s[key].isoformat()
    return docs


@router.delete("/sessions")
def revoke_all_sessions(response: Response, user: dict = Depends(require_user)):
    """Log out of all devices."""
    db = get_db()
    db["sessions"].delete_many({"userId": user["sub"]})
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: str, user: dict = Depends(require_user)):
    """Revoke a specific session by ID."""
    db = get_db()
    result = db["sessions"].delete_one({"sessionId": session_id, "userId": user["sub"]})
    if result.deleted_count == 0:
        raise HTTPException(404, "Session not found")
    return {"ok": True}


# ── Me / Logout ────────────────────────────────────────────────────

@router.get("/me")
def get_me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    db = get_db()
    user_doc = db["users"].find_one(
        {"userId": user["sub"]},
        {"_id": 0, "userId": 1, "email": 1, "householdId": 1}
    )
    if not user_doc:
        raise HTTPException(401, "User not found")
    return {**user_doc, "sessionId": user.get("sid")}


@router.post("/logout")
def logout(request: Request, response: Response):
    response.delete_cookie("access_token", path="/")
    token = request.cookies.get("access_token")
    if token:
        payload = decode_jwt(token)
        if payload and payload.get("sid"):
            get_db()["sessions"].delete_one({"sessionId": payload["sid"]})
    return {"ok": True}


# ── Magic link (legacy — kept for Android deep link compatibility) ──

@router.post("/send-magic-link")
def send_magic_link(body: EmailRequest):
    email = body.email.lower().strip()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Invalid email address")
    db = get_db()
    token = str(uuid.uuid4())
    db["magic_tokens"].insert_one({
        "token": token,
        "email": email,
        "expiresAt": datetime.utcnow() + timedelta(minutes=MAGIC_TOKEN_TTL_MINUTES),
        "used": False,
    })
    link = f"{APP_URL}/?auth_token={token}"
    try:
        _send_email(email, "Your Kai Planner login link",
                    f"Hi,\n\nClick the link below to sign in:\n\n{link}\n\n"
                    "This link expires in 30 minutes. If you didn't request this, ignore it.")
    except Exception as exc:
        print(f"[AUTH] Email send failed ({exc}); link: {link}")
    return {"sent": True, "email": email}


@router.get("/verify")
def verify_magic_link(token: str = Query(...), response: Response = None, request: Request = None):
    db = get_db()
    doc = db["magic_tokens"].find_one({"token": token, "used": False})
    if not doc or doc["expiresAt"] < datetime.utcnow():
        raise HTTPException(400, "Invalid or expired login link")

    db["magic_tokens"].update_one({"token": token}, {"$set": {"used": True}})

    email = doc["email"]
    user = db["users"].find_one({"email": email})
    if not user:
        user_id, household_id = _create_user_and_household(db, email)
    else:
        user_id = user["userId"]
        household_id = user.get("householdId")
        db["users"].update_one({"email": email}, {"$set": {"lastLoginAt": datetime.utcnow()}})

    session_id = _create_session(db, user_id, request)
    _set_auth_cookie(response, user_id, email, session_id)

    is_new = not user
    return {"ok": True, "userId": user_id, "email": email, "isNewUser": is_new,
            "householdId": household_id, "sessionId": session_id}
