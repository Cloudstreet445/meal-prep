"""Endpoint tests for /api/recipe routes."""

import pytest
from datetime import datetime
from tests.conftest import TEST_USER_ID

RECIPE = {
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
    "method": ["Heat oil", "Add chicken"],
    "usageHistory": ["2026-04-28", "2026-05-05"],
    "bundleHistory": ["bundle-old", "bundle-new"],
    "createdAt": datetime(2026, 4, 1),
}


class TestListRecipes:
    def test_returns_all_recipes(self, client, meals_db):
        meals_db["recipes"].insert_many([
            {**RECIPE, "recipeId": "r1", "name": "Recipe A"},
            {**RECIPE, "recipeId": "r2", "name": "Recipe B"},
        ])

        resp = client.get("/api/recipes/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_returns_empty_when_no_recipes(self, client):
        resp = client.get("/api/recipes/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_filters_by_week(self, client, meals_db):
        meals_db["recipes"].insert_many([
            {**RECIPE, "recipeId": "r1", "usageHistory": ["2026-05-05"]},
            {**RECIPE, "recipeId": "r2", "usageHistory": ["2026-04-28"]},
        ])

        resp = client.get("/api/recipes/?week=2026-05-05")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["recipeId"] == "r1"

    def test_filters_by_bundle(self, client, meals_db):
        meals_db["recipes"].insert_many([
            {**RECIPE, "recipeId": "r1", "bundleHistory": ["bundle-abc"]},
            {**RECIPE, "recipeId": "r2", "bundleHistory": ["bundle-xyz"]},
        ])

        resp = client.get("/api/recipes/?bundle=bundle-abc")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["recipeId"] == "r1"


class TestRateRecipe:
    def test_adds_thumbs_up(self, client, meals_db):
        meals_db["recipes"].insert_one(dict(RECIPE))
        resp = client.post("/api/recipes/chicken-stir-fry-abc123/rate", json={"score": 1})
        assert resp.status_code == 200
        doc = meals_db["recipes"].find_one({"recipeId": "chicken-stir-fry-abc123"})
        assert len(doc["ratings"]) == 1
        assert doc["ratings"][0]["score"] == 1
        # Ratings now attribute to the authenticated user (per-user, feeds plan gen)
        assert doc["ratings"][0]["userId"] == TEST_USER_ID

    def test_adds_thumbs_down(self, client, meals_db):
        meals_db["recipes"].insert_one(dict(RECIPE))
        resp = client.post("/api/recipes/chicken-stir-fry-abc123/rate", json={"score": -1})
        assert resp.status_code == 200
        doc = meals_db["recipes"].find_one({"recipeId": "chicken-stir-fry-abc123"})
        assert doc["ratings"][0]["score"] == -1

    def test_re_rating_overwrites_in_place(self, client, meals_db):
        """A user has at most one rating per recipe — re-rating updates the
        existing entry instead of stacking (prevents downvote spam)."""
        meals_db["recipes"].insert_one(dict(RECIPE))
        client.post("/api/recipes/chicken-stir-fry-abc123/rate", json={"score": 1})
        client.post("/api/recipes/chicken-stir-fry-abc123/rate", json={"score": -1})
        doc = meals_db["recipes"].find_one({"recipeId": "chicken-stir-fry-abc123"})
        assert len(doc["ratings"]) == 1
        assert doc["ratings"][0]["score"] == -1
        assert doc["ratings"][0]["userId"] == TEST_USER_ID

    def test_invalid_score_returns_422(self, client, meals_db):
        meals_db["recipes"].insert_one(dict(RECIPE))
        resp = client.post("/api/recipes/chicken-stir-fry-abc123/rate", json={"score": 5})
        assert resp.status_code == 422

    def test_unknown_recipe_returns_404(self, client):
        resp = client.post("/api/recipes/does-not-exist/rate", json={"score": 1})
        assert resp.status_code == 404

    def test_requires_auth(self, anon_client, meals_db):
        meals_db["recipes"].insert_one(dict(RECIPE))
        resp = anon_client.post("/api/recipes/chicken-stir-fry-abc123/rate", json={"score": 1})
        assert resp.status_code == 401


class TestGetRecipe:
    def test_returns_recipe_by_id(self, client, meals_db):
        meals_db["recipes"].insert_one(dict(RECIPE))

        resp = client.get("/api/recipes/chicken-stir-fry-abc123")
        assert resp.status_code == 200
        assert resp.json()["recipeId"] == "chicken-stir-fry-abc123"
        assert resp.json()["name"] == "Chicken Stir Fry"

    def test_returns_404_for_unknown_recipe(self, client):
        resp = client.get("/api/recipes/does-not-exist")
        assert resp.status_code == 404

    def test_recipe_has_expected_fields(self, client, meals_db):
        meals_db["recipes"].insert_one(dict(RECIPE))

        resp = client.get("/api/recipes/chicken-stir-fry-abc123")
        data = resp.json()
        assert "recipeId" in data
        assert "name" in data
        assert "ingredients" in data
        assert "method" in data
        assert "serves" in data
