"""Shared helper functions for bundle and shopping routes."""

import re


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


def _enrich_ingredient(item: dict, pricing_db, store_id: str) -> dict:
    """
    Try to match an ingredient name against paknsave-pricing products.
    Attaches isSpecial and currentPrice from the store-specific storePrice entry.
    """
    name = item.get("name", "")
    words = [w for w in re.split(r'\W+', name.lower()) if len(w) > 2]

    if not words:
        return item

    name_pattern = re.compile(words[0], re.IGNORECASE)
    product = pricing_db["products"].find_one(
        {
            "name": name_pattern,
            f"storePrice.{store_id}": {"$exists": True},
        },
        {
            "name": 1,
            f"storePrice.{store_id}.currentPrice": 1,
            f"storePrice.{store_id}.isSpecial": 1,
            "avgPrice90d": 1,
        }
    )

    if product:
        store_data = product.get("storePrice", {}).get(store_id, {})
        item["isSpecial"]      = store_data.get("isSpecial", False)
        item["currentPrice"]   = store_data.get("currentPrice")
        item["matchedProduct"] = product.get("name")

        avg     = product.get("avgPrice90d")
        current = item["currentPrice"]
        if item["isSpecial"] and avg and current and avg > 0:
            pct = round((1 - current / avg) * 100)
            if pct > 0:
                item["dealStrength"] = pct

    return item


def _derive_shopping_list(recipes: list, pricing_db, store_id: str = "paknsave-lower-hutt") -> tuple[list, float]:
    """
    Derive a deduplicated shopping list from a list of recipe documents.

    - Deduplicates by normalised ingredient name
    - Computes sharedWith dynamically (ingredients used in >1 recipe)
    - Enriches with live prices from paknsave-pricing for the given store
    - Returns (shopping_items, total)
    """
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
                    "usedIn":        [],
                    "usedInNames":   [],
                    "category":      _guess_category(ing.get("name", "")),
                }
            else:
                ingredient_map[key]["estimatedCost"] += ing.get("estimatedCost", 0)
                if ing.get("fromSpecial"):
                    ingredient_map[key]["fromSpecial"] = True

            if recipe_id not in ingredient_map[key]["usedIn"]:
                ingredient_map[key]["usedIn"].append(recipe_id)
                ingredient_map[key]["usedInNames"].append(recipe_name)

    items = []
    for item in ingredient_map.values():
        enriched = _enrich_ingredient(item, pricing_db, store_id)
        enriched["sharedWith"] = enriched["usedInNames"] if len(enriched["usedIn"]) > 1 else []
        enriched["estimatedCost"] = round(enriched["estimatedCost"], 2)
        items.append(enriched)

    category_order = {"protein": 0, "vegetable": 1, "pantry": 2, "dairy": 3, "other": 4}
    items.sort(key=lambda x: category_order.get(x.get("category", "other"), 4))

    total = round(sum(i["estimatedCost"] for i in items), 2)
    return items, total


def _get_bundle_with_recipes(bundle: dict, db, pricing_db) -> dict:
    """Given a bundle document, fetch its recipes and attach them."""
    recipe_ids = bundle.get("recipeIds", [])
    recipes = list(db["recipes"].find({"recipeId": {"$in": recipe_ids}}))

    recipe_map = {r["recipeId"]: _clean(r) for r in recipes}
    ordered_recipes = [recipe_map[rid] for rid in recipe_ids if rid in recipe_map]

    bundle["recipes"] = ordered_recipes
    return bundle
