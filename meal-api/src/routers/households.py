"""Household management endpoints."""

import uuid
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..database import get_db
from ..auth_utils import require_user

router = APIRouter()

INVITE_TTL_HOURS = 48


@router.get("/")
def get_household(user: dict = Depends(require_user)):
    db = get_db()
    user_doc = db["users"].find_one({"userId": user["sub"]}, {"householdId": 1})
    if not user_doc or not user_doc.get("householdId"):
        raise HTTPException(404, "No household found")
    household = db["households"].find_one(
        {"householdId": user_doc["householdId"]},
        {"_id": 0},
    )
    if not household:
        raise HTTPException(404, "Household not found")

    # Enrich members with email addresses
    member_ids = [m["userId"] for m in household.get("members", [])]
    email_map = {
        u["userId"]: u["email"]
        for u in db["users"].find(
            {"userId": {"$in": member_ids}},
            {"userId": 1, "email": 1, "_id": 0},
        )
    }
    household["members"] = [
        {**m, "email": email_map.get(m["userId"], "")}
        for m in household.get("members", [])
    ]
    return household


class HouseholdUpdate(BaseModel):
    name: Optional[str] = None


@router.put("/")
def update_household(body: HouseholdUpdate, user: dict = Depends(require_user)):
    db = get_db()
    user_doc = db["users"].find_one({"userId": user["sub"]}, {"householdId": 1})
    household_id = user_doc and user_doc.get("householdId")
    if not household_id:
        raise HTTPException(404, "No household")
    household = db["households"].find_one({"householdId": household_id}, {"createdBy": 1})
    if not household or household["createdBy"] != user["sub"]:
        raise HTTPException(403, "Only the household owner can update settings")
    updates = body.model_dump(exclude_none=True)
    if updates:
        db["households"].update_one({"householdId": household_id}, {"$set": updates})
    return {"ok": True}


@router.get("/invite")
def create_invite(user: dict = Depends(require_user)):
    db = get_db()
    user_doc = db["users"].find_one({"userId": user["sub"]}, {"householdId": 1})
    household_id = user_doc and user_doc.get("householdId")
    if not household_id:
        raise HTTPException(404, "No household")
    token = str(uuid.uuid4())
    db["household_invites"].insert_one({
        "token": token,
        "householdId": household_id,
        "createdBy": user["sub"],
        "expiresAt": datetime.utcnow() + timedelta(hours=INVITE_TTL_HOURS),
        "used": False,
    })
    return {"token": token, "expiresInHours": INVITE_TTL_HOURS}


@router.post("/join")
def join_household(token: str, user: dict = Depends(require_user)):
    db = get_db()
    invite = db["household_invites"].find_one({"token": token, "used": False})
    if not invite or invite["expiresAt"] < datetime.utcnow():
        raise HTTPException(400, "Invalid or expired invite link")

    user_id = user["sub"]
    household_id = invite["householdId"]

    # Check user isn't already a member
    household = db["households"].find_one({"householdId": household_id})
    if not household:
        raise HTTPException(404, "Household not found")

    already_member = any(m["userId"] == user_id for m in household.get("members", []))
    if not already_member:
        db["households"].update_one(
            {"householdId": household_id},
            {"$push": {"members": {"userId": user_id, "role": "member", "joinedAt": datetime.utcnow()}}},
        )
        db["users"].update_one({"userId": user_id}, {"$set": {"householdId": household_id}})

    db["household_invites"].update_one({"token": token}, {"$set": {"used": True}})
    return {"ok": True, "householdId": household_id}


@router.delete("/members/{member_id}")
def remove_member(member_id: str, user: dict = Depends(require_user)):
    db = get_db()
    user_doc = db["users"].find_one({"userId": user["sub"]}, {"householdId": 1})
    household_id = user_doc and user_doc.get("householdId")
    if not household_id:
        raise HTTPException(404, "No household")
    household = db["households"].find_one({"householdId": household_id}, {"createdBy": 1})
    if not household:
        raise HTTPException(404, "Household not found")
    if household["createdBy"] != user["sub"] and member_id != user["sub"]:
        raise HTTPException(403, "Only the owner can remove members")
    if member_id == household["createdBy"]:
        raise HTTPException(400, "Household owner cannot be removed")
    db["households"].update_one(
        {"householdId": household_id},
        {"$pull": {"members": {"userId": member_id}}},
    )
    db["users"].update_one({"userId": member_id}, {"$set": {"householdId": None}})
    return {"ok": True}
