"""Shopping list endpoints — thin wrapper over bundle shopping derivation."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from ..database import get_db, get_pricing_db
from ..auth_utils import get_current_user, require_user, household_id_for
from .helpers import _derive_shopping_list, _ingredient_alternatives, _normalise_name
from .settings import effective_settings

router = APIRouter()


def _pantry_keys(db, user: dict | None) -> set:
    """Normalised canonical names of the user's server-side pantry, for fuzzy
    'already have it' matching. Empty for anonymous callers."""
    if not user:
        return set()
    items = db["user_pantry"].find({"userId": user["sub"]}, {"canonical": 1, "name": 1})
    return {_normalise_name(i.get("canonical") or i.get("name") or "") for i in items}


@router.get("/latest")
def get_latest_shopping(store_id: str = Query(default=None), user: dict = Depends(require_user)):
    """Shopping list for the household's most recent active bundle.

    Honours the caller's saved settings (store + household size), any brand/cut
    overrides stored on the bundle, and the household's pantry (pantry items are
    flagged and excluded from the total)."""
    db = get_db()
    pricing_db = get_pricing_db()
    settings = effective_settings(db, user)
    hid = household_id_for(db, user)

    bundle = db["bundles"].find_one(
        {"active": True, "householdId": hid},
        sort=[("week", -1), ("createdAt", -1)]
    )
    if not bundle:
        raise HTTPException(status_code=404, detail="No active bundle found")

    store = store_id or settings.get("storeId", "paknsave-lower-hutt")
    recipe_ids = bundle.get("recipeIds", [])
    recipes = list(db["recipes"].find({"recipeId": {"$in": recipe_ids}}))
    shopping_items, total = _derive_shopping_list(
        recipes, pricing_db, store,
        serves=settings.get("serves"),
        overrides=bundle.get("productOverrides") or {},
        pantry=_pantry_keys(db, user),
    )

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


@router.get("/alternatives")
def get_alternatives(
    request: Request,
    ingredient: str = Query(..., min_length=1, max_length=100),
    amount: str = Query(default=""),
    store_id: str = Query(default=None),
):
    """Ranked alternative products for an ingredient (cheapest-relevant first),
    for the brand/cut picker. The first entry is the current default."""
    db = get_db()
    pricing_db = get_pricing_db()
    user = get_current_user(request)
    store = store_id or effective_settings(db, user).get("storeId", "paknsave-lower-hutt")

    return {
        "ingredient":   ingredient,
        "storeId":      store,
        "alternatives": _ingredient_alternatives(ingredient, amount, pricing_db, store),
    }
