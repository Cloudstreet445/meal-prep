"""Recipe endpoints."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from ..database import get_db
from ..auth_utils import require_user
from ..limiter import limiter as _limiter


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
@_limiter.limit("30/minute")
def rate_recipe(recipe_id: str, body: RatingIn, request: Request, user: dict = Depends(require_user)):
    """Rate a recipe (👍/👎). Auth required, and each user has at most one
    rating per recipe — re-rating overwrites the previous score rather than
    stacking. This prevents anonymous mass-downvoting from poisoning plan
    generation (👎 recipes are excluded for the rating user)."""
    if body.score not in (1, -1):
        raise HTTPException(status_code=422, detail="score must be 1 or -1")
    user_id = user["sub"]
    db = get_db()

    if db["recipes"].count_documents({"recipeId": recipe_id}, limit=1) == 0:
        raise HTTPException(status_code=404, detail=f"Recipe {recipe_id} not found")

    today = datetime.now().strftime("%Y-%m-%d")
    # One rating per user: update in place if they've rated before…
    updated = db["recipes"].update_one(
        {"recipeId": recipe_id, "ratings.userId": user_id},
        {"$set": {"ratings.$.score": body.score, "ratings.$.date": today}},
    )
    if updated.matched_count == 0:
        # …otherwise append their first rating.
        db["recipes"].update_one(
            {"recipeId": recipe_id},
            {"$push": {"ratings": {"userId": user_id, "score": body.score, "date": today}}},
        )
    return {"ok": True}