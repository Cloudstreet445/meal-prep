"""Endpoint tests for /api/shopping routes."""

import pytest
from datetime import datetime


BUNDLE = {
    "bundleId": "bundle-abc123",
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

    def test_sums_cost_for_shared_ingredients(self, client, meals_db):
        meals_db["bundles"].insert_one(dict(BUNDLE))
        meals_db["recipes"].insert_many([dict(r) for r in RECIPES])

        resp = client.get("/api/shopping/latest")
        data = resp.json()
        garlic = next(i for i in data["shoppingList"] if i["name"] == "Garlic")
        assert garlic["estimatedCost"] == 1.00

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
