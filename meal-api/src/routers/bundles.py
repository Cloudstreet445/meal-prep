"""Bundle endpoints — route handlers only. Helpers live in helpers.py."""

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from ..database import get_db, get_pricing_db
from ..auth_utils import require_user
from .helpers import _clean, _clean_list, _derive_shopping_list, _get_bundle_with_recipes

router = APIRouter()


class CustomBundleIn(BaseModel):
    recipeIds: List[str]
    week: str  # YYYY-MM-DD


# ══════════════════════════════════════════════════════════════════
# ROUTES — order matters! specific paths before /{bundle_id}
# ══════════════════════════════════════════════════════════════════

@router.get("/latest")
def get_latest_bundle():
    """
    Get the active bundle for the most recent week, with full recipes.
    """
    db = get_db()
    pricing_db = get_pricing_db()

    # Find most recent week's active bundle
    doc = db["bundles"].find_one(
        {"active": True},
        sort=[("week", -1), ("createdAt", -1)]
    )
    if not doc:
        raise HTTPException(status_code=404, detail="No active bundles found")

    bundle = _clean(doc)
    bundle = _get_bundle_with_recipes(bundle, db, pricing_db)
    # Recompute total from live recipe data so it matches the shopping list
    _, fresh_total = _derive_shopping_list(bundle["recipes"], pricing_db)
    bundle["estimatedTotal"] = fresh_total
    return bundle


@router.get("/history")
def get_bundle_history():
    """
    List all weeks with their active bundle summary.
    One entry per week, newest first.
    """
    db = get_db()

    pipeline = [
        {"$sort": {"week": -1, "createdAt": -1}},
        {"$group": {
            "_id":            "$week",
            "week":           {"$first": "$week"},
            "activeBundleId": {"$first": {"$cond": ["$active", "$bundleId", None]}},
            "weekSummary":    {"$first": {"$cond": ["$active", "$weekSummary", None]}},
            "estimatedTotal": {"$first": {"$cond": ["$active", "$estimatedTotal", None]}},
            "bundleCount":    {"$sum": 1},
            "priceSnapshotDate": {"$first": {"$cond": ["$active", "$priceSnapshotDate", None]}},
        }},
        {"$sort": {"_id": -1}}
    ]

    weeks = list(db["bundles"].aggregate(pipeline))
    return [
        {
            "week":              w["_id"],
            "activeBundleId":    w.get("activeBundleId"),
            "weekSummary":       w.get("weekSummary"),
            "estimatedTotal":    w.get("estimatedTotal"),
            "bundleCount":       w.get("bundleCount", 1),
            "priceSnapshotDate": w.get("priceSnapshotDate"),
        }
        for w in weeks
    ]


@router.post("/custom")
def create_custom_bundle(body: CustomBundleIn, user: dict = Depends(require_user)):
    """Create a user-defined bundle from a chosen list of recipe IDs."""
    if not body.recipeIds:
        raise HTTPException(status_code=422, detail="recipeIds cannot be empty")

    db = get_db()

    recipes = list(db["recipes"].find({"recipeId": {"$in": body.recipeIds}}))
    found_ids = {r["recipeId"] for r in recipes}
    missing = [rid for rid in body.recipeIds if rid not in found_ids]
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown recipes: {missing}")

    recipe_map = {r["recipeId"]: r for r in recipes}
    ordered = [recipe_map[rid] for rid in body.recipeIds if rid in recipe_map]

    total = round(sum(
        ing.get("estimatedCost", 0)
        for r in ordered
        for ing in r.get("ingredients", [])
    ), 2)

    names = [r["name"] for r in ordered]
    week_summary = ", ".join(names[:3]) + (f" + {len(names) - 3} more" if len(names) > 3 else "")

    bundle_id = f"custom-{uuid.uuid4().hex[:8]}"
    now = datetime.utcnow()

    db["bundles"].update_many({"week": body.week}, {"$set": {"active": False}})
    db["bundles"].insert_one({
        "bundleId":          bundle_id,
        "week":              body.week,
        "active":            True,
        "recipeIds":         body.recipeIds,
        "weekSummary":       week_summary,
        "estimatedTotal":    total,
        "generatedBy":       "user",
        "priceSnapshotDate": now.strftime("%Y-%m-%d"),
        "createdAt":         now,
        "updatedAt":         now,
    })

    for rid in body.recipeIds:
        db["recipes"].update_one(
            {"recipeId": rid},
            {"$addToSet": {"bundleHistory": bundle_id}}
        )

    return {"bundleId": bundle_id, "week": body.week, "estimatedTotal": total}


@router.get("/week/{week_id}")
def get_bundles_for_week(week_id: str):
    """List all bundles for a specific week, newest first."""
    db = get_db()
    docs = list(db["bundles"].find(
        {"week": week_id},
        {"bundleId": 1, "weekSummary": 1, "estimatedTotal": 1,
         "createdAt": 1, "active": 1, "recipeIds": 1, "priceSnapshotDate": 1}
    ).sort("createdAt", -1))

    if not docs:
        raise HTTPException(status_code=404, detail=f"No bundles found for week {week_id}")

    return [_clean(doc) for doc in docs]


