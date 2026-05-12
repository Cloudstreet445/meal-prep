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
        _STORE_NAME_MAP = {
            "paknsave-lower-hutt": "PAK'nSAVE Lower Hutt",
            "paknsave-porirua":    "PAK'nSAVE Porirua",
            "paknsave-petone":     "PAK'nSAVE Petone",
            "paknsave-kilbirnie":  "PAK'nSAVE Kilbirnie",
        }
        store_name   = _STORE_NAME_MAP.get(body.store_id)
        store_filter = {"storeId": store_name} if store_name else {}
        product = pricing_db["products"].find_one(
            {"name": name_pattern, **store_filter},
            {"name": 1, "currentPrice": 1, "isSpecial": 1},
        )
        if product:
            suggestions.append({
                "name": product["name"],
                "searchTerm": term,
                "currentPrice": product.get("currentPrice"),
                "isSpecial": product.get("isSpecial", False),
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
