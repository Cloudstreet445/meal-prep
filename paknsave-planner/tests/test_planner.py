"""Tests for market data queries in planner.py."""

import pytest
import mongomock
from unittest.mock import patch
from datetime import datetime, timedelta


STORE_ID = "paknsave-lower-hutt"

_STORE_NAME_MAP = {
    "paknsave-lower-hutt": "PAK'nSAVE Lower Hutt",
    "paknsave-porirua":    "PAK'nSAVE Porirua",
}


def make_product(name, category, price, is_special=False, days_ago=0, store_id=STORE_ID):
    """Build a product document using the flat pricing schema."""
    last_checked = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    return {
        "name":          name,
        "category":      category,
        "size":          "500g",
        "sourceSite":    "paknsave",
        "storeId":       _STORE_NAME_MAP.get(store_id, store_id),
        "currentPrice":  price,
        "isSpecial":     is_special,
        "unitPrice":     f"${price:.2f}/kg",
        "maxPrice90d":   price + 2.00,
        "avgPrice90d":   price + 1.00,
        "lastChecked":   last_checked,
    }


@pytest.fixture
def populated_client():
    client = mongomock.MongoClient()
    db = client["paknsave-pricing"]
    db["products"].insert_many([
        make_product("Chicken Breast", "chicken", 8.00, is_special=True),
        make_product("Pork Shoulder", "pork", 10.00),
        make_product("Broccoli", "fresh-vegetables", 2.50),
        make_product("Capsicum", "fresh-vegetables", 3.00, is_special=True),
        make_product("Pasta Penne", "pasta", 2.00),
        make_product("Full Cream Milk", "milk", 3.50),
        # excluded items
        make_product("Salmon Fillet", "seafood", 15.00),
        make_product("Sliced Mushrooms", "fresh-vegetables", 2.00),
        make_product("Canned Tuna", "canned-fish", 2.50),
    ])
    return client


class TestGetMarketData:
    def test_returns_market_data_with_all_categories(self, populated_client):
        with patch("planner._client", populated_client):
            from planner import get_market_data
            data = get_market_data()

        assert hasattr(data, "proteins_on_special")
        assert hasattr(data, "proteins_cheap")
        assert hasattr(data, "beef_mince_special")
        assert hasattr(data, "veges_cheap")
        assert hasattr(data, "veges_special")
        assert hasattr(data, "pantry")
        assert hasattr(data, "dairy")

    def test_proteins_on_special_includes_chicken_on_special(self, populated_client):
        with patch("planner._client", populated_client):
            from planner import get_market_data
            data = get_market_data()

        names = [p["name"] for p in data.proteins_on_special]
        assert "Chicken Breast" in names

    def test_excludes_seafood_category(self, populated_client):
        with patch("planner._client", populated_client):
            from planner import get_market_data
            data = get_market_data()

        all_items = (
            data.proteins_on_special + data.proteins_cheap +
            data.veges_cheap + data.pantry + data.dairy
        )
        categories = [p["category"] for p in all_items]
        assert "seafood" not in categories
        assert "canned-fish" not in categories

    def test_excludes_mushroom_keyword(self, populated_client):
        with patch("planner._client", populated_client):
            from planner import get_market_data
            data = get_market_data()

        all_items = (
            data.proteins_on_special + data.proteins_cheap +
            data.veges_cheap + data.pantry + data.dairy
        )
        names = [p["name"].lower() for p in all_items]
        assert not any("mushroom" in n for n in names)

    def test_excludes_stale_products(self):
        client = mongomock.MongoClient()
        db = client["paknsave-pricing"]
        db["products"].insert_many([
            make_product("Fresh Chicken", "chicken", 8.00, is_special=True, days_ago=1),
            make_product("Stale Chicken", "chicken", 5.00, is_special=True, days_ago=10),
        ])

        with patch("planner._client", client):
            from planner import get_market_data
            data = get_market_data()

        names = [p["name"] for p in data.proteins_on_special]
        assert "Fresh Chicken" in names
        assert "Stale Chicken" not in names

    def test_veges_cheap_only_includes_under_threshold(self):
        client = mongomock.MongoClient()
        db = client["paknsave-pricing"]
        db["products"].insert_many([
            make_product("Cheap Broccoli", "fresh-vegetables", 2.00),
            make_product("Expensive Broccoli", "fresh-vegetables", 8.00),
        ])

        with patch("planner._client", client):
            from planner import get_market_data
            data = get_market_data()

        names = [p["name"] for p in data.veges_cheap]
        assert "Cheap Broccoli" in names
        assert "Expensive Broccoli" not in names

    def test_result_items_have_expected_keys(self, populated_client):
        with patch("planner._client", populated_client):
            from planner import get_market_data
            data = get_market_data()

        all_items = data.proteins_on_special + data.veges_cheap + data.pantry
        for item in all_items:
            assert "name" in item
            assert "price" in item
            assert "category" in item
            assert "isSpecial" in item

    def test_uses_store_id_for_queries(self):
        """Products only visible to the queried store are returned; other-store products are not."""
        client = mongomock.MongoClient()
        db = client["paknsave-pricing"]
        db["products"].insert_many([
            make_product("Lower Hutt Chicken", "chicken", 7.00, is_special=True, store_id=STORE_ID),
            make_product("Other Store Chicken", "chicken", 6.00, is_special=True, store_id="paknsave-other"),
        ])

        with patch("planner._client", client):
            from planner import get_market_data
            data = get_market_data(store_id=STORE_ID)

        names = [p["name"] for p in data.proteins_on_special]
        assert "Lower Hutt Chicken" in names
        assert "Other Store Chicken" not in names
