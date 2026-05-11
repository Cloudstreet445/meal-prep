"""Shopping list endpoints — thin wrapper over bundle shopping derivation."""

from fastapi import APIRouter, HTTPException, Query
from ..database import get_db, get_pricing_db
from .helpers import _derive_shopping_list

router = APIRouter()


@router.get("/latest")
def get_latest_shopping(store_id: str = Query(default="paknsave-lower-hutt")):
    """Shopping list for the most recent active bundle."""
    db = get_db()
    pricing_db = get_pricing_db()

    bundle = db["bundles"].find_one(
        {"active": True},
        sort=[("week", -1), ("createdAt", -1)]
    )
    if not bundle:
        raise HTTPException(status_code=404, detail="No active bundle found")

    recipe_ids = bundle.get("recipeIds", [])
    recipes = list(db["recipes"].find({"recipeId": {"$in": recipe_ids}}))
    shopping_items, total = _derive_shopping_list(recipes, pricing_db, store_id)

    latest_product = pricing_db["products"].find_one(
        {}, sort=[("lastChecked", -1)], projection={"lastChecked": 1}
    )
    scraped_at = latest_product.get("lastChecked") if latest_product else None

    return {
        "bundleId":       bundle.get("bundleId"),
        "week":           bundle.get("week"),
        "weekSummary":    bundle.get("weekSummary"),
        "estimatedTotal": total,
        "scrapedAt":      scraped_at,
        "shoppingList":   shopping_items,
    }