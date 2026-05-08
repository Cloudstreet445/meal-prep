"""Household settings endpoints."""

from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel
from ..database import get_db

router = APIRouter()

_DEFAULTS = {"budget": 60.0, "serves": 2, "exclusions": []}


class SettingsIn(BaseModel):
    budget: Optional[float] = None
    serves: Optional[int] = None
    exclusions: Optional[List[str]] = None


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
