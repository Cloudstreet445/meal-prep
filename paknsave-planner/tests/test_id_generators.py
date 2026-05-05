"""Tests for deterministic ID generation in mongodb.py."""

import pytest
from mongodb import generate_recipe_id, generate_bundle_id


class TestGenerateRecipeId:
    def test_deterministic_same_name(self):
        meal = {"name": "Chicken Stir Fry"}
        assert generate_recipe_id(meal) == generate_recipe_id(meal)

    def test_slug_format_lowercase(self):
        meal = {"name": "Chicken Stir Fry"}
        result = generate_recipe_id(meal)
        assert result == result.lower()

    def test_slug_contains_no_spaces(self):
        meal = {"name": "Chicken Stir Fry"}
        result = generate_recipe_id(meal)
        assert " " not in result

    def test_slug_uses_hyphens(self):
        meal = {"name": "Chicken Stir Fry"}
        result = generate_recipe_id(meal)
        assert "-" in result

    def test_special_chars_removed(self):
        meal = {"name": "Beef & Vegetable Casserole"}
        result = generate_recipe_id(meal)
        assert "&" not in result
        assert " " not in result

    def test_ends_with_short_hash(self):
        meal = {"name": "Chicken Stir Fry"}
        result = generate_recipe_id(meal)
        parts = result.rsplit("-", 1)
        assert len(parts) == 2
        hash_part = parts[1]
        assert len(hash_part) == 6
        assert all(c in "0123456789abcdef" for c in hash_part)

    def test_different_names_produce_different_ids(self):
        id1 = generate_recipe_id({"name": "Chicken Stir Fry"})
        id2 = generate_recipe_id({"name": "Beef Stew"})
        assert id1 != id2

    def test_same_name_same_id_regardless_of_other_fields(self):
        meal_a = {"name": "Pasta Bake", "serves": 2}
        meal_b = {"name": "Pasta Bake", "serves": 4, "description": "different"}
        assert generate_recipe_id(meal_a) == generate_recipe_id(meal_b)


class TestGenerateBundleId:
    def test_deterministic(self):
        id1 = generate_bundle_id("5 winter meals", "2026-05-05")
        id2 = generate_bundle_id("5 winter meals", "2026-05-05")
        assert id1 == id2

    def test_same_summary_different_week_gives_different_id(self):
        id1 = generate_bundle_id("5 winter meals", "2026-05-05")
        id2 = generate_bundle_id("5 winter meals", "2026-04-28")
        assert id1 != id2

    def test_different_summary_same_week_gives_different_id(self):
        id1 = generate_bundle_id("5 winter meals", "2026-05-05")
        id2 = generate_bundle_id("5 summer meals", "2026-05-05")
        assert id1 != id2

    def test_slug_lowercase_no_spaces(self):
        result = generate_bundle_id("5 Winter Meals", "2026-05-05")
        assert result == result.lower()
        assert " " not in result

    def test_ends_with_six_char_hash(self):
        result = generate_bundle_id("5 winter meals", "2026-05-05")
        parts = result.rsplit("-", 1)
        assert len(parts[1]) == 6

    def test_long_summary_is_truncated(self):
        long_summary = "a" * 100
        result = generate_bundle_id(long_summary, "2026-05-05")
        # slug is truncated to 40 chars before hash suffix
        slug_part = result.rsplit("-", 1)[0]
        assert len(slug_part) <= 40
