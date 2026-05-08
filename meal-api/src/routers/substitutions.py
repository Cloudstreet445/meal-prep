"""Ingredient substitution suggestions — static map + live pricing lookup."""

import re
from fastapi import APIRouter
from pydantic import BaseModel
from ..database import get_pricing_db
from .settings import DEFAULT_STORE_ID

router = APIRouter()

# Substitution map: normalised keyword → list of search terms for the pricing DB
_SUBS: dict[str, list[str]] = {
    # Proteins
    "pork":           ["chicken thigh", "beef mince", "tofu firm", "lamb mince"],
    "chicken breast": ["chicken thigh", "pork loin", "turkey breast", "tofu firm"],
    "chicken thigh":  ["chicken breast", "pork shoulder", "beef chuck"],
    "chicken":        ["chicken thigh", "pork mince", "beef mince", "tofu firm"],
    "beef":           ["pork mince", "chicken mince", "lamb mince", "lentils"],
    "lamb":           ["beef mince", "pork mince", "chicken thigh"],
    "mince":          ["chicken mince", "pork mince", "beef mince", "lentils"],
    "steak":          ["pork loin", "chicken breast", "lamb chop"],
    "bacon":          ["chicken breast", "pork belly", "turkey bacon"],
    "sausage":        ["chicken sausage", "pork mince", "beef mince"],
    "tofu":           ["chicken breast", "chickpeas", "paneer", "tempeh"],
    "salmon":         ["chicken thigh", "pork loin", "tofu firm"],
    # Dairy
    "cream":          ["coconut cream", "sour cream", "greek yoghurt"],
    "butter":         ["olive oil", "coconut oil", "margarine"],
    "cheese":         ["feta cheese", "cheddar cheese", "parmesan"],
    "milk":           ["oat milk", "coconut milk", "soy milk"],
    # Veg
    "broccoli":       ["cauliflower", "broccolini", "green beans"],
    "capsicum":       ["courgette", "celery", "carrot"],
    "courgette":      ["capsicum", "eggplant", "zucchini"],
    "potato":         ["kumara", "pumpkin", "cauliflower"],
    "kumara":         ["potato", "pumpkin", "parsnip"],
    "spinach":        ["kale", "silverbeet", "bok choy"],
    # Pantry
    "pasta":          ["rice", "noodles", "couscous", "quinoa"],
    "rice":           ["pasta", "couscous", "quinoa", "noodles"],
    "noodles":        ["pasta", "rice", "vermicelli"],
    "flour":          ["almond flour", "cornflour", "breadcrumbs"],
    "olive oil":      ["vegetable oil", "coconut oil", "canola oil"],
    "soy sauce":      ["tamari", "fish sauce", "coconut aminos"],
    "stock":          ["vegetable stock", "chicken stock", "beef stock"],
}

# Resolve a raw ingredient name to the best substitution key
def _match_key(name: str) -> str | None:
    n = name.lower()
    # Exact key match first
    if n in _SUBS:
        return n
    # Longest keyword that appears in the ingredient name
    best = None
    for key in sorted(_SUBS, key=len, reverse=True):
        if key in n:
            best = key
            break
    return best


class SubstituteRequest(BaseModel):
    ingredient: str
    store_id: str = DEFAULT_STORE_ID


@router.post("/suggest")
def suggest_substitutes(body: SubstituteRequest):
    """Return substitute options with live prices from the pricing DB."""
    pricing_db = get_pricing_db()

    key = _match_key(body.ingredient)
    search_terms = _SUBS.get(key, []) if key else []

    suggestions = []
    for term in search_terms:
        words = [w for w in re.split(r'\W+', term.lower()) if len(w) > 2]
        if not words:
            continue
        name_pattern = re.compile(words[0], re.IGNORECASE)
        product = pricing_db["products"].find_one(
            {
                "name": name_pattern,
                f"storePrice.{body.store_id}": {"$exists": True},
            },
            {
                "name": 1,
                f"storePrice.{body.store_id}.currentPrice": 1,
                f"storePrice.{body.store_id}.isSpecial": 1,
            }
        )
        if product:
            store_data = product.get("storePrice", {}).get(body.store_id, {})
            suggestions.append({
                "name": product["name"],
                "searchTerm": term,
                "currentPrice": store_data.get("currentPrice"),
                "isSpecial": store_data.get("isSpecial", False),
            })
        else:
            # Include without price if not in DB — still useful
            suggestions.append({
                "name": term.title(),
                "searchTerm": term,
                "currentPrice": None,
                "isSpecial": False,
            })

    return {
        "ingredient": body.ingredient,
        "matchedKey": key,
        "suggestions": suggestions,
    }
