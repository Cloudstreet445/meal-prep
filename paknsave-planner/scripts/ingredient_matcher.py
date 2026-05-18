"""
Fuzzy ingredient-to-product matching engine.

MEA-71  — original matcher (flat product schema, per-product normalisation).
MEA-115 — reworked for the live data model:
  * reads the `products` collection inside the `paknsave-pricing` database
    (the old code treated the database name as a collection)
  * reads price / special from the per-store `storePrice.{storeId}` map the
    C# scraper writes — there is no top-level `currentPrice`/`storeId`
  * resolves NZ / UK / US naming via the `ingredient_synonyms` collection
    before searching
  * scores against the precomputed `searchTokens` array (MEA-111) instead of
    re-normalising every product name on every lookup
  * checks `ingredient_match_cache` first, and writes matches back with a
    BSON-date `matchedAt` so the collection's TTL index expires them
  * tries `searchKeyVariants` in order, highest-confidence first

Usage:
    matcher = IngredientMatcher(pricing_db)        # the paknsave-pricing DB
    result = matcher.match("chicken drumsticks", store_id="paknsave-lower-hutt")
    if result:
        print(result.product_name, result.price, result.confidence)
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from pricing_tokens import tokenise

# ---------------------------------------------------------------------------
# Category hints — if a searchKey contains these words, bias candidate
# selection toward the matching product categories. Best-effort fallback only.
# ---------------------------------------------------------------------------

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
# Scoring
# ---------------------------------------------------------------------------

def token_overlap_score(query_tokens: list, candidate_tokens: list) -> float:
    """
    Jaccard-style token overlap, blended with query coverage so that a
    candidate containing every query token scores higher than one that
    merely shares a token.
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
    coverage = len(intersection) / len(q_set)
    return (base_score + coverage) / 2


