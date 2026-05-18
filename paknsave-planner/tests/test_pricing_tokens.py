"""Tests for the product tokeniser and ingredient synonyms (MEA-111)."""

import pytest

from pricing_tokens import tokenise
from ingredient_synonyms import SYNONYMS, build_lookup, expand


class TestTokenise:
    def test_strips_brands_qualifiers_and_units(self):
        assert tokenise("Pams Fresh NZ Chicken Drumsticks 1kg") == ["chicken", "drumsticks"]

    def test_strips_punctuation(self):
        assert tokenise("Wattie's Tomato Paste") == ["tomato", "paste"]

    def test_deduplicates_preserving_order(self):
        assert tokenise("Chicken Chicken Stock") == ["chicken", "stock"]

    def test_empty_name_returns_empty_list(self):
        assert tokenise("") == []

    def test_drops_pure_digit_tokens(self):
        assert "500" not in tokenise("Anchor Butter 500")


class TestSynonyms:
    def test_every_entry_has_canonical_and_variants(self):
        for entry in SYNONYMS:
            assert entry["canonical"] and entry["variants"]

    def test_lookup_maps_variant_to_canonical(self):
        lookup = build_lookup()
        assert lookup["cilantro"] == "coriander"
        assert lookup["ground beef"] == "beef mince"

    def test_expand_returns_canonical_and_all_variants(self):
        result = expand("cilantro")
        assert "coriander" in result and "cilantro" in result

    def test_expand_unknown_term_returns_itself(self):
        assert expand("unobtanium") == ["unobtanium"]
