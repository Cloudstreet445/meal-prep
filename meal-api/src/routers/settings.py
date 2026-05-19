"""Household settings endpoints — per-user with anonymous fallback."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from ..database import get_db, get_pricing_db
from ..auth_utils import get_current_user, require_user

router = APIRouter()

DEFAULT_STORE_ID = "paknsave-lower-hutt"
_DEFAULTS = {"budget": 60.0, "serves": 2, "exclusions": [], "storeId": DEFAULT_STORE_ID}


def _settings_key(user: dict | None) -> dict:
    """Return MongoDB filter for the settings doc — per-user if auth, else shared default."""
    if user:
        return {"userId": user["sub"]}
    return {"key": "default"}


def _migrate_defaults(db, user: dict) -> dict:
    """On first per-user access, seed from the shared 'default' doc."""
    default_doc = db["settings"].find_one({"key": "default"}, {"_id": 0, "key": 0}) or {}
    seed = {**_DEFAULTS, **default_doc, "userId": user["sub"]}
    db["settings"].update_one({"userId": user["sub"]}, {"$setOnInsert": seed}, upsert=True)
    return seed


class SettingsIn(BaseModel):
    budget: Optional[float] = Field(None, ge=1, le=10000)
    serves: Optional[int] = Field(None, ge=1, le=20)
    exclusions: Optional[List[str]] = Field(None, max_length=50)
    storeId: Optional[str] = Field(None, max_length=100)


@router.get("/")
def get_settings(request: Request):
    user = get_current_user(request)
    db = get_db()
    if user:
        doc = db["settings"].find_one({"userId": user["sub"]}, {"_id": 0, "userId": 0})
        if not doc:
            doc = _migrate_defaults(db, user)
    else:
        doc = db["settings"].find_one({"key": "default"}, {"_id": 0, "key": 0})
    return {**_DEFAULTS, **(doc or {})}


@router.put("/")
def update_settings(body: SettingsIn, request: Request, user: dict = Depends(require_user)):
    updates = body.model_dump(exclude_none=True)
    if updates:
        db = get_db()
        db["settings"].update_one(
            {"userId": user["sub"]},
            {"$set": updates},
            upsert=True,
        )
    return get_settings(request)


@router.get("/stores")
def list_stores():
    pricing_db = get_pricing_db()
    pipeline = [
        {"$project": {"stores": {"$objectToArray": "$storePrice"}}},
        {"$unwind": "$stores"},
        {"$group": {"_id": "$stores.k"}},
        {"$sort": {"_id": 1}},
    ]
    result = list(pricing_db["products"].aggregate(pipeline))
    return [r["_id"] for r in result]
