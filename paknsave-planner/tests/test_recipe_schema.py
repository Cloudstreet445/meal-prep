"""Tests for recipe schema v2 — parsing and validation (MEA-109, MEA-110)."""

import copy
import pytest

from recipe_schema import (
    parse_amount, is_staple_name, validate_recipe, validate_generated_recipe,
)


def valid_v2_recipe():
    """A fully-formed v2 recipe that passes strict generation validation."""
    return {
        "name": "Test Chicken Tray Bake",
        "description": "A simple one-pan chicken bake.",
        "serves": 4,
        "primaryProtein": "chicken",
        "proteinSubstitutes": [
            {"name": "pork chops", "searchKey": "pork chops", "ratio": 1.0, "note": "add 5 min"},
        ],
        "time": {
            "prepMinutes": 15, "activeCookMinutes": 20, "passiveCookMinutes": 25,
            "totalRangeMinutes": [55, 70],
        },
        "equipment": ["oven"],
        "skillLevel": "easy",
        "spiceLevel": 1,
        "mealType": "dinner",
        "tags": ["one-pan", "tray-bake"],
        "season": ["all"],
        "dietaryFlags": [],
        "allergens": ["gluten"],
        "costTier": "budget",
        "leftovers": {
            "keepsInFridgeDays": 3, "freezable": True,
            "reheatMethod": "oven", "lunchFriendly": True,
        },
        "nutritionPerServe": {"calories": 480, "proteinG": 34},
        "ingredients": [
            {
                "name": "Chicken Drumsticks",
                "amount": {"value": 1, "unit": "kg", "display": "1kg"},
                "searchKey": "chicken drumsticks",
                "searchKeyVariants": ["chicken drumsticks", "drumsticks"],
                "category": "meat", "substitutes": [],
                "optional": False, "pantryStaple": False, "prepNote": None,
            },
            {
                "name": "Olive Oil",
                "amount": {"value": 2, "unit": "tbsp", "display": "2 tbsp"},
                "searchKey": "olive oil",
                "searchKeyVariants": ["olive oil", "cooking oil"],
                "category": "pantry", "substitutes": [],
                "optional": False, "pantryStaple": True, "prepNote": None,
            },
        ],
        "method": ["Step 1: season chicken.", "Step 2: bake 45 minutes."],
    }


class TestParseAmount:
    def test_parses_kilograms(self):
        assert parse_amount("1kg") == {"value": 1.0, "unit": "kg", "display": "1kg"}

    def test_parses_grams_with_descriptor(self):
        result = parse_amount("500g chicken")
        assert result["value"] == 500.0 and result["unit"] == "g"

    def test_bare_number_becomes_each(self):
        assert parse_amount("2 medium")["unit"] == "ea"

    def test_unparseable_falls_back_to_display_only(self):
        assert parse_amount("to taste") == {"value": None, "unit": None, "display": "to taste"}

    def test_dict_input_passes_through(self):
        structured = {"value": 3, "unit": "cup", "display": "3 cups"}
        assert parse_amount(structured) == structured


class TestStapleDetection:
    def test_olive_oil_is_staple(self):
        assert is_staple_name("Extra Virgin Olive Oil") is True

    def test_chicken_is_not_staple(self):
        assert is_staple_name("Chicken Drumsticks") is False


class TestValidateRecipe:
    def test_valid_v2_recipe_has_no_errors(self):
        assert validate_recipe(valid_v2_recipe()) == []

    def test_missing_required_field_is_reported(self):
        recipe = valid_v2_recipe()
        del recipe["primaryProtein"]
        errors = validate_recipe(recipe)
        assert any("primaryProtein" in e for e in errors)

    def test_banned_price_field_on_ingredient_is_reported(self):
        recipe = valid_v2_recipe()
        recipe["ingredients"][0]["fromSpecial"] = True
        errors = validate_recipe(recipe)
        assert any("fromSpecial" in e for e in errors)

    def test_invalid_ingredient_category_is_reported(self):
        recipe = valid_v2_recipe()
        recipe["ingredients"][0]["category"] = "spaceship"
        errors = validate_recipe(recipe)
        assert any("category" in e for e in errors)

    def test_inverted_time_range_is_reported(self):
        recipe = valid_v2_recipe()
        recipe["time"]["totalRangeMinutes"] = [70, 55]
        errors = validate_recipe(recipe)
        assert any("totalRangeMinutes" in e for e in errors)


class TestValidateGeneratedRecipe:
    def test_valid_recipe_passes_strict_validation(self):
        assert validate_generated_recipe(valid_v2_recipe()) == []

    def test_meat_recipe_without_substitutes_fails(self):
        recipe = valid_v2_recipe()
        recipe["proteinSubstitutes"] = []
        errors = validate_generated_recipe(recipe)
        assert any("proteinSubstitutes" in e for e in errors)

    def test_ingredient_needs_two_search_variants(self):
        recipe = valid_v2_recipe()
        recipe["ingredients"][0]["searchKeyVariants"] = ["chicken drumsticks"]
        errors = validate_generated_recipe(recipe)
        assert any("searchKeyVariants" in e for e in errors)

    def test_unflagged_staple_ingredient_fails(self):
        recipe = valid_v2_recipe()
        recipe["ingredients"][1]["pantryStaple"] = False
        errors = validate_generated_recipe(recipe)
        assert any("pantryStaple" in e for e in errors)
