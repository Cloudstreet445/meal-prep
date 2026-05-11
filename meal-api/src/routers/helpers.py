"""Shared helper functions for bundle and shopping routes."""

import re


_AMOUNT_RE = re.compile(r'^(\d+(?:\.\d+)?)\s*([a-zA-Z]+)$')

_UNIT_NORMALIZE = {
    "grams": "g", "gram": "g",
    "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
    "millilitres": "ml", "millilitre": "ml", "milliliters": "ml", "milliliter": "ml",
    "litres": "l", "litre": "l", "liters": "l", "liter": "l",
    "cloves": "clove",
    "cups": "cup",
    "teaspoons": "tsp", "teaspoon": "tsp",
    "tablespoons": "tbsp", "tablespoon": "tbsp",
    "heads": "head",
    "bunches": "bunch",
    "items": "item",
}


def _parse_amount(raw: str) -> dict | None:
    """Parse a free-text amount string to {value, unit}, or None if unparseable."""
    if not raw:
        return None
    m = _AMOUNT_RE.match(raw.strip())
    if not m:
        return None
    unit = _UNIT_NORMALIZE.get(m.group(2).lower(), m.group(2).lower())
    return {"value": float(m.group(1)), "unit": unit}


def _normalise_unit(value: float, unit: str) -> tuple[float, str]:
    """Promote g→kg if ≥1000g, ml→L if ≥1000ml."""
    if unit == "g" and value >= 1000:
        return value / 1000, "kg"
    if unit == "ml" and value >= 1000:
        return value / 1000, "L"
    return value, unit


def _add_amounts(a: dict, b: dict) -> dict | None:
    """Sum two parsed amounts if units are compatible; returns None if not."""
    ua, ub = a["unit"], b["unit"]
    va, vb = a["value"], b["value"]

    if ua == ub:
        return {"value": va + vb, "unit": ua}

    if {ua, ub} == {"g", "kg"}:
        total_g = (va if ua == "g" else va * 1000) + (vb if ub == "g" else vb * 1000)
        return {"value": total_g, "unit": "g"}

    if {ua, ub} == {"ml", "l"}:
        total_ml = (va if ua == "ml" else va * 1000) + (vb if ub == "ml" else vb * 1000)
        return {"value": total_ml, "unit": "ml"}

    return None


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
                item["priceSavings"] = round(avg - current, 2)

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
                existing = ingredient_map[key]
                existing["estimatedCost"] += ing.get("estimatedCost", 0)
                if ing.get("fromSpecial"):
                    existing["fromSpecial"] = True

                new_raw = ing.get("amount", "")
                if "amount_parts" not in existing:
                    parsed_existing = _parse_amount(existing.get("amount", ""))
                    parsed_new = _parse_amount(new_raw)
                    if parsed_existing and parsed_new:
                        summed = _add_amounts(parsed_existing, parsed_new)
                        if summed:
                            total_val, total_unit = _normalise_unit(summed["value"], summed["unit"])
                            existing["amount"] = f"{total_val:g} {total_unit}"
                        else:
                            existing["amount_parts"] = [
                                {"amount": existing["amount"], "recipe": existing["usedInNames"][0]},
                                {"amount": new_raw, "recipe": recipe_name},
                            ]
                            existing["amount"] = ""
                else:
                    existing["amount_parts"].append({"amount": new_raw, "recipe": recipe_name})

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
