"""Endpoint tests for /api/bundle routes."""

import pytest
from datetime import datetime


BUNDLE = {
    "bundleId": "bundle-abc123",
    "week": "2026-05-05",
    "active": True,
    "weekSummary": "5 hearty winter meals",
    "estimatedTotal": 45.50,
    "recipeIds": ["chicken-stir-fry-abc123", "pasta-bake-def456"],
    "priceSnapshotDate": "2026-05-05",
    "createdAt": datetime(2026, 5, 5, 10, 0, 0),
    "updatedAt": datetime(2026, 5, 5, 10, 0, 0),
}

RECIPE_1 = {
    "recipeId": "chicken-stir-fry-abc123",
    "name": "Chicken Stir Fry",
    "serves": 4,
    "leftovers": True,
    "cookTime": "30 mins",
    "description": "Quick weeknight stir fry",
    "recipeUrl": "https://example.com/recipe",
    "ingredients": [
        {"name": "Chicken breast", "amount": "400g", "estimatedCost": 5.00},
        {"name": "Broccoli", "amount": "1 head", "estimatedCost": 2.00},
    ],
    "method": ["Heat oil in wok", "Add chicken and stir fry 5 mins"],
}

RECIPE_2 = {
    "recipeId": "pasta-bake-def456",
    "name": "Pasta Bake",
    "serves": 4,
    "leftovers": True,
    "cookTime": "45 mins",
    "description": "Cheesy pasta bake",
    "recipeUrl": "https://example.com/pasta",
    "ingredients": [
        {"name": "Pasta", "amount": "300g", "estimatedCost": 1.50},
        {"name": "Tasty cheese", "amount": "200g", "estimatedCost": 3.00},
    ],
    "method": ["Cook pasta", "Mix with sauce", "Bake 25 mins"],
}


class TestGetLatestBundle:
    def test_returns_active_bundle_with_recipes(self, client, meals_db):
        meals_db["bundles"].insert_one(dict(BUNDLE))
        meals_db["recipes"].insert_many([dict(RECIPE_1), dict(RECIPE_2)])

        resp = client.get("/api/bundle/latest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["bundleId"] == "bundle-abc123"
        assert data["weekSummary"] == "5 hearty winter meals"
        assert len(data["recipes"]) == 2

    def test_returns_404_when_no_active_bundle(self, client):
        resp = client.get("/api/bundle/latest")
        assert resp.status_code == 404

    def test_inactive_bundle_is_not_returned(self, client, meals_db):
        meals_db["bundles"].insert_one({**BUNDLE, "active": False})
        resp = client.get("/api/bundle/latest")
        assert resp.status_code == 404

    def test_recipes_returned_in_bundle_order(self, client, meals_db):
        meals_db["bundles"].insert_one(dict(BUNDLE))
        # Insert recipes in reversed order — bundle should still return them in recipeIds order
        meals_db["recipes"].insert_many([dict(RECIPE_2), dict(RECIPE_1)])

        resp = client.get("/api/bundle/latest")
        data = resp.json()
        recipe_ids = [r["recipeId"] for r in data["recipes"]]
        assert recipe_ids == BUNDLE["recipeIds"]

    def test_returns_most_recent_active_bundle(self, client, meals_db):
        older = {**BUNDLE, "bundleId": "older", "week": "2026-04-28", "active": True}
        newer = {**BUNDLE, "bundleId": "newer", "week": "2026-05-05", "active": True}
        meals_db["bundles"].insert_many([older, newer])

        resp = client.get("/api/bundle/latest")
        assert resp.json()["bundleId"] == "newer"

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestBundleHistory:
    def test_returns_one_entry_per_week(self, client, meals_db):
        meals_db["bundles"].insert_many([
            {**BUNDLE, "bundleId": "b1", "week": "2026-05-05", "active": True},
            {**BUNDLE, "bundleId": "b2", "week": "2026-05-05", "active": False},
            {**BUNDLE, "bundleId": "b3", "week": "2026-04-28", "active": True},
        ])

        resp = client.get("/api/bundle/history")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_newest_week_is_first(self, client, meals_db):
        meals_db["bundles"].insert_many([
            {**BUNDLE, "bundleId": "b1", "week": "2026-04-28", "active": True},
            {**BUNDLE, "bundleId": "b2", "week": "2026-05-05", "active": True},
        ])

        resp = client.get("/api/bundle/history")
        weeks = resp.json()
        assert weeks[0]["week"] == "2026-05-05"
        assert weeks[1]["week"] == "2026-04-28"

    def test_bundle_count_per_week(self, client, meals_db):
        meals_db["bundles"].insert_many([
            {**BUNDLE, "bundleId": "b1", "week": "2026-05-05", "active": True},
            {**BUNDLE, "bundleId": "b2", "week": "2026-05-05", "active": False},
        ])

        resp = client.get("/api/bundle/history")
        week = resp.json()[0]
        assert week["bundleCount"] == 2

    def test_returns_empty_list_with_no_bundles(self, client):
        resp = client.get("/api/bundle/history")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetBundlesForWeek:
    def test_returns_all_bundles_for_week(self, client, meals_db):
        meals_db["bundles"].insert_many([
            {**BUNDLE, "bundleId": "b1", "week": "2026-05-05"},
            {**BUNDLE, "bundleId": "b2", "week": "2026-05-05"},
            {**BUNDLE, "bundleId": "b3", "week": "2026-04-28"},
        ])

        resp = client.get("/api/bundle/week/2026-05-05")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_returns_404_for_unknown_week(self, client):
        resp = client.get("/api/bundle/week/2020-01-01")
        assert resp.status_code == 404


class TestGetBundle:
    def test_returns_bundle_by_id(self, client, meals_db):
        meals_db["bundles"].insert_one(dict(BUNDLE))
        meals_db["recipes"].insert_many([dict(RECIPE_1), dict(RECIPE_2)])

        resp = client.get("/api/bundle/bundle-abc123")
        assert resp.status_code == 200
        assert resp.json()["bundleId"] == "bundle-abc123"

    def test_returns_404_for_unknown_bundle(self, client):
        resp = client.get("/api/bundle/does-not-exist")
        assert resp.status_code == 404


class TestActivateBundle:
    def test_activates_bundle(self, client, meals_db):
        meals_db["bundles"].insert_many([
            {**BUNDLE, "bundleId": "b1", "week": "2026-05-05", "active": True},
            {**BUNDLE, "bundleId": "b2", "week": "2026-05-05", "active": False},
        ])

        resp = client.post("/api/bundle/b2/activate")
        assert resp.status_code == 200
        assert resp.json()["activated"] == "b2"

        assert meals_db["bundles"].find_one({"bundleId": "b2"})["active"] is True
        assert meals_db["bundles"].find_one({"bundleId": "b1"})["active"] is False

    def test_only_deactivates_same_week_bundles(self, client, meals_db):
        meals_db["bundles"].insert_many([
            {**BUNDLE, "bundleId": "b1", "week": "2026-05-05", "active": True},
            {**BUNDLE, "bundleId": "b2", "week": "2026-05-05", "active": False},
            {**BUNDLE, "bundleId": "b3", "week": "2026-04-28", "active": True},
        ])

        client.post("/api/bundle/b2/activate")
        assert meals_db["bundles"].find_one({"bundleId": "b3"})["active"] is True

    def test_returns_404_for_unknown_bundle(self, client):
        resp = client.post("/api/bundle/nonexistent/activate")
        assert resp.status_code == 404
