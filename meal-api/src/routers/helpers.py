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


def _parse_amount(raw) -> dict | None:
    """Parse an amount to {value, unit}. Accepts a string or a v2 amount object."""
    if not raw:
        return None
    # v2 schema: {"value": 1.2, "unit": "kg", "display": "1.2kg"}
    if isinstance(raw, dict):
        v, u = raw.get("value"), raw.get("unit", "")
        if v is not None and u:
            unit = _UNIT_NORMALIZE.get(u.lower(), u.lower())
            return {"value": float(v), "unit": unit}
        # Fall back to display string if value/unit missing
        raw = raw.get("display", "")
    if not raw:
        return None
    m = _AMOUNT_RE.match(str(raw).strip())
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


_PROTEIN_KEYWORDS: dict[str, list[str]] = {
    "chicken":    ["chicken"],
    "pork":       ["pork", "sausage"],
    "beef":       ["beef", "mince"],
    "lamb":       ["lamb"],
    "vegetarian": [],
}


def _infer_protein(recipe: dict) -> str:
    """Return primaryProtein if set (v2 schema), otherwise infer from ingredient names."""
    if recipe.get("primaryProtein"):
        p = recipe["primaryProtein"].lower()
        return p if p in _PROTEIN_KEYWORDS else "other"
    text = " ".join(i.get("name", "").lower() for i in recipe.get("ingredients", []))
    text += " " + recipe.get("name", "").lower()
    for protein, keywords in _PROTEIN_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return protein
    return "other"


_COST_TIER_ESTIMATE = {"budget": 10.0, "mid": 17.0, "premium": 28.0}


def _recipe_cost(recipe: dict) -> float:
    """Return the recipe's estimated cost.

    Priority order:
      1. recipe.baselineCost — explicit price from scraper/pricing pass
      2. recipe.costTier     — v2 recipes use tier as a proxy (budget/mid/premium)
      3. sum of ingredient.estimatedCost — legacy v1 per-ingredient prices
    """
    if recipe.get("baselineCost") is not None:
        return recipe["baselineCost"]
    tier = recipe.get("costTier")
    if tier in _COST_TIER_ESTIMATE:
        return _COST_TIER_ESTIMATE[tier]
    return sum(i.get("estimatedCost", 0) for i in recipe.get("ingredients", []))


def _select_from_library(
    db,
    budget: float,
    exclusions: list[str],
    exclude_ids: set[str],
    n: int = 5,
) -> list[dict] | None:
    """
    Pick n recipes from the library that fit within budget with protein variety.

    Selection strategy:
      1. Filter out recipes that contain any excluded ingredient.
      2. Filter out recipes in exclude_ids (current active bundle — avoid repeats).
      3. Sort candidates by lastUsedWeek ascending (prefer least-recently-used),
         then by cost ascending as a tiebreaker.
      4. Pass 1 — pick one recipe per protein group (chicken → pork → beef → lamb → other),
         taking the top candidate from each group that fits in the remaining budget.
      5. Pass 2 — fill remaining slots with the cheapest remaining candidates that fit.

    Returns the selected recipe docs, or None if fewer than n candidates exist
    or the budget cannot accommodate n meals.
    """
    excl_terms = [e.lower().strip() for e in (exclusions or []) if e.strip()]

    raw = list(db["recipes"].find(
        {"recipeId": {"$nin": list(exclude_ids)}} if exclude_ids else {}
    ))

    def _has_excluded(r: dict) -> bool:
        if not excl_terms:
            return False
        text = " ".join(i.get("name", "").lower() for i in r.get("ingredients", []))
        return any(t in text for t in excl_terms)

    candidates = [r for r in raw if not _has_excluded(r)]

    if len(candidates) < n:
        return None

    for r in candidates:
        r["_protein"]   = _infer_protein(r)
        r["_cost"]      = _recipe_cost(r)
        r["_last_used"] = r.get("lastUsedWeek") or "2000-01-01"

    candidates.sort(key=lambda r: (r["_last_used"], r["_cost"]))

    selected: list[dict] = []
    total = 0.0

    # Pass 1: one per protein type, least-recently-used first
    for protein in ("chicken", "pork", "beef", "lamb", "other"):
        if len(selected) >= n:
            break
        for r in candidates:
            if r["_protein"] == protein and r not in selected:
                if total + r["_cost"] <= budget:
                    selected.append(r)
                    total += r["_cost"]
                    break

    # Pass 2: fill remaining slots
    for r in candidates:
        if len(selected) >= n:
            break
        if r not in selected and total + r["_cost"] <= budget:
            selected.append(r)
            total += r["_cost"]

    return selected if len(selected) >= n else None


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

    The pricing DB uses the nested schema: each product carries a
    storePrice.{storeSlug} map with currentPrice/isSpecial/avgPrice90d inside
    the per-store entry. store_id is the slug used as the map key.
    """
    name = item.get("name", "") or item.get("searchKey", "")
    words = [w for w in re.split(r'\W+', name.lower()) if len(w) > 2]

    if not words:
        return item

    price_prefix = f"storePrice.{store_id}"
    name_pattern = re.compile(words[0], re.IGNORECASE)
    product = pricing_db["products"].find_one(
        {"name": name_pattern, price_prefix: {"$exists": True}},
        {"name": 1, price_prefix: 1},
    )

    if product:
        sp = product.get("storePrice", {}).get(store_id, {})
        item["isSpecial"]      = sp.get("isSpecial", False)
        item["currentPrice"]   = sp.get("currentPrice")
        item["matchedProduct"] = product.get("name")

        avg     = sp.get("avgPrice90d")
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

            # Normalise v2 amount object to display string for storage
            raw_amount = ing.get("amount", "")
            if isinstance(raw_amount, dict):
                raw_amount = raw_amount.get("display", "") or ""

            if key not in ingredient_map:
                ingredient_map[key] = {
                    "name":         ing.get("name"),
                    "amount":       raw_amount,
                    "searchKey":    ing.get("searchKey", ""),
                    "isSpecial":    False,
                    "currentPrice": None,
                    "usedIn":       [],
                    "usedInNames":  [],
                    "category":     _guess_category(ing.get("name", "")),
                }
            else:
                existing = ingredient_map[key]
                new_raw = ing.get("amount", "")
                if isinstance(new_raw, dict):
                    new_raw = new_raw.get("display", "") or ""
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
        # Use live price as cost; fall back to 0 if no product was matched
        enriched["estimatedCost"] = round(enriched.get("currentPrice") or 0, 2)
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
