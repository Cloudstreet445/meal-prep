"""Tests for the reworked fuzzy ingredient matcher (MEA-115)."""

from datetime import datetime

import pytest

from ingredient_matcher import IngredientMatcher, token_overlap_score

STORE = "paknsave-lower-hutt"
OTHER_STORE = "paknsave-porirua"


def make_product(pid, name, category, search_tokens, stores):
    """stores: {storeId: {"price": float, "special": bool}}"""
    return {
        "_id": pid,
        "name": name,
        "category": category,
        "searchTokens": search_tokens,
        "storePrice": {
            sid: {
                "currentPrice": s["price"],
                "isSpecial": s.get("special", False),
                "lastChecked": "2026-05-17",
            }
            for sid, s in stores.items()
        },
    }


@pytest.fixture
def seeded(pricing_db):
    """A pricing DB with products + synonyms; returns (db, matcher)."""
    pricing_db["products"].insert_many([
        make_product("p1", "Fresh NZ Chicken Drumsticks 1kg", "chicken",
                     ["chicken", "drumsticks"], {STORE: {"price": 7.99}}),
        make_product("p2", "NZ Chicken Breast Fillets", "chicken",
                     ["chicken", "breast", "fillets"],
                     {STORE: {"price": 12.50, "special": True}}),
        make_product("p3", "Fresh Coriander Bunch", "fresh-vegetables",
                     ["coriander", "bunch"], {STORE: {"price": 2.50}}),
        make_product("p4", "Anchor Butter 500g", "dairy",
                     ["butter"], {OTHER_STORE: {"price": 6.20}}),
    ])
    pricing_db["ingredient_synonyms"].insert_one(
        {"canonical": "coriander", "variants": ["cilantro", "dhania"]}
    )
    return pricing_db, IngredientMatcher(pricing_db)


class TestTokenOverlapScore:
    def test_identical_tokens_score_one(self):
        assert token_overlap_score(["chicken", "drumsticks"],
                                   ["chicken", "drumsticks"]) == 1.0

    def test_no_overlap_scores_zero(self):
        assert token_overlap_score(["chicken"], ["butter"]) == 0.0

    def test_empty_inputs_score_zero(self):
        assert token_overlap_score([], ["chicken"]) == 0.0


class TestMatch:
    def test_matches_product_and_reads_storePrice_map(self, seeded):
        _, matcher = seeded
        result = matcher.match("chicken drumsticks", STORE)
        assert result is not None
        assert result.product_id == "p1"
        assert result.price == 7.99
        assert result.confidence >= matcher.CONFIDENCE_GOOD

    def test_reads_isSpecial_from_store_entry(self, seeded):
        _, matcher = seeded
        result = matcher.match("chicken breast fillets", STORE)
        assert result.product_id == "p2"
        assert result.is_special is True

    def test_product_not_stocked_at_store_is_not_matched(self, seeded):
        # p4 (butter) only exists at OTHER_STORE.
        _, matcher = seeded
        assert matcher.match("butter", STORE) is None

    def test_synonym_resolves_to_nz_shelf_term(self, seeded):
        # "cilantro" is not on any product; it must resolve to "coriander".
        _, matcher = seeded
        result = matcher.match("cilantro", STORE)
        assert result is not None
        assert result.product_id == "p3"

    def test_unrelated_query_returns_none(self, seeded):
        _, matcher = seeded
        assert matcher.match("chocolate cake", STORE) is None

    def test_empty_search_key_returns_none(self, seeded):
        _, matcher = seeded
        assert matcher.match("", STORE) is None


class TestMatchCache:
    def test_match_writes_cache_entry_with_bson_date(self, seeded):
        db, matcher = seeded
        matcher.match("chicken drumsticks", STORE)
        doc = db["ingredient_match_cache"].find_one({"searchKey": "chicken drumsticks"})
        assert doc is not None
        assert doc["productId"] == "p1"
        assert isinstance(doc["matchedAt"], datetime)

    def test_cache_hit_returns_cached_confidence(self, seeded):
        # A distinctive cached confidence that scoring would never produce
        # proves the result came from the cache, not a fresh match.
        db, matcher = seeded
        db["ingredient_match_cache"].insert_one({
            "searchKey": "chicken drumsticks",
            "productId": "p1",
            "confidence": 0.123,
            "matchedAt": datetime.utcnow(),
        })
        result = matcher.match("chicken drumsticks", STORE)
        assert result.confidence == 0.123
        assert result.price == 7.99  # still re-priced live from the product

    def test_stale_cache_entry_for_unstocked_store_falls_through(self, pricing_db):
        # Cache points at a product stocked only at OTHER_STORE; a query for
        # STORE must ignore it and match a STORE-stocked product instead.
        pricing_db["products"].insert_many([
            make_product("old", "Chicken Drumsticks", "chicken",
                         ["chicken", "drumsticks"], {OTHER_STORE: {"price": 9.0}}),
            make_product("new", "Fresh Chicken Drumsticks", "chicken",
                         ["chicken", "drumsticks"], {STORE: {"price": 7.5}}),
        ])
        pricing_db["ingredient_match_cache"].insert_one({
            "searchKey": "chicken drumsticks",
            "productId": "old",
            "confidence": 0.99,
            "matchedAt": datetime.utcnow(),
        })
        matcher = IngredientMatcher(pricing_db)
        result = matcher.match("chicken drumsticks", STORE)
        assert result.product_id == "new"


class TestMatchIngredients:
    def test_searchKeyVariants_tried_in_order(self, seeded):
        _, matcher = seeded
        ingredients = [{
            "name": "Chicken",
            "searchKey": "chicken drumsticks",
            "searchKeyVariants": ["nonexistent ingredient", "chicken drumsticks"],
        }]
        out = matcher.match_ingredients(ingredients, STORE)
        assert out[0]["matchedProductId"] == "p1"
        assert out[0]["unpriced"] is False
        assert out[0]["currentPrice"] == 7.99

    def test_first_good_variant_wins(self, seeded):
        _, matcher = seeded
        ingredients = [{
            "searchKeyVariants": ["chicken drumsticks", "chicken breast fillets"],
        }]
        out = matcher.match_ingredients(ingredients, STORE)
        assert out[0]["matchedProductId"] == "p1"

    def test_falls_back_to_searchKey_when_no_variants(self, seeded):
        _, matcher = seeded
        out = matcher.match_ingredients(
            [{"searchKey": "chicken drumsticks"}], STORE)
        assert out[0]["matchedProductId"] == "p1"

    def test_unmatched_ingredient_marked_unpriced(self, seeded):
        _, matcher = seeded
        out = matcher.match_ingredients(
            [{"searchKey": "dragon fruit"}], STORE)
        assert out[0]["unpriced"] is True
        assert out[0]["currentPrice"] is None
        assert out[0]["matchConfidence"] == 0.0


class TestLegacyProductFallback:
    def test_product_without_searchTokens_matched_via_category(self, pricing_db):
        # A product that predates the searchTokens backfill still matches
        # through the category-hint fallback path.
        pricing_db["products"].insert_one({
            "_id": "legacy",
            "name": "Chicken Drumsticks Value Pack",
            "category": "chicken",
            "storePrice": {STORE: {"currentPrice": 8.0, "isSpecial": False}},
        })
        matcher = IngredientMatcher(pricing_db)
        result = matcher.match("chicken drumsticks", STORE)
        assert result is not None
        assert result.product_id == "legacy"
