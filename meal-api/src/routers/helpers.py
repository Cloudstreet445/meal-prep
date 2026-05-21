"""Shared helper functions for bundle and shopping routes."""

import math
import re
from datetime import date as _date


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
    # count plurals → singular (matched against _CULINARY_TO_GRAMS)
    "onions": "onion",
    "eggs": "egg",
    "lemons": "lemon",
    "limes": "lime",
    "carrots": "carrot",
    "potatoes": "potato",
    "tomatoes": "tomato",
    "zucchinis": "zucchini",
    "courgettes": "courgette",
    "capsicums": "capsicum",
    "avocados": "avocado",
    "stalks": "stalk",
    "sprigs": "sprig",
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
    user_id: str | None = None,
) -> list[dict] | None:
    """
    Pick n recipes from the library that fit within budget.

    Protein variety is enforced, with slot priority driven by which proteins
    haven't appeared recently (stalest protein gets first pick). Within each
    slot, candidates are ranked by a composite score: recency decay ×
    rating multiplier.
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

    # Build per-user rating sets
    disliked_ids: set[str] = set()
    liked_ids: set[str] = set()
    if user_id:
        for r in candidates:
            for rating in r.get("ratings", []):
                if rating.get("userId") == user_id:
                    if rating.get("score") == -1:
                        disliked_ids.add(r["recipeId"])
                    elif rating.get("score") == 1:
                        liked_ids.add(r["recipeId"])

    filtered = [r for r in candidates if r["recipeId"] not in disliked_ids]
    if len(filtered) < n:
        import logging
        logging.warning(
            f"Only {len(filtered)} candidates after dislike filter for user {user_id} — including disliked"
        )
        filtered = candidates

    candidates = filtered

    if len(candidates) < n:
        return None

    today = _date.today()

    for r in candidates:
        r["_protein"]   = _infer_protein(r)
        r["_cost"]      = _recipe_cost(r)
        r["_last_used"] = r.get("lastUsedWeek") or "2000-01-01"

        # Recency: 0.0 (used this week) → 1.0 (not used in 8+ weeks / never)
        try:
            weeks_ago = (today - _date.fromisoformat(r["_last_used"])).days / 7
        except (ValueError, TypeError):
            weeks_ago = 52
        recency = min(weeks_ago / 8, 1.0)

        # Liked recipes score 30% higher; disliked already excluded above
        rating_mult = 1.3 if r["recipeId"] in liked_ids else 1.0

        r["_score"] = recency * rating_mult

    # Best candidates first
    candidates.sort(key=lambda r: r["_score"], reverse=True)

    # Protein priority: stalest protein gets first pick, preventing repetition ruts
    protein_last_used = {
        protein: max(
            (r["_last_used"] for r in candidates if r["_protein"] == protein),
            default="2000-01-01",
        )
        for protein in ("chicken", "pork", "beef", "lamb", "other")
    }
    protein_order = sorted(protein_last_used, key=lambda p: protein_last_used[p])

    selected: list[dict] = []
    selected_ids: set[str] = set()
    total = 0.0

    # Pass 1: one slot per protein, least-recently-used protein first
    for protein in protein_order:
        if len(selected) >= n:
            break
        for r in candidates:
            if r["_protein"] == protein and r["recipeId"] not in selected_ids:
                if total + r["_cost"] <= budget:
                    selected.append(r)
                    selected_ids.add(r["recipeId"])
                    total += r["_cost"]
                    break

    # Pass 2: fill remaining slots, best-scored first
    for r in candidates:
        if len(selected) >= n:
            break
        if r["recipeId"] not in selected_ids and total + r["_cost"] <= budget:
            selected.append(r)
            selected_ids.add(r["recipeId"])
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


_CULINARY_TO_GRAMS = {
    # culinary measures
    "clove":   5.0,
    "pinch":   0.5,
    "handful": 30.0,
    "sprig":   2.0,
    "stalk":   20.0,
    "head":    200.0,
    "bunch":   100.0,
    # common produce sold by count
    "onion":   150.0,
    "egg":     60.0,
    "lemon":   100.0,
    "lime":    70.0,
    "carrot":  80.0,
    "potato":  150.0,
    "tomato":  100.0,
    "zucchini": 200.0,
    "courgette": 200.0,
    "capsicum": 150.0,
    "avocado": 200.0,
}

_CULINARY_TO_ML = {
    "tsp":  5.0,
    "tbsp": 15.0,
    "cup":  240.0,
    "fl oz": 30.0,
}

_INGREDIENT_COST_CAP = 20.0   # cap on proportional budget estimate per ingredient
_PACK_COST_CAP       = 60.0   # cap on pack price (legitimate packs rarely exceed this)

_PACK_SIZE_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(kg|g|ml|l)\b', re.IGNORECASE)


def _parse_pack_size_g(product_name: str) -> float | None:
    """Parse pack size from a product name string, returning grams (or ml as grams)."""
    m = _PACK_SIZE_RE.search(product_name)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2).lower()
    if unit == "kg":
        return val * 1000
    if unit == "g":
        return val
    if unit == "l":
        return val * 1000
    if unit == "ml":
        return val
    return None


def _ingredient_to_g(amount) -> float | None:
    """Convert an ingredient amount to grams or ml for proportional cost calculation."""
    parsed = _parse_amount(amount)
    if not parsed:
        return None
    value, unit = parsed["value"], parsed["unit"]
    if unit == "g":
        return value
    if unit == "kg":
        return value * 1000
    if unit == "ml":
        return value
    if unit == "l":
        return value * 1000
    if unit in _CULINARY_TO_GRAMS:
        return value * _CULINARY_TO_GRAMS[unit]
    if unit in _CULINARY_TO_ML:
        return value * _CULINARY_TO_ML[unit]
    return None


# Processed/derivative product words — penalised when the ingredient
# name itself doesn't contain them (e.g. "garlic" → penalise "Garlic Paste")
_PROCESSED_WORDS = frozenset({
    "paste", "powder", "sauce", "seasoning", "aioli", "marinade",
    "extract", "flavour", "flavor", "spread", "dip", "mix", "blend",
    "salt", "flakes", "granules", "crushed", "minced", "roasted",
    "dried", "smoked", "pickled", "fermented",
})


def _word_score(product_name: str, words: list[str]) -> int:
    """
    Score a product name against ingredient words.
    Positive score for each ingredient word found in the product name.
    Heavy penalty for processed/derivative words not present in the ingredient.
    """
    prod_lower  = product_name.lower()
    prod_tokens = set(re.split(r'\W+', prod_lower))
    ing_tokens  = set(words)

    score = sum(1 for w in words if w in prod_lower)

    # Each unexpected processed-food word subtracts 2 points
    unexpected = (prod_tokens & _PROCESSED_WORDS) - ing_tokens
    score -= len(unexpected) * 2

    return score


def _enrich_ingredient(item: dict, pricing_db, store_id: str) -> dict:
    """
    Match an ingredient against paknsave-pricing products and calculate cost.

    Fetches up to 30 candidates matching the primary ingredient word, scores
    each by how many ingredient words appear in the product name, then picks
    the option with the lowest total purchase cost for the quantity needed
    (e.g. 1×1kg pack beats 2×500g packs when the 1kg is cheaper overall).

    Two prices are stored on the item:
      packPrice    – what the shopper actually pays at checkout (whole packs)
      currentPrice – proportional budget impact (fed to estimatedCost)
    """
    name = item.get("name", "") or item.get("searchKey", "")
    words = [w for w in re.split(r'\W+', name.lower()) if len(w) > 2]

    if not words:
        return item

    price_prefix = f"storePrice.{store_id}"
    candidates = list(pricing_db["products"].find(
        {"name": re.compile(words[0], re.IGNORECASE), price_prefix: {"$exists": True}},
        {"name": 1, price_prefix: 1},
        limit=30,
    ))

    if not candidates:
        return item

    needed_g = _ingredient_to_g(item.get("amount"))

    # Evaluate every candidate: score by name relevance, cost by quantity needed
    best: dict | None = None

    for product in candidates:
        sp = product.get("storePrice", {}).get(store_id, {})
        raw_price = sp.get("currentPrice")
        if raw_price is None:
            continue

        score  = _word_score(product["name"], words)
        pack_g = _parse_pack_size_g(product["name"])

        if pack_g and needed_g and pack_g > 0:
            packs      = max(1, math.ceil(needed_g / pack_g))
            total_cost = packs * raw_price
        else:
            packs      = 1
            total_cost = raw_price

        candidate = {
            "product":    product,
            "sp":         sp,
            "raw_price":  raw_price,
            "pack_g":     pack_g,
            "packs":      packs,
            "total_cost": total_cost,
            "score":      score,
        }

        if best is None:
            best = candidate
            continue

        # Higher word-match score wins outright; ties go to lowest total cost
        if score > best["score"] or (
            score == best["score"] and total_cost < best["total_cost"]
        ):
            best = candidate

    if best is None:
        return item

    raw_price = best["raw_price"]
    pack_g    = best["pack_g"]

    item["isSpecial"]      = best["sp"].get("isSpecial", False)
    item["matchedProduct"] = best["product"]["name"]

    # packPrice: whole-pack checkout cost — what the shopper actually spends
    item["packPrice"] = min(round(best["total_cost"], 2), _PACK_COST_CAP)

    # currentPrice: proportional budget share (cheap staples stay cheap in estimates)
    if pack_g and needed_g and pack_g > 0:
        calculated = (needed_g / pack_g) * raw_price
    else:
        calculated = raw_price
    item["currentPrice"] = min(round(calculated, 2), _INGREDIENT_COST_CAP)

    avg     = best["sp"].get("avgPrice90d")
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

    total = round(sum(i.get("packPrice") or i["estimatedCost"] for i in items), 2)
    return items, total


def _get_bundle_with_recipes(bundle: dict, db, pricing_db) -> dict:
    """Given a bundle document, fetch its recipes and attach them."""
    recipe_ids = bundle.get("recipeIds", [])
    recipes = list(db["recipes"].find({"recipeId": {"$in": recipe_ids}}))

    def _with_cost(r: dict) -> dict:
        cleaned = _clean(r)
        cleaned["estimatedCost"] = round(_recipe_cost(r), 2)
        return cleaned

    recipe_map = {r["recipeId"]: _with_cost(r) for r in recipes}
    ordered_recipes = [recipe_map[rid] for rid in recipe_ids if rid in recipe_map]

    bundle["recipes"] = ordered_recipes
    return bundle
