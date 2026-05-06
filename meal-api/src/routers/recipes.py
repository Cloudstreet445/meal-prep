"""Recipe endpoints."""

from fastapi import APIRouter, HTTPException
from ..database import get_db

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