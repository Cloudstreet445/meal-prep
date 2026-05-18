"""Tests for the schema v2 backfill patch (MEA-113)."""

import pytest

from backfill_v2 import build_v2_patch, migrate_ingredient_v2


def v1_recipe():
    return {
        "name": "Old Chicken Curry",
        "cookTimeMinutes": 45,
        "leftovers": True,
        "ingredients": [
            {"name": "Chicken Thighs", "amount": "600g",
             "quantity": 600, "unit": "g", "searchKey": "chicken thighs"},
            {"name": "Olive Oil", "amount": "2 tbsp",
             "quantity": 2, "unit": "tbsp", "searchKey": "olive oil"},
        ],
    }


class TestMigrateIngredient:
    def test_quantity_unit_become_structured_amount(self):
        result = migrate_ingredient_v2(v1_recipe()["ingredients"][0])
        assert result["amount"] == {"value": 600.0, "unit": "g", "display": "600g"}

    def test_search_key_variants_default_to_search_key(self):
        result = migrate_ingredient_v2(v1_recipe()["ingredients"][0])
        assert result["searchKeyVariants"] == ["chicken thighs"]

    def test_staple_ingredient_is_flagged(self):
        result = migrate_ingredient_v2(v1_recipe()["ingredients"][1])
        assert result["pantryStaple"] is True

    def test_amount_string_only_is_parsed(self):
        ing = {"name": "Salt", "amount": "1 tsp", "searchKey": "salt"}
        result = migrate_ingredient_v2(ing)
        assert result["amount"]["value"] == 1.0 and result["amount"]["unit"] == "tsp"


class TestBuildV2Patch:
    def test_time_range_inferred_from_cook_minutes(self):
        patch = build_v2_patch(v1_recipe())
        assert patch["time"]["totalRangeMinutes"] == [35, 55]

    def test_leftovers_bool_carried_into_lunch_friendly(self):
        patch = build_v2_patch(v1_recipe())
        assert patch["leftovers"]["lunchFriendly"] is True

    def test_marked_as_v1_and_needs_regen(self):
        patch = build_v2_patch(v1_recipe())
        assert patch["source"]["promptVersion"] == "v1"
        assert patch["qualityFlags"]["needsRegen"] is True

    def test_schema_version_bumped(self):
        patch = build_v2_patch(v1_recipe())
        assert patch["schemaVersion"] == 3

    def test_time_range_floors_at_five_minutes(self):
        fast = v1_recipe()
        fast["cookTimeMinutes"] = 8
        patch = build_v2_patch(fast)
        assert patch["time"]["totalRangeMinutes"][0] == 5
