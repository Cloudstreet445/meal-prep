"""Endpoint tests for /api/shopping routes."""

import pytest
from datetime import datetime


from tests.conftest import TEST_HOUSEHOLD_ID

BUNDLE = {
    "bundleId": "bundle-abc123",
    "householdId": TEST_HOUSEHOLD_ID,
    "week": "2026-05-05",
    "active": True,
    "weekSummary": "5 hearty winter meals",
    "estimatedTotal": 45.50,
    "recipeIds": ["r1", "r2"],
    "createdAt": datetime(2026, 5, 5),
    "updatedAt": datetime(2026, 5, 5),
}

RECIPES = [
    {
        "recipeId": "r1",
        "name": "Chicken Stir Fry",
        "ingredients": [
            {"name": "Chicken breast", "amount": "400g", "estimatedCost": 5.00},
            {"name": "Garlic", "amount": "3 cloves", "estimatedCost": 0.50},
        ],
    },
    {
        "recipeId": "r2",
        "name": "Pasta Bake",
        "ingredients": [
            {"name": "Pasta", "amount": "300g", "estimatedCost": 1.50},
            {"name": "Garlic", "amount": "2 cloves", "estimatedCost": 0.50},
        ],
    },
]


class TestGetLatestShopping:
    def test_returns_shopping_list(self, client, meals_db):
        meals_db["bundles"].insert_one(dict(BUNDLE))
        meals_db["recipes"].insert_many([dict(r) for r in RECIPES])

        resp = client.get("/api/shopping/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert "shoppingList" in data
        assert data["bundleId"] == "bundle-abc123"
        assert data["week"] == "2026-05-05"

    def test_deduplicates_shared_ingredients(self, client, meals_db):
        meals_db["bundles"].insert_one(dict(BUNDLE))
        meals_db["recipes"].insert_many([dict(r) for r in RECIPES])

        resp = client.get("/api/shopping/latest")
        data = resp.json()
        garlic_items = [i for i in data["shoppingList"] if i["name"] == "Garlic"]
        assert len(garlic_items) == 1

    def test_cost_is_zero_when_no_product_match(self, client, meals_db):
        meals_db["bundles"].insert_one(dict(BUNDLE))
        meals_db["recipes"].insert_many([dict(r) for r in RECIPES])

        resp = client.get("/api/shopping/latest")
        data = resp.json()
        garlic = next(i for i in data["shoppingList"] if i["name"] == "Garlic")
        # No product in pricing DB → cost falls back to 0 (live price drives cost, not stored field)
        assert garlic["estimatedCost"] == 0

    def test_shared_with_populated_for_garlic(self, client, meals_db):
        meals_db["bundles"].insert_one(dict(BUNDLE))
        meals_db["recipes"].insert_many([dict(r) for r in RECIPES])

        resp = client.get("/api/shopping/latest")
        data = resp.json()
        garlic = next(i for i in data["shoppingList"] if i["name"] == "Garlic")
        assert set(garlic["sharedWith"]) == {"Chicken Stir Fry", "Pasta Bake"}

    def test_returns_404_when_no_active_bundle(self, client):
        resp = client.get("/api/shopping/latest")
        assert resp.status_code == 404

    def test_total_is_sum_of_items(self, client, meals_db):
        meals_db["bundles"].insert_one(dict(BUNDLE))
        meals_db["recipes"].insert_many([dict(r) for r in RECIPES])

        resp = client.get("/api/shopping/latest")
        data = resp.json()
        item_total = round(sum(i["estimatedCost"] for i in data["shoppingList"]), 2)
        assert data["estimatedTotal"] == item_total

    def test_empty_recipes_gives_empty_list(self, client, meals_db):
        bundle_no_recipes = {**BUNDLE, "recipeIds": []}
        meals_db["bundles"].insert_one(bundle_no_recipes)

        resp = client.get("/api/shopping/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["shoppingList"] == []
        assert data["estimatedTotal"] == 0.0

    def test_scraped_at_included_when_products_exist(self, client, meals_db, pricing_db):
        meals_db["bundles"].insert_one(dict(BUNDLE))
        pricing_db["products"].insert_one({"name": "Chicken", "lastChecked": "2026-05-09"})

        resp = client.get("/api/shopping/latest")
        assert resp.status_code == 200
        assert resp.json()["scrapedAt"] == "2026-05-09"

    def test_scraped_at_is_none_when_no_products(self, client, meals_db):
        meals_db["bundles"].insert_one(dict(BUNDLE))

        resp = client.get("/api/shopping/latest")
        assert resp.status_code == 200
        assert resp.json()["scrapedAt"] is None


class TestAlternatives:
    def test_returns_alternatives_cheapest_first(self, client, pricing_db):
        pricing_db["products"].insert_many([
            {"_id": "P-cheap", "name": "Pams Chicken Breast 1kg", "brand": "Pams",
             "sizeGrams": 1000.0,
             "storePrice": {"paknsave-lower-hutt": {"currentPrice": 9.0, "isSpecial": False}}},
            {"_id": "P-premium", "name": "Free Range Chicken Breast 1kg",
             "sizeGrams": 1000.0,
             "storePrice": {"paknsave-lower-hutt": {"currentPrice": 15.0, "isSpecial": False}}},
        ])
        resp = client.get("/api/shopping/alternatives",
                          params={"ingredient": "Chicken breast", "amount": "1kg"})
        assert resp.status_code == 200
        alts = resp.json()["alternatives"]
        assert [a["productId"] for a in alts] == ["P-cheap", "P-premium"]
        assert alts[0]["brand"] == "Pams"

    def test_returns_empty_when_no_match(self, client, pricing_db):
        resp = client.get("/api/shopping/alternatives", params={"ingredient": "Unobtanium"})
        assert resp.status_code == 200
        assert resp.json()["alternatives"] == []
