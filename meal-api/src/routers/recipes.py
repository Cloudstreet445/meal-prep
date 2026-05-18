"""Recipe endpoints."""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from ..database import get_db
from ..auth_utils import get_current_user


class RatingIn(BaseModel):
    score: int  # 1 (thumbs up) or -1 (thumbs down)

router = APIRouter()


def _clean(doc) -> dict:
    if not doc:
        return {}
    doc["_id"] = str(doc["_id"])
    for key, val in doc.items():
        if hasattr(val, "isoformat"):
            doc[key] = val.isoformat()
    return doc


@router.get("/")
def list_recipes(week: str = None, bundle: str = None):
    """List recipes, optionally filtered by week or bundle."""
    db = get_db()
    filter_dict = {}
    if week:
        filter_dict["usageHistory"] = week
    if bundle:
        filter_dict["bundleHistory"] = bundle
    docs = list(db["recipes"].find(filter_dict).sort("name", 1))
    return [_clean(doc) for doc in docs]


@router.get("/{recipe_id}")
def get_recipe(recipe_id: str):
    """Get a single recipe by recipeId."""
    db = get_db()
    doc = db["recipes"].find_one({"recipeId": recipe_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Recipe {recipe_id} not found")
    return _clean(doc)


@router.post("/{recipe_id}/rate")
def rate_recipe(recipe_id: str, body: RatingIn, request: Request):
    """Add a rating to a recipe. Scoped to the authenticated user if available."""
    if body.score not in (1, -1):
        raise HTTPException(status_code=422, detail="score must be 1 or -1")
    user = get_current_user(request)
    user_id = user["sub"] if user else "default"
    db = get_db()
    result = db["recipes"].update_one(
        {"recipeId": recipe_id},
        {"$push": {"ratings": {
            "userId": user_id,
            "score": body.score,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=f"Recipe {recipe_id} not found")
    return {"ok": True}