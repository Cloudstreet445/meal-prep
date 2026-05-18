"""Per-user server-side pantry endpoints."""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..database import get_db
from ..auth_utils import require_user

router = APIRouter()


class PantryItemIn(BaseModel):
    name: str
    canonical: str
    quantity: Optional[str] = None
    category: Optional[str] = None
    expiryDate: Optional[str] = None


class PantryItemUpdate(BaseModel):
    quantity: Optional[str] = None
    expiryDate: Optional[str] = None


@router.get("/")
def get_pantry(user: dict = Depends(require_user)):
    db = get_db()
    items = list(db["user_pantry"].find(
        {"userId": user["sub"]},
        {"_id": 0, "userId": 0},
    ))
    return items


@router.post("/")
def add_pantry_item(body: PantryItemIn, user: dict = Depends(require_user)):
    db = get_db()
    existing = db["user_pantry"].find_one({"userId": user["sub"], "canonical": body.canonical})
    if existing:
        raise HTTPException(409, "Item already in pantry")
    db["user_pantry"].insert_one({
        "userId": user["sub"],
        "name": body.name,
        "canonical": body.canonical,
        "quantity": body.quantity,
        "category": body.category,
        "expiryDate": body.expiryDate,
        "addedAt": datetime.utcnow().isoformat(),
    })
    return {"ok": True}


@router.put("/{canonical}")
def update_pantry_item(canonical: str, body: PantryItemUpdate, user: dict = Depends(require_user)):
    db = get_db()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "Nothing to update")
    result = db["user_pantry"].update_one(
        {"userId": user["sub"], "canonical": canonical},
        {"$set": updates},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Item not found")
    return {"ok": True}


@router.delete("/{canonical}")
def delete_pantry_item(canonical: str, user: dict = Depends(require_user)):
    db = get_db()
    result = db["user_pantry"].delete_one({"userId": user["sub"], "canonical": canonical})
    if result.deleted_count == 0:
        raise HTTPException(404, "Item not found")
    return {"ok": True}
