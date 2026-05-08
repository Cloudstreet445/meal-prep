"""Tests for substitution matching logic and /substitutions/suggest endpoint."""

import pytest
from src.routers.substitutions import _match_key


class TestMatchKey:
    def test_exact_key_match(self):
        assert _match_key("chicken") == "chicken"

    def test_exact_key_match_case_insensitive(self):
        assert _match_key("Chicken") == "chicken"

    def test_compound_key_match(self):
        # "chicken breast" is a key and should beat the shorter "chicken" key
        assert _match_key("chicken breast") == "chicken breast"

    def test_substring_match(self):
        # "pork mince 500g" contains "mince"
        assert _match_key("pork mince 500g") == "mince"

    def test_longest_substring_wins(self):
        # "chicken breast fillets" contains both "chicken breast" and "chicken"
        # longest match should win
        assert _match_key("chicken breast fillets") == "chicken breast"

    def test_no_match_returns_none(self):
        assert _match_key("oregano") is None

    def test_no_match_for_short_unrelated_word(self):
        assert _match_key("salt") is None

    def test_exact_key_takes_priority_over_substring(self):
        # "beef" is an exact key — should match directly
        assert _match_key("beef") == "beef"

    def test_ingredient_with_size(self):
        # "salmon fillet 400g" contains "salmon"
        assert _match_key("salmon fillet 400g") == "salmon"


class TestSuggestSubstitutes:
    def test_returns_suggestions_for_known_ingredient(self, client):
        resp = client.post("/api/substitutions/suggest", json={"ingredient": "chicken"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["matchedKey"] == "chicken"
        assert len(data["suggestions"]) > 0

    def test_returns_empty_for_unknown_ingredient(self, client):
        resp = client.post("/api/substitutions/suggest", json={"ingredient": "oregano"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["matchedKey"] is None
        assert data["suggestions"] == []

    def test_echoes_ingredient_name(self, client):
        resp = client.post("/api/substitutions/suggest", json={"ingredient": "beef"})
        assert resp.json()["ingredient"] == "beef"

    def test_suggestion_includes_required_fields(self, client):
        resp = client.post("/api/substitutions/suggest", json={"ingredient": "pork"})
        suggestions = resp.json()["suggestions"]
        for s in suggestions:
            assert "name" in s
            assert "searchTerm" in s
            assert "currentPrice" in s
            assert "isSpecial" in s

    def test_attaches_live_price_when_product_in_db(self, client, pricing_db):
        pricing_db["products"].insert_one({
            "name": "Chicken Thigh 1kg",
            "storePrice": {
                "paknsave-lower-hutt": {"currentPrice": 8.99, "isSpecial": True},
            },
        })
        resp = client.post("/api/substitutions/suggest", json={"ingredient": "pork"})
        suggestions = resp.json()["suggestions"]
        matched = next((s for s in suggestions if "Chicken Thigh" in s["name"]), None)
        assert matched is not None
        assert matched["currentPrice"] == 8.99
        assert matched["isSpecial"] is True

    def test_falls_back_to_title_name_when_not_in_db(self, client):
        # No products seeded — every suggestion should fall back to term.title()
        resp = client.post("/api/substitutions/suggest", json={"ingredient": "pasta"})
        suggestions = resp.json()["suggestions"]
        assert len(suggestions) > 0
        # All should have no price
        for s in suggestions:
            assert s["currentPrice"] is None
            assert s["isSpecial"] is False

    def test_respects_store_id(self, client, pricing_db):
        pricing_db["products"].insert_one({
            "name": "Chicken Thigh 1kg",
            "storePrice": {
                "paknsave-porirua": {"currentPrice": 9.49, "isSpecial": False},
            },
        })
        # Ask for lower-hutt — product only exists for porirua, so no price
        resp = client.post("/api/substitutions/suggest", json={
            "ingredient": "pork",
            "store_id": "paknsave-lower-hutt",
        })
        suggestions = resp.json()["suggestions"]
        matched = next((s for s in suggestions if "Chicken Thigh" in s["name"]), None)
        assert matched is None or matched["currentPrice"] is None

    def test_default_store_id_used_when_omitted(self, client, pricing_db):
        pricing_db["products"].insert_one({
            "name": "Chicken Thigh 1kg",
            "storePrice": {
                "paknsave-lower-hutt": {"currentPrice": 8.99, "isSpecial": False},
            },
        })
        # No store_id in request — should default to paknsave-lower-hutt
        resp = client.post("/api/substitutions/suggest", json={"ingredient": "pork"})
        suggestions = resp.json()["suggestions"]
        matched = next((s for s in suggestions if "Chicken Thigh" in s["name"]), None)
        assert matched is not None
        assert matched["currentPrice"] == 8.99

    def test_compound_ingredient_name_resolves(self, client):
        # "chicken breast fillets 500g" should match "chicken breast" key
        resp = client.post("/api/substitutions/suggest", json={"ingredient": "chicken breast fillets 500g"})
        assert resp.json()["matchedKey"] == "chicken breast"
