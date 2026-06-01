"""Plan endpoints — library-first generation."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db, get_pricing_db
from ..auth_utils import require_user, household_id_for
from .helpers import _select_from_library, _derive_shopping_list, _pantry_keys
from .settings import effective_settings
from .bundles import get_latest_bundle

router = APIRouter()


@router.get("/latest")
def get_latest_plan(user: dict = Depends(require_user)):
    """Legacy alias for /api/bundle/latest."""
    return get_latest_bundle(user)


@router.post("/generate")
def generate_plan(user: dict = Depends(require_user)):
    """Generate a new meal plan from the recipe library."""
    db         = get_db()
    pricing_db = get_pricing_db()
    hid        = household_id_for(db, user)

    # Use THIS user's saved settings (budget / exclusions / store), not the
    # shared anonymous default. Without this, onboarding choices are ignored.
    settings   = effective_settings(db, user)
    budget     = float(settings.get("budget", 60))
    exclusions = settings.get("exclusions", [])
    store_id   = settings.get("storeId", "paknsave-lower-hutt")
    serves     = settings.get("serves")
    diet_tags  = settings.get("dietTags", [])

    # Exclude this household's current active bundle's recipes (no repeats)
    active      = db["bundles"].find_one({"active": True, "householdId": hid}, sort=[("week", -1), ("createdAt", -1)])
    exclude_ids = set(active.get("recipeIds", [])) if active else set()

    # Aim for 5 meals but degrade gracefully to as few as 3 on a tight budget
    # rather than failing outright.
    selected = _select_from_library(
        db, budget, exclusions, exclude_ids,
        n=5, min_n=3,
        user_id=user.get("sub"), pricing_db=pricing_db, store_id=store_id,
        serves=serves, diet_tags=diet_tags,
    )

    if selected is None:
        raise HTTPException(
            status_code=422,
            detail="Couldn't build a plan within your budget. Try raising your budget, relaxing exclusions/diet filters, or adding more recipes.",
        )

    # Build a bundle from the selected recipes. The stored estimatedTotal must
    # match what the Shopping tab and week card show, so compute it the same
    # way: one deduplicated list across all meals, pantry items excluded — NOT
    # the sum of per-recipe costs (which double-counts shared ingredients).
    recipe_ids = [r["recipeId"] for r in selected]
    _, total = _derive_shopping_list(
        selected, pricing_db, store_id,
        serves=serves,
        pantry=_pantry_keys(db, user),
    )

    names        = [r["name"] for r in selected]
    week_summary = ", ".join(names[:3]) + (f" + {len(names) - 3} more" if len(names) > 3 else "")

    week_id   = datetime.utcnow().strftime("%Y-%m-%d")
    bundle_id = f"auto-{uuid.uuid4().hex[:8]}"
    now       = datetime.utcnow()

    db["bundles"].update_many({"week": week_id, "householdId": hid}, {"$set": {"active": False}})
    db["bundles"].insert_one({
        "bundleId":          bundle_id,
        "householdId":       hid,
        "week":              week_id,
        "active":            True,
        "recipeIds":         recipe_ids,
        "weekSummary":       week_summary,
        "estimatedTotal":    total,
        "generatedBy":       "library",
        "storeId":           store_id,
        "serves":            serves,
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
        # True when the budget was too tight for a full 5-meal week
        "degraded":    len(selected) < 5,
    }
