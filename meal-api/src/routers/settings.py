"""Household settings endpoints."""

from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel
from ..database import get_db, get_pricing_db

router = APIRouter()

_DEFAULTS = {"budget": 60.0, "serves": 2, "exclusions": [], "storeId": "paknsave-lower-hutt"}


class SettingsIn(BaseModel):
    budget: Optional[float] = None
    serves: Optional[int] = None
    exclusions: Optional[List[str]] = None
    storeId: Optional[str] = None


@router.get("/")
def get_settings():
    """Return current settings, merged with defaults for any missing fields."""
    db = get_db()
    doc = db["settings"].find_one({"key": "default"}, {"_id": 0, "key": 0})
    return {**_DEFAULTS, **(doc or {})}


@router.put("/")
def update_settings(body: SettingsIn):
    """Partial-update household settings. Returns the full settings after save."""
    updates = body.model_dump(exclude_none=True)
    if updates:
        db = get_db()
        db["settings"].update_one(
            {"key": "default"},
            {"$set": updates},
            upsert=True,
        )
    return get_settings()


@router.get("/stores")
def list_stores():
    """Return store IDs that have pricing data in the database."""
    pricing_db = get_pricing_db()
    pipeline = [
        {"$project": {"stores": {"$objectToArray": "$storePrice"}}},
        {"$unwind": "$stores"},
        {"$group": {"_id": "$stores.k"}},
        {"$sort": {"_id": 1}},
    ]
    result = list(pricing_db["products"].aggregate(pipeline))
    return [r["_id"] for r in result]
