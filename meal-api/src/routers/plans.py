"""Plan endpoints — library-first generation."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db, get_pricing_db
from ..auth_utils import require_user
from .helpers import _select_from_library, _recipe_cost
from .bundles import get_latest_bundle

router = APIRouter()


@router.get("/latest")
def get_latest_plan():
    """Legacy alias for /api/bundle/latest."""
    return get_latest_bundle()


@router.post("/generate")
def generate_plan(user: dict = Depends(require_user)):
    """Generate a new meal plan from the recipe library."""
    db         = get_db()
    pricing_db = get_pricing_db()

    settings   = db["settings"].find_one({"key": "default"}) or {}
    budget     = float(settings.get("budget", 60))
    exclusions = settings.get("exclusions", [])

    # Exclude the current active bundle's recipes so we don't repeat last week
    active      = db["bundles"].find_one({"active": True}, sort=[("week", -1), ("createdAt", -1)])
    exclude_ids = set(active.get("recipeIds", [])) if active else set()

    selected = _select_from_library(db, budget, exclusions, exclude_ids, user_id=user.get("sub"))

    if selected is None:
        raise HTTPException(
            status_code=422,
            detail="Not enough recipes in the library to build a plan. Try relaxing your exclusions or adding more recipes.",
        )

    # Build a bundle from the selected recipes
    recipe_ids = [r["recipeId"] for r in selected]
    total      = round(sum(r["_cost"] for r in selected), 2)

    names        = [r["name"] for r in selected]
    week_summary = ", ".join(names[:3]) + (f" + {len(names) - 3} more" if len(names) > 3 else "")

    week_id   = datetime.utcnow().strftime("%Y-%m-%d")
    bundle_id = f"auto-{uuid.uuid4().hex[:8]}"
    now       = datetime.utcnow()

    db["bundles"].update_many({"week": week_id}, {"$set": {"active": False}})
    db["bundles"].insert_one({
        "bundleId":          bundle_id,
        "week":              week_id,
        "active":            True,
        "recipeIds":         recipe_ids,
        "weekSummary":       week_summary,
        "estimatedTotal":    total,
        "generatedBy":       "library",
        "priceSnapshotDate": now.strftime("%Y-%m-%d"),
        "createdAt":         now,
        "updatedAt":         now,
    })

    db["recipes"].update_many(
        {"recipeId": {"$in": recipe_ids}},
        {"$set": {"lastUsedWeek": week_id}, "$addToSet": {"bundleHistory": bundle_id}},
    )

    return {
        "bundleId":    bundle_id,
        "week":        week_id,
        "recipeCount": len(selected),
        "estimatedTotal": total,
        "source":      "library",
    }
