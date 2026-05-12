"""
Fuzzy ingredient-to-product matching engine.
MEA-71: Map recipe ingredient searchKeys to paknsave-pricing products.

Informed by MEA-77 audit:
  - Fresh veg: generic names ("Brown Onions", "Broccoli")
  - Proteins: brand + descriptor ("NZ Chicken Drumsticks Value Pack")
  - Dairy: brand-heavy (Anchor, Meadow Fresh)
  - Strip stop words before scoring

Usage:
    matcher = IngredientMatcher(db)
    result = matcher.match("chicken drumsticks", store_id="PAK'nSAVE Lower Hutt")
    if result:
        print(result.product_name, result.price, result.confidence)
"""

import re
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Stop words to strip before matching
# Stop words are brand/qualifier terms that appear in product names
# but don't help find the right product category.
# ---------------------------------------------------------------------------

STOP_WORDS = {
    # Brands
    "pams", "anchor", "meadow", "fresh", "dairyworks", "hellers",
    "wattie", "watties", "homebrand", "san", "remo", "mainland",
    # NZ qualifiers
    "nz", "new", "zealand",
    # Product qualifiers
    "value", "pack", "free", "range", "boneless", "skinless",
    "brushed", "agria", "organic", "trim", "lean",
    # Size qualifiers (keep numbers, strip words)
    "large", "medium", "small", "extra",
}

# Category hints — if searchKey contains these words, bias toward this category
CATEGORY_HINTS = {
    "chicken": ["chicken", "poultry"],
    "pork": ["pork"],
    "beef": ["beef-lamb", "mince-sausages"],
    "lamb": ["beef-lamb"],
    "mince": ["beef-lamb", "mince-sausages", "sausages"],
    "sausage": ["sausages"],
    "salmon": ["seafood"],
    "fish": ["seafood"],
    "prawn": ["seafood"],
    "butter": ["dairy"],
    "milk": ["dairy"],
    "cheese": ["dairy"],
    "cream": ["dairy"],
    "egg": ["eggs"],
    "bread": ["bread-bakery"],
    "pasta": ["pasta-rice-noodles"],
    "rice": ["pasta-rice-noodles"],
    "noodle": ["pasta-rice-noodles"],
    "onion": ["fresh-vegetables"],
    "potato": ["fresh-vegetables"],
    "carrot": ["fresh-vegetables"],
    "broccoli": ["fresh-vegetables"],
    "cabbage": ["fresh-vegetables"],
    "tomato paste": ["sauces"],
    "passata": ["sauces"],
    "soy sauce": ["condiments"],
    "oil": ["oils-vinegars"],
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MatchResult:
    product_id: str
    product_name: str
    category: str
    price: float
    is_special: bool
    confidence: float       # 0.0 – 1.0
    store_id: str

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def normalise(text: str) -> list:
    """
    Lowercase, strip punctuation, remove stop words.
    Returns list of meaningful tokens.
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = text.split()
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


def token_overlap_score(query_tokens: list, candidate_tokens: list) -> float:
    """
    Jaccard-style token overlap score.
    Weights exact matches higher than partial.
    """
    if not query_tokens or not candidate_tokens:
        return 0.0

    q_set = set(query_tokens)
    c_set = set(candidate_tokens)

    intersection = q_set & c_set
    union = q_set | c_set

    if not union:
        return 0.0

    base_score = len(intersection) / len(union)

    # Bonus: if all query tokens are covered by candidate
    coverage = len(intersection) / len(q_set) if q_set else 0
    return (base_score + coverage) / 2


def get_category_hints(search_key: str) -> list:
    """Return likely category names for a given searchKey."""
    sk = search_key.lower()
    for keyword, categories in CATEGORY_HINTS.items():
        if keyword in sk:
            return categories
    return []

# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------

class IngredientMatcher:
    """
    Matches a recipe ingredient searchKey against products in paknsave-pricing.
    Requires a pymongo Database instance.
    """

    CONFIDENCE_EXACT = 0.9
    CONFIDENCE_GOOD = 0.7
    CONFIDENCE_WEAK = 0.5

    def __init__(self, db, collection: str = "paknsave-pricing"):
        self.col = db[collection]

    def match(
        self,
        search_key: str,
        store_id: str,
        prefer_special: bool = False,
    ) -> Optional[MatchResult]:
        """
        Find the best matching product for a searchKey.
        Returns None if no match exceeds the weak threshold.
        """
        query_tokens = normalise(search_key)
        if not query_tokens:
            return None

        # Build category filter to narrow candidates
        category_hints = get_category_hints(search_key)

        mongo_query = {"storeId": store_id}
        if category_hints:
            mongo_query["category"] = {"$in": category_hints}

        candidates = list(self.col.find(mongo_query, {
            "_id": 1, "name": 1, "category": 1,
            "currentPrice": 1, "isSpecial": 1, "storeId": 1,
        }))

        # If category filter returns nothing, try without it
        if not candidates:
            candidates = list(self.col.find({"storeId": store_id}, {
                "_id": 1, "name": 1, "category": 1,
                "currentPrice": 1, "isSpecial": 1, "storeId": 1,
            }))

        if not candidates:
            return None

        # Score all candidates
        best_score = 0.0
        best_candidate = None

        for product in candidates:
            product_tokens = normalise(product.get("name", ""))
            score = token_overlap_score(query_tokens, product_tokens)

            # Boost if on special and caller prefers specials
            if prefer_special and product.get("isSpecial"):
                score = min(score * 1.1, 1.0)

            if score > best_score:
                best_score = score
                best_candidate = product

        if not best_candidate or best_score < self.CONFIDENCE_WEAK:
            return None

        return MatchResult(
            product_id=str(best_candidate["_id"]),
            product_name=best_candidate["name"],
            category=best_candidate.get("category", ""),
            price=best_candidate.get("currentPrice", 0.0),
            is_special=best_candidate.get("isSpecial", False),
            confidence=round(best_score, 3),
            store_id=store_id,
        )

    def match_ingredients(
        self,
        ingredients: list,
        store_id: str,
        prefer_special: bool = False,
    ) -> list:
        """
        Match a list of recipe ingredients.
        Returns list of dicts with match results merged in.
        """
        results = []
        for ing in ingredients:
            search_key = ing.get("searchKey", ing.get("name", ""))
            result = self.match(search_key, store_id, prefer_special)

            enriched = {**ing}
            if result:
                enriched["matchedProduct"] = result.product_name
                enriched["matchedProductId"] = result.product_id
                enriched["matchConfidence"] = result.confidence
                enriched["currentPrice"] = result.price
                enriched["isSpecial"] = result.is_special
                enriched["unpriced"] = False
            else:
                enriched["matchedProduct"] = None
                enriched["matchedProductId"] = None
                enriched["matchConfidence"] = 0.0
                enriched["currentPrice"] = None
                enriched["isSpecial"] = False
                enriched["unpriced"] = True

            results.append(enriched)

        return results
