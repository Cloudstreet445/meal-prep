"""Endpoint tests for /api/bundle routes."""

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


class TestHouseholdScoping:
    def test_latest_requires_auth(self, anon_client, meals_db):
        meals_db["bundles"].insert_one(dict(BUNDLE))
        resp = anon_client.get("/api/bundle/latest")
        assert resp.status_code == 401

    def test_other_household_bundle_not_returned(self, client, meals_db):
        # Active bundle owned by a different household must be invisible.
        meals_db["bundles"].insert_one({**BUNDLE, "bundleId": "other", "householdId": "other-hh"})
        resp = client.get("/api/bundle/latest")
        assert resp.status_code == 404

    def test_get_bundle_by_id_scoped_to_household(self, client, meals_db):
        meals_db["bundles"].insert_one({**BUNDLE, "bundleId": "foreign", "householdId": "other-hh"})
        resp = client.get("/api/bundle/foreign")
        assert resp.status_code == 404


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


class TestCustomBundle:
    def test_creates_bundle_and_returns_bundle_id(self, client, meals_db):
        meals_db["recipes"].insert_many([dict(RECIPE_1), dict(RECIPE_2)])
        resp = client.post("/api/bundle/custom", json={
            "recipeIds": ["chicken-stir-fry-abc123", "pasta-bake-def456"],
            "week": "2026-05-12",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["bundleId"].startswith("custom-")
        assert data["week"] == "2026-05-12"

    def test_bundle_saved_active_with_correct_fields(self, client, meals_db):
        meals_db["recipes"].insert_one(dict(RECIPE_1))
        resp = client.post("/api/bundle/custom", json={
            "recipeIds": ["chicken-stir-fry-abc123"],
            "week": "2026-05-12",
        })
        bundle_id = resp.json()["bundleId"]
        doc = meals_db["bundles"].find_one({"bundleId": bundle_id})
        assert doc["active"] is True
        assert doc["generatedBy"] == "user"
        assert doc["recipeIds"] == ["chicken-stir-fry-abc123"]

    def test_deactivates_existing_bundle_for_same_week(self, client, meals_db):
        meals_db["bundles"].insert_one({**BUNDLE, "bundleId": "existing", "week": "2026-05-12", "active": True})
        meals_db["recipes"].insert_one(dict(RECIPE_1))
        client.post("/api/bundle/custom", json={
            "recipeIds": ["chicken-stir-fry-abc123"],
            "week": "2026-05-12",
        })
        assert meals_db["bundles"].find_one({"bundleId": "existing"})["active"] is False

    def test_computes_estimated_total_from_ingredients(self, client, meals_db):
        meals_db["recipes"].insert_many([dict(RECIPE_1), dict(RECIPE_2)])
        resp = client.post("/api/bundle/custom", json={
            "recipeIds": ["chicken-stir-fry-abc123", "pasta-bake-def456"],
            "week": "2026-05-12",
        })
        # RECIPE_1: 5.00 + 2.00 = 7.00, RECIPE_2: 1.50 + 3.00 = 4.50
        assert resp.json()["estimatedTotal"] == 11.50

    def test_unknown_recipe_returns_422(self, client):
        resp = client.post("/api/bundle/custom", json={
            "recipeIds": ["does-not-exist"],
            "week": "2026-05-12",
        })
        assert resp.status_code == 422

    def test_empty_recipe_list_returns_422(self, client):
        resp = client.post("/api/bundle/custom", json={
            "recipeIds": [],
            "week": "2026-05-12",
        })
        assert resp.status_code == 422


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
