"""Tests for /api/enhancements routes (MEA-50, MEA-52, MEA-53)."""

import pytest

RECIPE_THAI_CURRY = {
    "recipeId": "thai-curry-abc",
    "name": "Thai Chicken Curry",
    "description": "Aromatic coconut curry",
    "ingredients": [
        {"name": "Chicken Thighs", "amount": "600g"},
        {"name": "Coconut Milk", "amount": "400ml"},
        {"name": "Fish Sauce", "amount": "2 tbsp"},
    ],
    "method": [],
}

RECIPE_PASTA = {
    "recipeId": "pasta-bake-xyz",
    "name": "Pasta Bake",
    "description": "Hearty pasta with mince",
    "ingredients": [
        {"name": "Pasta", "amount": "300g"},
        {"name": "Beef Mince", "amount": "500g"},
        {"name": "Tomato Sauce", "amount": "500ml"},
    ],
    "method": [],
}

ENHANCEMENT_CORIANDER = {
    "enhancementId": "fresh-coriander-lime",
    "name": "Fresh Coriander & Lime",
    "description": "Brightens Thai and Asian curries",
    "estimatedCost": 2.50,
    "ingredients": [{"name": "Fresh Coriander", "amount": "1 bunch"}],
    "compatibleIngredients": ["coconut milk", "fish sauce"],
    "compatibleRecipeKeywords": ["thai", "curry"],
    "tags": ["fresh"],
}

ENHANCEMENT_GARLIC_BREAD = {
    "enhancementId": "garlic-bread",
    "name": "Garlic Bread",
    "description": "Classic side for pasta",
    "estimatedCost": 3.00,
    "ingredients": [{"name": "Baguette", "amount": "1 loaf"}],
    "compatibleIngredients": ["pasta", "mince"],
    "compatibleRecipeKeywords": ["bolognese", "bake", "italian"],
    "tags": ["side"],
}


class TestListEnhancements:
    def test_returns_all_enhancements(self, client, meals_db):
        meals_db["enhancements"].insert_many([
            dict(ENHANCEMENT_CORIANDER),
            dict(ENHANCEMENT_GARLIC_BREAD),
        ])
        resp = client.get("/api/enhancements/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_returns_empty_list_when_none_seeded(self, client):
        resp = client.get("/api/enhancements/")
        assert resp.status_code == 200
        assert resp.json() == []


class TestGetEnhancement:
    def test_returns_enhancement_by_id(self, client, meals_db):
        meals_db["enhancements"].insert_one(dict(ENHANCEMENT_CORIANDER))
        resp = client.get("/api/enhancements/fresh-coriander-lime")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Fresh Coriander & Lime"

    def test_returns_404_for_unknown_id(self, client):
        resp = client.get("/api/enhancements/does-not-exist")
        assert resp.status_code == 404


class TestGetEnhancementsForRecipe:
    def test_matches_by_compatible_ingredient(self, client, meals_db):
        """Coriander & Lime matches Thai Curry because recipe has coconut milk."""
        meals_db["recipes"].insert_one(dict(RECIPE_THAI_CURRY))
        meals_db["enhancements"].insert_many([
            dict(ENHANCEMENT_CORIANDER),
            dict(ENHANCEMENT_GARLIC_BREAD),
        ])
        resp = client.get("/api/enhancements/for-recipe/thai-curry-abc")
        assert resp.status_code == 200
        data = resp.json()
        names = [e["name"] for e in data["enhancements"]]
        assert "Fresh Coriander & Lime" in names
        assert "Garlic Bread" not in names

    def test_matches_by_compatible_recipe_keyword(self, client, meals_db):
        """Garlic Bread matches Pasta Bake via recipe keyword 'bake'."""
        meals_db["recipes"].insert_one(dict(RECIPE_PASTA))
        meals_db["enhancements"].insert_many([
            dict(ENHANCEMENT_CORIANDER),
            dict(ENHANCEMENT_GARLIC_BREAD),
        ])
        resp = client.get("/api/enhancements/for-recipe/pasta-bake-xyz")
        assert resp.status_code == 200
        names = [e["name"] for e in resp.json()["enhancements"]]
        assert "Garlic Bread" in names
        assert "Fresh Coriander & Lime" not in names

    def test_returns_404_for_unknown_recipe(self, client):
        resp = client.get("/api/enhancements/for-recipe/no-such-recipe")
        assert resp.status_code == 404

    def test_returns_empty_when_no_enhancements_match(self, client, meals_db):
        unrelated_recipe = {
            "recipeId": "plain-steak",
            "name": "Plain Steak",
            "description": "Simple grilled steak",
            "ingredients": [{"name": "Beef Steak", "amount": "250g"}],
            "method": [],
        }
        meals_db["recipes"].insert_one(unrelated_recipe)
        meals_db["enhancements"].insert_one(dict(ENHANCEMENT_CORIANDER))
        resp = client.get("/api/enhancements/for-recipe/plain-steak")
        assert resp.status_code == 200
        assert resp.json()["enhancements"] == []
