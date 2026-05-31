"""Shared helper functions for bundle and shopping routes."""

import logging
import math
import re
from datetime import date as _date

_log = logging.getLogger(__name__)


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


# Centre-of-plate protein classes. Order matters: the first class whose
# keyword appears wins, so meat is detected before plant proteins in mixed
# dishes. "plant" and "fish" mean a veg/seafood meal still has a recognised
# main — they are NOT lumped into "other" (which is reserved for meals with no
# identifiable protein at the centre).
_PROTEIN_KEYWORDS: dict[str, list[str]] = {
    "chicken": ["chicken"],
    "pork":    ["pork", "sausage", "bacon", "ham"],
    "beef":    ["beef", "mince", "steak"],
    "lamb":    ["lamb"],
    "fish":    ["fish", "salmon", "tuna", "prawn", "shrimp", "seafood", "mussel"],
    "plant":   ["tofu", "tempeh", "lentil", "chickpea", "bean", "paneer", "halloumi", "egg", "falafel"],
}

# Rotation order also includes "other" (proteinless mains) as a last resort.
_PROTEIN_CLASSES: tuple[str, ...] = tuple(_PROTEIN_KEYWORDS) + ("other",)


def _infer_protein(recipe: dict) -> str:
    """Return the centre-of-plate protein class. Uses primaryProtein if set
    (v2 schema), otherwise infers from ingredient/recipe names. Returns "other"
    only when no protein is found — i.e. the meal has no clear main."""
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


def _live_recipe_cost(recipe: dict, pricing_db, store_id: str, serves: int | None = None) -> tuple[float, bool]:
    """Cost to actually buy this recipe's ingredients at the given store.

    Reuses the same enrichment the shopping list uses, so the budget decision
    is made against live prices the shopper will really pay (whole packs),
    scaled to the household size. Returns (cost, any_ingredient_on_special).
    Falls back to (0.0, False) when nothing matched so the caller can drop back
    to a static estimate.
    """
    items, total = _derive_shopping_list([recipe], pricing_db, store_id, serves=serves)
    on_special = any(i.get("isSpecial") for i in items)
    return total, on_special


