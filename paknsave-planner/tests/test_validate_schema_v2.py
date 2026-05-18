"""Tests for schema v2 validation checks (MEA-114)."""

import pytest

from validate_schema_v2 import (
    check_time_sanity, check_enums, check_pantry_staples, distribution_report,
)


def recipe(**overrides):
    base = {
        "name": "R", "primaryProtein": "chicken", "season": ["all"],
        "costTier": "budget", "skillLevel": "easy", "mealType": "dinner",
        "equipment": ["oven"],
        "time": {"prepMinutes": 10, "activeCookMinutes": 20,
                 "passiveCookMinutes": 15, "totalRangeMinutes": [40, 50]},
        "ingredients": [],
    }
    base.update(overrides)
    return base


class TestTimeSanity:
    def test_valid_time_passes(self):
        assert check_time_sanity([recipe()])["status"] == "PASS"

    def test_inverted_range_fails(self):
        bad = recipe(time={"totalRangeMinutes": [60, 40]})
        result = check_time_sanity([bad])
        assert result["status"] == "FAIL"
        assert "R" in result["badRange"]

    def test_long_recipe_flagged_as_outlier(self):
        slow = recipe(time={"totalRangeMinutes": [100, 150]})
        result = check_time_sanity([slow])
        assert result["outliersOver120min"]


class TestEnums:
    def test_valid_enums_pass(self):
        assert check_enums([recipe()])["status"] == "PASS"

    def test_invalid_equipment_fails(self):
        result = check_enums([recipe(equipment=["teleporter"])])
        assert result["status"] == "FAIL"
        assert result["errorCount"] == 1

    def test_invalid_ingredient_category_fails(self):
        bad = recipe(ingredients=[{"name": "X", "category": "nonsense"}])
        assert check_enums([bad])["status"] == "FAIL"


class TestPantryStaples:
    def test_unflagged_staple_is_reported(self):
        bad = recipe(ingredients=[{"name": "Sea Salt", "pantryStaple": False}])
        result = check_pantry_staples([bad])
        assert result["misflaggedCount"] == 1

    def test_correctly_flagged_staple_passes(self):
        ok = recipe(ingredients=[{"name": "Sea Salt", "pantryStaple": True}])
        assert check_pantry_staples([ok])["status"] == "PASS"


class TestDistribution:
    def test_counts_proteins_and_total(self):
        report = distribution_report([recipe(), recipe(primaryProtein="pork")])
        assert report["totalRecipes"] == 2
        assert report["proteins"] == {"chicken": 1, "pork": 1}

    def test_counts_needs_regen(self):
        flagged = recipe(qualityFlags={"needsRegen": True})
        assert distribution_report([flagged])["needsRegen"] == 1
