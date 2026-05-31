"""Per-user server-side pantry endpoints."""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ..database import get_db
from ..auth_utils import require_user
from ..sanitize import clean_text

router = APIRouter()


class PantryItemIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    canonical: str = Field(..., min_length=1, max_length=200)
    quantity: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    expiryDate: Optional[str] = Field(None, max_length=40)


class PantryItemUpdate(BaseModel):
    quantity: Optional[str] = Field(None, max_length=100)
    expiryDate: Optional[str] = Field(None, max_length=40)


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
        # Sanitize stored free text so it can never carry live markup/JS
        # (stored XSS) regardless of which client later renders it.
        "name": clean_text(body.name),
        "canonical": clean_text(body.canonical),
        "quantity": clean_text(body.quantity) or None,
        "category": clean_text(body.category) or None,
        "expiryDate": clean_text(body.expiryDate) or None,
        "addedAt": datetime.utcnow().isoformat(),
    })
    return {"ok": True}


@router.put("/{canonical}")
def update_pantry_item(canonical: str, body: PantryItemUpdate, user: dict = Depends(require_user)):
    db = get_db()
    updates = {k: clean_text(v) for k, v in body.model_dump(exclude_none=True).items()}
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
