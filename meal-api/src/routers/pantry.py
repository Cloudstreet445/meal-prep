"""Per-user server-side pantry endpoints."""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from ..database import get_db
from ..auth_utils import require_user, get_current_user
from ..sanitize import clean_text
from ..meal_themes import pantry_suggestions_for
from .helpers import _normalise_name
from .settings import effective_settings

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


class PantryBulkIn(BaseModel):
    items: List[PantryItemIn] = Field(..., max_length=100)


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


@router.get("/suggestions")
def pantry_suggestions(request: Request, themes: Optional[str] = Query(default=None)):
    """Staple pantry items implied by the household's meal themes.

    ``themes`` (comma-separated) overrides the saved setting — used during
    onboarding before the choice is persisted. Each suggestion is flagged
    ``inPantry`` (fuzzy match) so the UI can pre-tick what's already owned.
    """
    db = get_db()
    user = get_current_user(request)
    if themes is not None:
        chosen = [t for t in themes.split(",") if t.strip()]
    else:
        chosen = effective_settings(db, user).get("mealThemes", [])

    owned = set()
    if user:
        owned = {
            _normalise_name(i.get("canonical") or i.get("name") or "")
            for i in db["user_pantry"].find({"userId": user["sub"]}, {"canonical": 1, "name": 1})
        }

    suggestions = []
    for s in pantry_suggestions_for(chosen):
        key = _normalise_name(s["canonical"])
        s["inPantry"] = any(o and (o in key or key in o) for o in owned)
        suggestions.append(s)
    return {"themes": chosen, "suggestions": suggestions}


@router.post("/bulk")
def add_pantry_items(body: PantryBulkIn, user: dict = Depends(require_user)):
    """Add several pantry items at once (skipping any already present).

    Used when a user confirms theme-suggested staples in one tap."""
    db = get_db()
    existing = {
        i["canonical"] for i in
        db["user_pantry"].find({"userId": user["sub"]}, {"canonical": 1})
    }
    docs = []
    for item in body.items:
        canonical = clean_text(item.canonical)
        if not canonical or canonical in existing:
            continue
        existing.add(canonical)
        docs.append({
            "userId": user["sub"],
            "name": clean_text(item.name),
            "canonical": canonical,
            "quantity": clean_text(item.quantity) or None,
            "category": clean_text(item.category) or None,
            "expiryDate": clean_text(item.expiryDate) or None,
            "addedAt": datetime.utcnow().isoformat(),
        })
    if docs:
        db["user_pantry"].insert_many(docs)
    return {"added": len(docs)}


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