@router.get("/{bundle_id}")
def get_bundle(bundle_id: str):
    """Get a specific bundle with full recipe data."""
    db = get_db()
    pricing_db = get_pricing_db()

    doc = db["bundles"].find_one({"bundleId": bundle_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Bundle {bundle_id} not found")

    bundle = _clean(doc)
    return _get_bundle_with_recipes(bundle, db, pricing_db)


@router.get("/{bundle_id}/shopping")
def get_bundle_shopping(bundle_id: str, store_id: str = Query(default="paknsave-lower-hutt")):
    """
    Derive shopping list from bundle's recipes with live prices.
    sharedWith is computed dynamically — never stored.
    """
    db = get_db()
    pricing_db = get_pricing_db()

    doc = db["bundles"].find_one({"bundleId": bundle_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Bundle {bundle_id} not found")

    recipe_ids = doc.get("recipeIds", [])
    recipes = list(db["recipes"].find({"recipeId": {"$in": recipe_ids}}))

    shopping_items, total = _derive_shopping_list(recipes, pricing_db, store_id)

    return {
        "bundleId":      bundle_id,
        "week":          doc.get("week"),
        "weekSummary":   doc.get("weekSummary"),
        "estimatedTotal": total,
        "shoppingList":  shopping_items,
    }


@router.post("/{bundle_id}/activate")
def activate_bundle(bundle_id: str, user: dict = Depends(require_user)):
    """
    Set a bundle as active for its week.
    Only deactivates other bundles for the SAME WEEK.
    Other weeks are untouched.
    """
    db = get_db()

    bundle = db["bundles"].find_one({"bundleId": bundle_id})
    if not bundle:
        raise HTTPException(status_code=404, detail=f"Bundle {bundle_id} not found")

    week_id = bundle["week"]

    # Deactivate all bundles for THIS week only
    db["bundles"].update_many(
        {"week": week_id},
        {"$set": {"active": False}}
    )

    # Activate the chosen bundle
    db["bundles"].update_one(
        {"bundleId": bundle_id},
        {"$set": {"active": True}}
    )

    return {"activated": bundle_id, "week": week_id}


@router.post("/{bundle_id}/refresh-prices")
def refresh_bundle_prices(bundle_id: str, store_id: str = Query(default="paknsave-lower-hutt"), user: dict = Depends(require_user)):
    """
    Recalculate estimatedTotal from current live prices.
    Updates the bundle's estimatedTotal and priceSnapshotDate.
    """
    from datetime import datetime

    db = get_db()
    pricing_db = get_pricing_db()

    doc = db["bundles"].find_one({"bundleId": bundle_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Bundle {bundle_id} not found")

    recipe_ids = doc.get("recipeIds", [])
    recipes = list(db["recipes"].find({"recipeId": {"$in": recipe_ids}}))
    _, new_total = _derive_shopping_list(recipes, pricing_db, store_id)

    db["bundles"].update_one(
        {"bundleId": bundle_id},
        {"$set": {
            "estimatedTotal":    new_total,
            "priceSnapshotDate": datetime.now().strftime("%Y-%m-%d"),
        }}
    )

    return {
        "bundleId":       bundle_id,
        "estimatedTotal": new_total,
        "priceSnapshotDate": datetime.now().strftime("%Y-%m-%d"),
        "message": "Prices refreshed from live data"
    }


class SwapRecipeIn(BaseModel):
    oldRecipeId: str
    newRecipeId: str


@router.post("/{bundle_id}/swap")
def swap_recipe(bundle_id: str, body: SwapRecipeIn, user: dict = Depends(require_user)):
    """Replace one recipe in a bundle without regenerating the whole plan."""
    db = get_db()
    pricing_db = get_pricing_db()

    bundle = db["bundles"].find_one({"bundleId": bundle_id})
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")

    recipe_ids = list(bundle.get("recipeIds", []))
    if body.oldRecipeId not in recipe_ids:
        raise HTTPException(status_code=400, detail="oldRecipeId not in this bundle")

    new_recipe = db["recipes"].find_one({"recipeId": body.newRecipeId})
    if not new_recipe:
        raise HTTPException(status_code=400, detail="newRecipeId not found")

    idx = recipe_ids.index(body.oldRecipeId)
    recipe_ids[idx] = body.newRecipeId

    recipes = list(db["recipes"].find({"recipeId": {"$in": recipe_ids}}))
    _, new_total = _derive_shopping_list(recipes, pricing_db)

    names = [r["name"] for r in recipes if r["recipeId"] in recipe_ids]
    week_summary = ", ".join(names[:3]) + (f" + {len(names) - 3} more" if len(names) > 3 else "")

    now = datetime.utcnow()
    db["bundles"].update_one(
        {"bundleId": bundle_id},
        {"$set": {
            "recipeIds":      recipe_ids,
            "estimatedTotal": new_total,
            "weekSummary":    week_summary,
            "updatedAt":      now,
        }}
    )

    return {"bundleId": bundle_id, "recipeIds": recipe_ids, "estimatedTotal": new_total}