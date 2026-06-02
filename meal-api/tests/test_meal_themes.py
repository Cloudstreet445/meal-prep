"""Unit tests for the meal-themes model (pure, no DB)."""

from src.meal_themes import (
    normalise_themes, pantry_suggestions_for, VALID_THEMES, THEME_LABELS,
)


def test_normalise_drops_unknown_and_dedupes_in_order():
    out = normalise_themes(["INDIAN", "asian", "asian", "klingon", " thai "])
    # Known themes only, deduped, in canonical display order.
    assert out == [t for t in THEME_LABELS if t in {"asian", "thai", "indian"}]
    assert "klingon" not in out


def test_normalise_handles_empty():
    assert normalise_themes(None) == []
    assert normalise_themes([]) == []


def test_suggestions_for_single_theme():
    sugg = pantry_suggestions_for(["thai"])
    names = {s["canonical"] for s in sugg}
    assert "fish sauce" in names
    assert "coconut milk" in names
    # Every suggestion records which theme produced it.
    assert all(s["themes"] == ["thai"] for s in sugg)


def test_suggestions_dedupe_across_themes_and_credit_both():
    sugg = pantry_suggestions_for(["asian", "indian"])
    by_canon = {s["canonical"]: s for s in sugg}
    # Garlic is implied by both → one entry crediting both themes.
    assert by_canon["garlic"]["themes"] == ["asian", "indian"]
    # And it appears exactly once.
    assert sum(1 for s in sugg if s["canonical"] == "garlic") == 1


def test_suggestions_empty_for_no_themes():
    assert pantry_suggestions_for([]) == []


def test_expanded_cuisines_have_distinct_staples():
    jp = {s["canonical"] for s in pantry_suggestions_for(["japanese"])}
    assert "miso paste" in jp
    kr = {s["canonical"] for s in pantry_suggestions_for(["korean"])}
    assert "gochujang" in kr
    me = {s["canonical"] for s in pantry_suggestions_for(["middle-eastern"])}
    assert "tahini" in me


def test_comprehensive_theme_count():
    # Expanded cuisine set (see meal_themes.THEME_LABELS).
    assert len(VALID_THEMES) == 14
    for key in ("chinese", "japanese", "korean", "vietnamese", "greek",
                "middle-eastern", "american"):
        assert key in VALID_THEMES


def test_all_themes_have_staples_and_tags():
    from src.meal_themes import THEME_PANTRY_STAPLES, THEME_RECIPE_TAGS
    for theme in VALID_THEMES:
        assert THEME_PANTRY_STAPLES.get(theme), f"{theme} has no staples"
        assert THEME_RECIPE_TAGS.get(theme), f"{theme} has no recipe tags"