def _select_from_library(
    db,
    budget: float,
    exclusions: list[str],
    exclude_ids: set[str],
    n: int = 5,
    user_id: str | None = None,
    pricing_db=None,
    store_id: str = "paknsave-lower-hutt",
    serves: int | None = None,
    min_n: int | None = None,
    diet_tags: list[str] | None = None,
) -> list[dict] | None:
    """
    Pick recipes from the library that fit within budget.

    Protein variety is enforced, with slot priority driven by which proteins
    haven't appeared recently (stalest protein gets first pick). Within each
    slot, candidates are ranked by a composite score.

    When ``pricing_db`` is supplied the selection becomes price-aware: each
    recipe's cost is computed from live store prices (scaled to ``serves``),
    cheaper meals are favoured (so the basket maximises value and leaves budget
    headroom), and meals using ingredients currently on special are boosted.
    Without it the legacy behaviour (recency × rating over static cost tiers)
    is used.

    ``min_n`` lets the plan degrade gracefully: it aims for ``n`` meals but
    returns as few as ``min_n`` rather than failing outright when the budget is
    tight (defaults to ``n`` — strict). ``diet_tags`` filters to recipes
    carrying every requested dietary tag (e.g. 'vegetarian', 'gluten-free').
    """
    min_n = n if min_n is None else min_n
    excl_terms = [e.lower().strip() for e in (exclusions or []) if e.strip()]
    want_tags = {t.lower().strip() for t in (diet_tags or []) if t.strip()}

    raw = list(db["recipes"].find(
        {"recipeId": {"$nin": list(exclude_ids)}} if exclude_ids else {}
    ))

    def _has_excluded(r: dict) -> bool:
        if not excl_terms:
            return False
        text = " ".join(i.get("name", "").lower() for i in r.get("ingredients", []))
        return any(t in text for t in excl_terms)

    def _meets_diet(r: dict) -> bool:
        if not want_tags:
            return True
        have = {str(t).lower() for t in r.get("dietTags", [])}
        return want_tags.issubset(have)

    candidates = [r for r in raw if not _has_excluded(r) and _meets_diet(r)]

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
    if len(filtered) < min_n:
        import logging
        logging.warning(
            f"Only {len(filtered)} candidates after dislike filter for user {user_id} — including disliked"
        )
        filtered = candidates

    candidates = filtered

    if len(candidates) < min_n:
        return None

    today = _date.today()
    price_aware = pricing_db is not None
    target_per_meal = (budget / n) if n else budget

    for r in candidates:
        r["_protein"]   = _infer_protein(r)
        r["_last_used"] = r.get("lastUsedWeek") or "2000-01-01"

        if price_aware:
            live_cost, on_special = _live_recipe_cost(r, pricing_db, store_id, serves=serves)
            # Fall back to a static estimate when nothing matched (e.g. empty
            # pricing data) so the recipe still has a sensible cost.
            r["_cost"]      = live_cost if live_cost > 0 else _recipe_cost(r)
            r["_onSpecial"] = on_special
        else:
            r["_cost"]      = _recipe_cost(r)
            r["_onSpecial"] = False

        # Recency: 0.0 (used this week) → 1.0 (not used in 8+ weeks / never)
        try:
            weeks_ago = (today - _date.fromisoformat(r["_last_used"])).days / 7
        except (ValueError, TypeError):
            weeks_ago = 52
        recency = min(weeks_ago / 8, 1.0)

        # Liked recipes score 30% higher; disliked already excluded above
        rating_mult = 1.3 if r["recipeId"] in liked_ids else 1.0

        if price_aware:
            # Cheapness: a meal at exactly the per-meal budget scores ×1.0;
            # cheaper meals are boosted (up to ×2), pricier ones penalised
            # (down to ×0.5). This drives the greedy passes toward value.
            if r["_cost"] > 0:
                cheap_mult = max(0.5, min(target_per_meal / r["_cost"], 2.0))
            else:
                cheap_mult = 1.0
            special_mult = 1.15 if r["_onSpecial"] else 1.0
            # Prefer meals with a clear protein at the centre of the plate;
            # proteinless meals ("other") are deprioritised but not excluded.
            main_mult = 0.5 if r["_protein"] == "other" else 1.0
            r["_score"] = recency * rating_mult * cheap_mult * special_mult * main_mult
        else:
            r["_score"] = recency * rating_mult

    # Best candidates first
    candidates.sort(key=lambda r: r["_score"], reverse=True)

    # Protein priority: stalest protein gets first pick, preventing repetition ruts
    protein_last_used = {
        protein: max(
            (r["_last_used"] for r in candidates if r["_protein"] == protein),
            default="2000-01-01",
        )
        for protein in _PROTEIN_CLASSES
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

    return selected if len(selected) >= min_n else None


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


def _match_score(product: dict, words: list[str]) -> int:
    """Relevance score for a product against ingredient words. Prefers the
    scraper's precomputed searchTokens (already brand/qualifier/unit-stripped,
    so matching is far cleaner) and falls back to the raw name for products
    scraped before tokens were stored."""
    tokens = product.get("searchTokens")
    if tokens:
        tokset = set(tokens)
        ing = set(words)
        score = sum(1 for w in words if w in tokset)
        # Still penalise processed/derivative tokens not asked for (e.g. a bare
        # "garlic" ingredient matching "Garlic Paste").
        score -= len((tokset & _PROCESSED_WORDS) - ing) * 2
        return score
    return _word_score(product.get("name", ""), words)


_PRODUCT_PROJECTION = {"name": 1, "brand": 1, "sizeGrams": 1, "searchTokens": 1}


def _candidate_query(words: list[str], price_prefix: str) -> dict:
    """Match products by the ingredient's primary word against either the
    scraper's clean searchTokens (brand/unit-stripped, MEA-111) or the raw
    name (fallback for products scraped before tokens existed)."""
    first = words[0]
    # re.escape the user-derived term: it is compiled into a MongoDB $regex,
    # so unescaped metacharacters would let a caller inject regex (ReDoS /
    # catastrophic backtracking, or skew matching).
    return {
        "$or": [
            {"searchTokens": first},
            {"name": re.compile(re.escape(first), re.IGNORECASE)},
        ],
        price_prefix: {"$exists": True},
    }


def _candidate_pricing(product: dict, store_id: str, words: list[str], needed_g: float | None) -> dict | None:
    """Score and cost a single pricing product against an ingredient.

    Returns None when the product has no price at this store. ``per_unit`` is
    the price per gram/ml, which lets us compare value fairly across pack sizes.
    """
    sp = product.get("storePrice", {}).get(store_id, {})
    raw_price = sp.get("currentPrice")
    if raw_price is None:
        return None

    # Prefer the numeric pack size stored by the scraper; fall back to parsing
    # it out of the product name for products that predate that field.
    pack_g = product.get("sizeGrams") or _parse_pack_size_g(product["name"])

    if pack_g and needed_g and pack_g > 0:
        packs      = max(1, math.ceil(needed_g / pack_g))
        total_cost = packs * raw_price
    else:
        packs      = 1
        total_cost = raw_price

    return {
        "product":    product,
        "sp":         sp,
        "raw_price":  raw_price,
        "pack_g":     pack_g,
        "packs":      packs,
        "total_cost": round(total_cost, 2),
        "per_unit":   (raw_price / pack_g) if pack_g else raw_price,
        "score":      _match_score(product, words),
    }


def _rank_candidates(name: str, amount, candidates: list, store_id: str) -> list[dict]:
    """Rank pricing products for an ingredient: most relevant first, then
    cheapest per unit, then cheapest total. The top entry is the sensible
    default (cheapest among the best textual matches — so 'chicken breast'
    lands on the cheapest chicken-breast brand); the rest are the alternatives
    a shopper can switch to.
    """
    words = [w for w in re.split(r'\W+', name.lower()) if len(w) > 2]
    needed_g = _ingredient_to_g(amount)
    scored = [
        c for product in candidates
        if (c := _candidate_pricing(product, store_id, words, needed_g)) is not None
    ]
    scored.sort(key=lambda c: (-c["score"], c["per_unit"], c["total_cost"]))
    return scored


def _apply_pricing(item: dict, best: dict) -> dict:
    """Write the chosen product's pricing/metadata onto a shopping item."""
    product, sp = best["product"], best["sp"]
    raw_price, pack_g = best["raw_price"], best["pack_g"]
    needed_g = _ingredient_to_g(item.get("amount"))

    item["isSpecial"]      = sp.get("isSpecial", False)
    item["matchedProduct"] = product["name"]
    if product.get("_id") is not None:
        item["productId"] = str(product["_id"])
    if product.get("brand"):
        item["brand"] = product["brand"]
    if sp.get("unitPriceValue") is not None:
        item["unitPriceValue"] = sp.get("unitPriceValue")
        item["unitPriceUnit"]  = sp.get("unitPriceUnit", "")

    # packPrice: whole-pack checkout cost — what the shopper actually spends
    raw_pack = round(best["total_cost"], 2)
    item["packPrice"] = min(raw_pack, _PACK_COST_CAP)

    # currentPrice: proportional budget share (cheap staples stay cheap in estimates)
    if pack_g and needed_g and pack_g > 0:
        calculated = (needed_g / pack_g) * raw_price
    else:
        calculated = raw_price
    raw_current = round(calculated, 2)
    item["currentPrice"] = min(raw_current, _INGREDIENT_COST_CAP)

    # A value over the cap almost always means a bad ingredient→product match.
    # Cap to protect the total, but flag + log so it's visible instead of hidden.
    if raw_pack > _PACK_COST_CAP or raw_current > _INGREDIENT_COST_CAP:
        item["costWarning"] = True
        _log.warning(
            "Suspicious price for %r → matched %r: pack $%.2f, unit $%.2f (capped)",
            item.get("name"), product.get("name"), raw_pack, raw_current,
        )

    avg     = sp.get("avgPrice90d")
    current = item["currentPrice"]
    if item["isSpecial"] and avg and current and avg > 0:
        pct = round((1 - current / avg) * 100)
        if pct > 0:
            item["dealStrength"] = pct
            item["priceSavings"] = round(avg - current, 2)

    return item


def _enrich_ingredient(item: dict, pricing_db, store_id: str, override_id=None) -> dict:
    """
    Match an ingredient against paknsave-pricing products and calculate cost.

    By default the cheapest of the best-matching products is chosen (so a
    recipe's 'chicken breast' defaults to the cheapest chicken-breast brand).
    When ``override_id`` is given, that specific product is used instead — this
    is how a shopper can swap to a different brand or cut and have the total
    follow their choice.

    Two prices are stored on the item:
      packPrice    – what the shopper actually pays at checkout (whole packs)
      currentPrice – proportional budget impact (fed to estimatedCost)
    """
    name = item.get("name", "") or item.get("searchKey", "")
    words = [w for w in re.split(r'\W+', name.lower()) if len(w) > 2]

    if not words:
        return item

    price_prefix = f"storePrice.{store_id}"
    projection = {**_PRODUCT_PROJECTION, price_prefix: 1}

    best: dict | None = None

    # An explicit user override wins, as long as it's stocked at this store.
    if override_id:
        chosen = pricing_db["products"].find_one({"_id": override_id}, projection)
        if chosen:
            best = _candidate_pricing(chosen, store_id, words, _ingredient_to_g(item.get("amount")))
            if best:
                item["isOverride"] = True

    if best is None:
        candidates = list(pricing_db["products"].find(
            _candidate_query(words, price_prefix),
            projection,
            limit=30,
        ))
        ranked = _rank_candidates(name, item.get("amount"), candidates, store_id)
        best = ranked[0] if ranked else None

    if best is None:
        return item

    return _apply_pricing(item, best)


def _ingredient_alternatives(name: str, amount, pricing_db, store_id: str, limit: int = 8) -> list[dict]:
    """Return ranked alternative products for an ingredient (cheapest-relevant
    first) for the brand/cut picker in the shopping list."""
    words = [w for w in re.split(r'\W+', name.lower()) if len(w) > 2]
    if not words:
        return []

    price_prefix = f"storePrice.{store_id}"
    candidates = list(pricing_db["products"].find(
        _candidate_query(words, price_prefix),
        {**_PRODUCT_PROJECTION, price_prefix: 1},
        limit=30,
    ))

    out = []
    for c in _rank_candidates(name, amount, candidates, store_id)[:limit]:
        product, sp = c["product"], c["sp"]
        out.append({
            "productId":    str(product["_id"]) if product.get("_id") is not None else None,
            "name":         product["name"],
            "brand":        product.get("brand") or None,
            "packPrice":    round(c["total_cost"], 2),
            "currentPrice": sp.get("currentPrice"),
            "unitPrice":    sp.get("unitPrice") or None,
            "sizeGrams":    c["pack_g"],
            "isSpecial":    sp.get("isSpecial", False),
        })
    return out


def _scale_amount(raw, factor: float):
    """Scale a display amount by a serving factor, e.g. '400g' ×1.5 → '600 g'.
    Leaves unparseable amounts (and factor 1) untouched."""
    if not raw or not factor or factor == 1:
        return raw
    parsed = _parse_amount(raw)
    if not parsed:
        return raw
    value, unit = _normalise_unit(parsed["value"] * factor, parsed["unit"])
    return f"{value:g} {unit}"


def _derive_shopping_list(
    recipes: list,
    pricing_db,
    store_id: str = "paknsave-lower-hutt",
    *,
    serves: int | None = None,
    overrides: dict | None = None,
    pantry: set | None = None,
) -> tuple[list, float]:
    """
    Derive a deduplicated shopping list from a list of recipe documents.

    - Deduplicates by normalised ingredient name
    - Computes sharedWith dynamically (ingredients used in >1 recipe)
    - Enriches with live prices from paknsave-pricing for the given store
    - ``serves``: scale each recipe's quantities to this household size
      (recipes carry their own base ``serves``)
    - ``overrides``: {normalised ingredient name: productId} brand/cut choices
    - ``pantry``: normalised names the household already has — flagged
      ``inPantry`` and excluded from the total (you don't buy what you own)
    - Returns (shopping_items, total)
    """
    overrides = overrides or {}
    pantry = pantry or set()
    ingredient_map: dict[str, dict] = {}

    for recipe in recipes:
        recipe_id = recipe.get("recipeId", recipe.get("_id", ""))
        recipe_name = recipe.get("name", "")

        # Scale this recipe's quantities to the household size when both the
        # target and the recipe's own base serving count are known.
        base_serves = recipe.get("serves")
        factor = (serves / base_serves) if (serves and base_serves) else 1

        for ing in recipe.get("ingredients", []):
            key = _normalise_name(ing.get("name", ""))
            if not key:
                continue

            # Normalise v2 amount object to display string for storage
            raw_amount = ing.get("amount", "")
            if isinstance(raw_amount, dict):
                raw_amount = raw_amount.get("display", "") or ""
            raw_amount = _scale_amount(raw_amount, factor)

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
                new_raw = _scale_amount(new_raw, factor)
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
    for key, item in ingredient_map.items():
        enriched = _enrich_ingredient(item, pricing_db, store_id, override_id=overrides.get(key))
        enriched["sharedWith"] = enriched["usedInNames"] if len(enriched["usedIn"]) > 1 else []
        # Use live price as cost; fall back to 0 if no product was matched
        enriched["estimatedCost"] = round(enriched.get("currentPrice") or 0, 2)
        # Pantry match is fuzzy: 'garlic' in pantry covers 'garlic cloves'.
        enriched["inPantry"] = any(p and (p in key or key in p) for p in pantry)
        items.append(enriched)

    category_order = {"protein": 0, "vegetable": 1, "pantry": 2, "dairy": 3, "other": 4}
    items.sort(key=lambda x: category_order.get(x.get("category", "other"), 4))

    # Total excludes pantry items — you don't buy what you already have.
    total = round(sum(
        (i.get("packPrice") or i["estimatedCost"])
        for i in items if not i.get("inPantry")
    ), 2)
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
