"""
Bundle endpoints.

Key design decisions implemented here:
- active flag is scoped PER WEEK (not global)
- sharedWith on shopping list items is computed dynamically
- Shopping list prices are enriched from live paknsave-pricing data
- Route order matters: /history and /latest BEFORE /{bundle_id}
"""

import re
from fastapi import APIRouter, HTTPException, Query
from ..database import get_db, get_pricing_db

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────

def _clean(doc) -> dict:
    if not doc:
        return {}
    doc["_id"] = str(doc["_id"])
    for key, val in doc.items():
        if hasattr(val, "isoformat"):
            doc[key] = val.isoformat()
    return doc


def _clean_list(docs) -> list:
    return [_clean(doc) for doc in docs]


def _normalise_name(name: str) -> str:
    """Normalise ingredient name for deduplication matching."""
    return re.sub(r'[^a-z0-9]', '', name.lower())


def _enrich_ingredient(item: dict, pricing_db, store_id: str) -> dict:
    """
    Try to match an ingredient name against paknsave-pricing products.
    Attaches isSpecial and currentPrice from the store-specific storePrice entry.
    """
    name = item.get("name", "")
    words = [w for w in re.split(r'\W+', name.lower()) if len(w) > 2]

    if not words:
        return item

    pattern = "|".join(re.escape(w) for w in words[:3])
    product = pricing_db["products"].find_one(
        {
            "name": {"$regex": pattern, "$options": "i"},
            f"storePrice.{store_id}": {"$exists": True},
        },
        {"name": 1, f"storePrice.{store_id}.currentPrice": 1, f"storePrice.{store_id}.isSpecial": 1}
    )

    if product:
        store_data = product.get("storePrice", {}).get(store_id, {})
        item["isSpecial"]     = store_data.get("isSpecial", False)
        item["currentPrice"]  = store_data.get("currentPrice")
        item["matchedProduct"] = product.get("name")

    return item


def _derive_shopping_list(recipes: list, pricing_db, store_id: str = "paknsave-lower-hutt") -> tuple[list, float]:
    """
    Derive a deduplicated shopping list from a list of recipe documents.

    - Deduplicates by normalised ingredient name
    - Computes sharedWith dynamically (ingredients used in >1 recipe)
    - Enriches with live prices from paknsave-pricing for the given store
    - Returns (shopping_items, total)
    """
    # Map: normalised_name → aggregated item
    ingredient_map: dict[str, dict] = {}

    for recipe in recipes:
        recipe_id = recipe.get("recipeId", recipe.get("_id", ""))
        recipe_name = recipe.get("name", "")

        for ing in recipe.get("ingredients", []):
            key = _normalise_name(ing.get("name", ""))
            if not key:
                continue

            if key not in ingredient_map:
                ingredient_map[key] = {
                    "name":          ing.get("name"),
                    "amount":        ing.get("amount", ""),
                    "estimatedCost": ing.get("estimatedCost", 0),
                    "fromSpecial":   ing.get("fromSpecial", False),
                    "isSpecial":     False,
                    "currentPrice":  None,
                    "usedIn":        [],          # recipeIds
                    "usedInNames":   [],          # human-readable names
                    "category":      _guess_category(ing.get("name", "")),
                }
            else:
                # Sum cost for shared ingredient
                ingredient_map[key]["estimatedCost"] += ing.get("estimatedCost", 0)
                if ing.get("fromSpecial"):
                    ingredient_map[key]["fromSpecial"] = True

            # Track which recipes use this ingredient
            if recipe_id not in ingredient_map[key]["usedIn"]:
                ingredient_map[key]["usedIn"].append(recipe_id)
                ingredient_map[key]["usedInNames"].append(recipe_name)

    # Enrich with live prices and compute sharedWith
    items = []
    for item in ingredient_map.values():
        # Enrich with live pricing
        enriched = _enrich_ingredient(item, pricing_db, store_id)

        # sharedWith = list of recipe names where more than one recipe uses this ingredient
        enriched["sharedWith"] = enriched["usedInNames"] if len(enriched["usedIn"]) > 1 else []
        enriched["estimatedCost"] = round(enriched["estimatedCost"], 2)

        items.append(enriched)

    # Sort: proteins → vegetables → pantry → dairy → other
    category_order = {"protein": 0, "vegetable": 1, "pantry": 2, "dairy": 3, "other": 4}
    items.sort(key=lambda x: category_order.get(x.get("category", "other"), 4))

    total = round(sum(i["estimatedCost"] for i in items), 2)
    return items, total


def _guess_category(name: str) -> str:
    """Rough category assignment for sorting."""
    name_lower = name.lower()
    if any(w in name_lower for w in ["chicken", "pork", "beef", "lamb", "mince", "meat"]):
        return "protein"
    if any(w in name_lower for w in ["milk", "cream", "butter", "cheese", "yoghurt"]):
        return "dairy"
    if any(w in name_lower for w in ["onion", "carrot", "potato", "garlic", "capsicum",
                                      "broccoli", "celery", "tomato", "courgette", "leek",
                                      "spinach", "cabbage", "pumpkin"]):
        return "vegetable"
    if any(w in name_lower for w in ["pasta", "rice", "noodle", "flour", "oil", "sauce",
                                      "stock", "can", "tin", "bean", "lentil", "spice",
                                      "salt", "pepper", "soy", "vinegar"]):
        return "pantry"
    return "other"


def _get_bundle_with_recipes(bundle: dict, db, pricing_db) -> dict:
    """
    Given a bundle document, fetch its recipes and attach them.
    Returns the enriched bundle dict.
    """
    recipe_ids = bundle.get("recipeIds", [])
    recipes = list(db["recipes"].find(
        {"recipeId": {"$in": recipe_ids}}
    ))

    # Preserve recipeIds order
    recipe_map = {r["recipeId"]: _clean(r) for r in recipes}
    ordered_recipes = [recipe_map[rid] for rid in recipe_ids if rid in recipe_map]

    bundle["recipes"] = ordered_recipes
    return bundle


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
    return _get_bundle_with_recipes(bundle, db, pricing_db)


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
def activate_bundle(bundle_id: str):
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
def refresh_bundle_prices(bundle_id: str, store_id: str = Query(default="paknsave-lower-hutt")):
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