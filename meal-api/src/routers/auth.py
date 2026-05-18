"""Auth endpoints — magic link + JWT session."""

import os
import uuid
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Response, Request, Query
from pydantic import BaseModel
from ..database import get_db
from ..auth_utils import create_jwt, get_current_user

router = APIRouter()

MAGIC_TOKEN_TTL_MINUTES = 30
APP_URL = os.getenv("APP_URL", "http://192.168.1.85:3000")


class MagicLinkRequest(BaseModel):
    email: str


def _send_magic_link(email: str, link: str):
    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        print(f"[AUTH] Magic link for {email}:\n  {link}")
        return
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASS", "")
    from_addr = os.getenv("SMTP_FROM", user)
    msg = MIMEText(
        f"Hi,\n\nClick the link below to sign in to Kai Planner:\n\n{link}\n\n"
        "This link expires in 30 minutes. If you didn't request this, ignore it."
    )
    msg["Subject"] = "Your Kai Planner login link"
    msg["From"] = from_addr
    msg["To"] = email
    with smtplib.SMTP(smtp_host, port) as s:
        if port != 465:
            s.starttls()
        if user:
            s.login(user, password)
        s.sendmail(from_addr, [email], msg.as_string())


@router.post("/send-magic-link")
def send_magic_link(body: MagicLinkRequest):
    email = body.email.lower().strip()
    if not email or "@" not in email:
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
        _send_magic_link(email, link)
    except Exception as exc:
        print(f"[AUTH] Email send failed ({exc}); link: {link}")

    return {"sent": True, "email": email}


@router.get("/verify")
def verify_magic_link(token: str = Query(...), response: Response = None):
    db = get_db()
    doc = db["magic_tokens"].find_one({"token": token, "used": False})

    if not doc or doc["expiresAt"] < datetime.utcnow():
        raise HTTPException(400, "Invalid or expired login link")

    db["magic_tokens"].update_one({"token": token}, {"$set": {"used": True}})

    email = doc["email"]
    user = db["users"].find_one({"email": email})
    if not user:
        user_id = str(uuid.uuid4())
        now = datetime.utcnow()
        household_id = str(uuid.uuid4())
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
    else:
        user_id = user["userId"]
        household_id = user.get("householdId")
        db["users"].update_one({"email": email}, {"$set": {"lastLoginAt": datetime.utcnow()}})

    jwt_token = create_jwt(user_id, email)
    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        samesite="lax",
        max_age=30 * 86400,
        path="/",
    )

    is_new = not user
    return {"ok": True, "userId": user_id, "email": email, "isNewUser": is_new, "householdId": household_id}


@router.get("/me")
def get_me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    db = get_db()
    user_doc = db["users"].find_one({"userId": user["sub"]}, {"_id": 0, "userId": 1, "email": 1, "householdId": 1})
    if not user_doc:
        raise HTTPException(401, "User not found")
    return user_doc


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}
