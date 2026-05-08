"""Tests for MongoDB storage operations in mongodb.py."""

import pytest
import mongomock
from unittest.mock import patch
from mongodb import store_recipes, store_bundle, generate_recipe_id, generate_bundle_id


def make_meal(name="Chicken Stir Fry", **kwargs):
    return {
        "id": "r1",
        "name": name,
        "serves": 4,
        "leftovers": True,
        "cookTime": "30 mins",
        "description": "Quick weeknight meal",
        "recipeUrl": "",
        "ingredients": [
            {"name": "Chicken breast", "amount": "400g", "estimatedCost": 5.00},
        ],
        "method": ["Step 1", "Step 2"],
        **kwargs,
    }


def make_plan(meals=None, week_summary="5 hearty meals", total=45.50):
    return {
        "weekSummary": week_summary,
        "estimatedTotal": total,
        "meals": meals or [make_meal()],
        "shoppingList": [],
    }


@pytest.fixture
def mock_client():
    return mongomock.MongoClient()


class TestStoreRecipes:
    def test_stores_recipe(self, mock_client):
        plan = make_plan()
        with patch("mongodb._client", mock_client):
            count, ids = store_recipes(plan, "2026-05-05")

        assert count == 1
        assert len(ids) == 1
        stored = mock_client["paknsave-meals"]["recipes"].find_one({"recipeId": ids[0]})
        assert stored is not None
        assert stored["name"] == "Chicken Stir Fry"

    def test_returns_recipe_ids(self, mock_client):
        plan = make_plan(meals=[make_meal("Meal A"), make_meal("Meal B")])
        with patch("mongodb._client", mock_client):
            _, ids = store_recipes(plan, "2026-05-05")

        assert len(ids) == 2
        assert generate_recipe_id({"name": "Meal A"}) in ids
        assert generate_recipe_id({"name": "Meal B"}) in ids

    def test_strips_shared_with_from_ingredients(self, mock_client):
        meal = make_meal()
        meal["ingredients"] = [
            {"name": "Garlic", "amount": "2 cloves", "estimatedCost": 0.5, "sharedWith": ["Other Meal"]}
        ]
        plan = make_plan(meals=[meal])
        with patch("mongodb._client", mock_client):
            _, ids = store_recipes(plan, "2026-05-05")

        stored = mock_client["paknsave-meals"]["recipes"].find_one({"recipeId": ids[0]})
        ing = stored["ingredients"][0]
        assert "sharedWith" not in ing

    def test_upserts_existing_recipe(self, mock_client):
        plan = make_plan()
        with patch("mongodb._client", mock_client):
            store_recipes(plan, "2026-05-01")
            plan["meals"][0]["description"] = "Updated description"
            _, ids = store_recipes(plan, "2026-05-05")

        all_stored = list(mock_client["paknsave-meals"]["recipes"].find({"recipeId": ids[0]}))
        assert len(all_stored) == 1
        assert all_stored[0]["description"] == "Updated description"

    def test_tracks_usage_history(self, mock_client):
        plan = make_plan()
        with patch("mongodb._client", mock_client):
            _, ids = store_recipes(plan, "2026-05-05")
            store_recipes(plan, "2026-05-12")

        stored = mock_client["paknsave-meals"]["recipes"].find_one({"recipeId": ids[0]})
        assert "2026-05-05" in stored["usageHistory"]
        assert "2026-05-12" in stored["usageHistory"]

    def test_empty_plan_returns_zero_count(self, mock_client):
        with patch("mongodb._client", mock_client):
            count, ids = store_recipes({"meals": []}, "2026-05-05")

        assert count == 0
        assert ids == []


class TestStoreBundle:
    def test_stores_bundle(self, mock_client):
        plan = make_plan()
        recipe_ids = [generate_recipe_id({"name": "Chicken Stir Fry"})]

        with patch("mongodb._client", mock_client):
            bundle_id = store_bundle(plan, "2026-05-05", recipe_ids)

        assert bundle_id is not None
        stored = mock_client["paknsave-meals"]["bundles"].find_one({"bundleId": bundle_id})
        assert stored is not None
        assert stored["week"] == "2026-05-05"
        assert stored["active"] is True

    def test_bundle_id_is_deterministic(self, mock_client):
        plan = make_plan()
        recipe_ids = ["r1"]

        with patch("mongodb._client", mock_client):
            id1 = store_bundle(plan, "2026-05-05", recipe_ids)
            id2 = store_bundle(plan, "2026-05-05", recipe_ids)

        assert id1 == id2

    def test_deactivates_other_bundles_for_same_week(self, mock_client):
        mock_client["paknsave-meals"]["bundles"].insert_one({
            "bundleId": "old-bundle",
            "week": "2026-05-05",
            "active": True,
        })

        plan = make_plan(week_summary="New plan")
        with patch("mongodb._client", mock_client):
            store_bundle(plan, "2026-05-05", [])

        old = mock_client["paknsave-meals"]["bundles"].find_one({"bundleId": "old-bundle"})
        assert old["active"] is False

    def test_does_not_deactivate_other_weeks(self, mock_client):
        mock_client["paknsave-meals"]["bundles"].insert_one({
            "bundleId": "prev-week-bundle",
            "week": "2026-04-28",
            "active": True,
        })

        plan = make_plan()
        with patch("mongodb._client", mock_client):
            store_bundle(plan, "2026-05-05", [])

        prev = mock_client["paknsave-meals"]["bundles"].find_one({"bundleId": "prev-week-bundle"})
        assert prev["active"] is True

    def test_adds_bundle_id_to_recipe_history(self, mock_client):
        recipe_id = generate_recipe_id({"name": "Chicken Stir Fry"})
        mock_client["paknsave-meals"]["recipes"].insert_one({
            "recipeId": recipe_id,
            "name": "Chicken Stir Fry",
            "bundleHistory": [],
        })

        plan = make_plan()
        with patch("mongodb._client", mock_client):
            bundle_id = store_bundle(plan, "2026-05-05", [recipe_id])

        recipe = mock_client["paknsave-meals"]["recipes"].find_one({"recipeId": recipe_id})
        assert bundle_id in recipe["bundleHistory"]
