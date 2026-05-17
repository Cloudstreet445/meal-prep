"""Tests for the v2 generation prompt builder (MEA-112)."""

import pytest

from generation_prompt import (
    SYSTEM_PROMPT, PROMPT_VERSION, BATCHES,
    build_user_prompt, parse_generation_response, make_recipe_id,
)


class TestSystemPrompt:
    def test_prompt_version_is_v2(self):
        assert PROMPT_VERSION == "v2"

    def test_system_prompt_lists_v2_enums(self):
        for token in ("equipment:", "costTier:", "skillLevel:", "searchKeyVariants"):
            assert token in SYSTEM_PROMPT

    def test_system_prompt_enforces_pantry_staples(self):
        assert "pantryStaple" in SYSTEM_PROMPT


class TestUserPrompt:
    def test_user_prompt_includes_v2_shape_keys(self):
        prompt = build_user_prompt(BATCHES[0], count=5)
        for key in ("proteinSubstitutes", "searchKeyVariants", "totalRangeMinutes",
                    "nutritionPerServe", "pantryStaple"):
            assert key in prompt

    def test_user_prompt_lists_existing_names_for_dedup(self):
        prompt = build_user_prompt(BATCHES[0], count=5, existing_names=["Old Recipe X"])
        assert "Old Recipe X" in prompt


class TestParseResponse:
    def test_parses_plain_json_array(self):
        assert parse_generation_response('[{"name": "A"}]') == [{"name": "A"}]

    def test_strips_markdown_fences(self):
        raw = '```json\n[{"name": "A"}]\n```'
        assert parse_generation_response(raw) == [{"name": "A"}]

    def test_unwraps_recipes_key(self):
        assert parse_generation_response('{"recipes": [{"name": "A"}]}') == [{"name": "A"}]


class TestBatches:
    def test_ids_are_contiguous_from_one(self):
        ids = [b["id"] for b in BATCHES]
        assert ids == list(range(1, len(BATCHES) + 1))

    def test_labels_are_unique(self):
        labels = [b["label"] for b in BATCHES]
        assert len(labels) == len(set(labels))

    def test_every_batch_has_a_focus(self):
        assert all(b["focus"].strip() for b in BATCHES)

    def test_count_supports_five_hundred_recipes(self):
        # 25 batches x 20 recipes per batch = 500.
        assert len(BATCHES) == 25


class TestMakeRecipeId:
    def test_deterministic(self):
        assert make_recipe_id("Thai Chicken Curry") == make_recipe_id("Thai Chicken Curry")

    def test_slug_and_hash_format(self):
        rid = make_recipe_id("Thai Chicken Curry")
        assert rid.startswith("thai-chicken-curry-")
        assert " " not in rid