def get_category_hints(search_key: str) -> list:
    """Return likely product category names for a given searchKey."""
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
    Matches a recipe ingredient searchKey against products in the
    `paknsave-pricing` database. Construct with the pymongo *Database*.
    """

    CONFIDENCE_EXACT = 0.9
    CONFIDENCE_GOOD = 0.7
    CONFIDENCE_WEAK = 0.5

    def __init__(self, db):
        """`db` is the paknsave-pricing database (a pymongo Database)."""
        self.db = db
        self.products = db["products"]
        self.synonyms_col = db["ingredient_synonyms"]
        self.cache_col = db["ingredient_match_cache"]
        self._syn_index = None  # lazily loaded {term -> [canonical, *variants]}

    # -- synonyms -----------------------------------------------------------

    def _load_synonyms(self):
        if self._syn_index is not None:
            return
        index = {}
        for entry in self.synonyms_col.find({}, {"canonical": 1, "variants": 1}):
            group = [entry.get("canonical", "")] + list(entry.get("variants", []))
            group = [g for g in group if g]
            for term in group:
                index[term.lower()] = group
        self._syn_index = index

    def _expand(self, term: str) -> list:
        """Return the term plus every known synonym worth searching for."""
        self._load_synonyms()
        return self._syn_index.get(term.lower().strip(), [term])

    # -- match cache --------------------------------------------------------

    def _cache_get(self, search_key: str, store_id: str) -> Optional[MatchResult]:
        """Return a cached match, re-pricing it from the live product doc."""
        doc = self.cache_col.find_one({"searchKey": search_key})
        if not doc or "productId" not in doc:
            return None

        store_field = "storePrice." + store_id
        product = self.products.find_one(
            {"_id": doc["productId"]},
            {"_id": 1, "name": 1, "category": 1, store_field: 1},
        )
        if not product:
            return None  # product gone — fall through to a fresh match

        store_data = (product.get("storePrice") or {}).get(store_id)
        if not store_data:
            return None  # not stocked at this store — re-match

        return MatchResult(
            product_id=str(product["_id"]),
            product_name=product.get("name", ""),
            category=product.get("category", ""),
            price=store_data.get("currentPrice", 0.0),
            is_special=bool(store_data.get("isSpecial", False)),
            confidence=doc.get("confidence", 0.0),
            store_id=store_id,
        )

    def _cache_put(self, search_key: str, raw_product_id, result: MatchResult):
        # `matchedAt` is written as a timezone-aware datetime → BSON date,
        # which the TTL index (idx_matchedAt_ttl) needs to expire the entry.
        self.cache_col.update_one(
            {"searchKey": search_key},
            {"$set": {
                "searchKey": search_key,
                "productId": raw_product_id,
                "productName": result.product_name,
                "confidence": result.confidence,
                "matchedAt": datetime.now(timezone.utc),
            }},
            upsert=True,
        )

    # -- matching -----------------------------------------------------------

    def match(
        self,
        search_key: str,
        store_id: str,
        prefer_special: bool = False,
        use_cache: bool = True,
    ) -> Optional[MatchResult]:
        """
        Find the best matching product for a searchKey at a given store.
        Returns None if no candidate exceeds the weak-confidence threshold.
        """
        if not search_key:
            return None

        if use_cache:
            cached = self._cache_get(search_key, store_id)
            if cached is not None:
                return cached

        # Expand synonyms, then tokenise every candidate term.
        term_token_sets = []
        for term in self._expand(search_key):
            toks = tokenise(term)
            if toks:
                term_token_sets.append(toks)
        if not term_token_sets:
            return None

        store_field = "storePrice." + store_id
        store_filter = {store_field: {"$exists": True}}
        projection = {
            "_id": 1, "name": 1, "category": 1,
            "searchTokens": 1, store_field: 1,
        }

        # Primary: products that share at least one precomputed token and are
        # stocked at this store.
        all_tokens = sorted({t for toks in term_token_sets for t in toks})
        candidates = list(self.products.find(
            {**store_filter, "searchTokens": {"$in": all_tokens}}, projection))

        # Fallback: narrow by category hint when the token query finds nothing
        # (e.g. legacy products that predate the searchTokens backfill).
        hints = get_category_hints(search_key)
        if not candidates:
            if hints:
                candidates = list(self.products.find(
                    {**store_filter, "category": {"$in": hints}}, projection))

        if not candidates:
            return None

        best_score = 0.0
        best = None
        for product in candidates:
            ptoks = product.get("searchTokens") or tokenise(product.get("name", ""))
            score = max(token_overlap_score(toks, ptoks) for toks in term_token_sets)

            store_data = (product.get("storePrice") or {}).get(store_id) or {}
            # Boost candidates whose product category aligns with the ingredient type.
            # Prevents e.g. "chicken breast" matching processed products over fresh cuts.
            if hints and product.get("category") in hints:
                score = min(score * 1.2, 1.0)
            if prefer_special and store_data.get("isSpecial"):
                score = min(score * 1.1, 1.0)

            if score > best_score:
                best_score = score
                best = (product, store_data)

        if not best or best_score < self.CONFIDENCE_WEAK:
            return None

        product, store_data = best
        result = MatchResult(
            product_id=str(product["_id"]),
            product_name=product.get("name", ""),
            category=product.get("category", ""),
            price=store_data.get("currentPrice", 0.0),
            is_special=bool(store_data.get("isSpecial", False)),
            confidence=round(best_score, 3),
            store_id=store_id,
        )

        if use_cache:
            self._cache_put(search_key, product["_id"], result)
        return result

    def match_best(
        self,
        variants: list,
        store_id: str,
        prefer_special: bool = False,
    ) -> Optional[MatchResult]:
        """
        Try `searchKeyVariants` in order — index 0 is the highest-confidence
        spelling. Returns the first GOOD (>=0.7) match, otherwise the best
        match found across all variants.
        """
        best = None
        for variant in variants:
            if not variant:
                continue
            result = self.match(variant, store_id, prefer_special)
            if result and (best is None or result.confidence > best.confidence):
                best = result
            if best and best.confidence >= self.CONFIDENCE_GOOD:
                break
        return best

    def match_ingredients(
        self,
        ingredients: list,
        store_id: str,
        prefer_special: bool = False,
    ) -> list:
        """
        Match a list of recipe ingredients. Each ingredient's
        `searchKeyVariants` are tried in order; `searchKey` is the fallback.
        Returns the ingredients with match fields merged in.
        """
        results = []
        for ing in ingredients:
            variants = [v for v in (ing.get("searchKeyVariants") or []) if v]
            if not variants:
                sk = ing.get("searchKey") or ing.get("name", "")
                variants = [sk] if sk else []

            result = self.match_best(variants, store_id, prefer_special)

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
