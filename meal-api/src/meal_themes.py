"""Meal-type themes (cuisines) and the pantry staples they imply.

Single source of truth shared by:
  - settings (the themes a household picks during onboarding)
  - the pantry suggestions endpoint (staples to offer for confirm/deny)
  - plan generation (a soft boost toward recipes matching chosen themes)

Kept as plain data so it's trivial to extend. Canonical pantry keys are
lower-cased names, matching how the pantry stores items elsewhere.
"""

# Display order + label for each selectable theme.
THEME_LABELS: dict[str, str] = {
    "asian":          "Asian",
    "chinese":        "Chinese",
    "japanese":       "Japanese",
    "korean":         "Korean",
    "thai":           "Thai",
    "vietnamese":     "Vietnamese",
    "indian":         "Indian",
    "mexican":        "Mexican",
    "italian":        "Italian",
    "mediterranean":  "Mediterranean",
    "greek":          "Greek",
    "middle-eastern": "Middle Eastern",
    "american":       "American / BBQ",
    "nz-classic":     "Kiwi Classic",
}

VALID_THEMES = set(THEME_LABELS)

# Recipe tags that count as "matching" a theme, for the soft plan-gen boost.
# Broad cuisines lean on existing/older tags; finer themes match their own
# dedicated tag (added to recipe_schema VALID_TAGS) once recipes carry them.
THEME_RECIPE_TAGS: dict[str, set[str]] = {
    "asian":          {"asian", "stir-fry", "curry"},
    "chinese":        {"chinese", "stir-fry"},
    "japanese":       {"japanese"},
    "korean":         {"korean"},
    "thai":           {"thai", "asian", "curry"},
    "vietnamese":     {"vietnamese"},
    "indian":         {"indian", "curry"},
    "mexican":        {"mexican"},
    "italian":        {"italian", "pasta"},
    "mediterranean":  {"mediterranean"},
    "greek":          {"greek"},
    "middle-eastern": {"middle-eastern"},
    "american":       {"american", "bbq"},
    "nz-classic":     {"nz-classic"},
}

# Staple pantry items each theme implies. Offered during onboarding and the
# weekly confirm so users can tick what they already own (kept off the shopping
# list and used to bias/cheapen plans). Names are display-cased; canonical keys
# are derived as the lower-cased name.
THEME_PANTRY_STAPLES: dict[str, list[str]] = {
    "asian":          ["Soy Sauce", "Sesame Oil", "Rice", "Rice Vinegar", "Ginger", "Garlic"],
    "chinese":        ["Soy Sauce", "Sesame Oil", "Rice", "Oyster Sauce", "Ginger", "Garlic", "Spring Onion"],
    "japanese":       ["Soy Sauce", "Mirin", "Short Grain Rice", "Miso Paste", "Nori", "Sesame Oil"],
    "korean":         ["Gochujang", "Soy Sauce", "Sesame Oil", "Rice", "Garlic", "Spring Onion"],
    "thai":           ["Fish Sauce", "Coconut Milk", "Thai Curry Paste", "Lime", "Jasmine Rice", "Lemongrass"],
    "vietnamese":     ["Fish Sauce", "Rice Noodles", "Lime", "Fresh Coriander", "Garlic", "Rice"],
    "indian":         ["Garam Masala", "Turmeric", "Ground Cumin", "Basmati Rice", "Red Lentils", "Ginger", "Garlic"],
    "mexican":        ["Ground Cumin", "Smoked Paprika", "Tinned Tomatoes", "Black Beans", "Tortillas", "Lime"],
    "italian":        ["Olive Oil", "Garlic", "Tinned Tomatoes", "Pasta", "Parmesan", "Dried Oregano"],
    "mediterranean":  ["Olive Oil", "Garlic", "Lemon", "Chickpeas", "Dried Oregano"],
    "greek":          ["Olive Oil", "Lemon", "Garlic", "Feta", "Dried Oregano", "Red Onion"],
    "middle-eastern": ["Ground Cumin", "Tahini", "Chickpeas", "Olive Oil", "Garlic", "Lemon", "Flatbread"],
    "american":       ["Tomato Ketchup", "Mustard", "BBQ Sauce", "Burger Buns", "Cheddar", "Smoked Paprika"],
    "nz-classic":     ["Potatoes", "Onion", "Butter", "Flour", "Mixed Herbs"],
}


def normalise_themes(themes) -> list[str]:
    """Filter an arbitrary input list down to known themes, de-duplicated and
    in canonical display order."""
    chosen = {str(t).lower().strip() for t in (themes or [])}
    return [t for t in THEME_LABELS if t in chosen]


def pantry_suggestions_for(themes) -> list[dict]:
    """Suggested staples for the chosen themes.

    Returns ``[{name, canonical, themes:[...]}]`` deduplicated by canonical
    name, each carrying which chosen theme(s) suggested it (so the UI can group
    or explain). Order follows theme order, then staple order within a theme.
    """
    chosen = normalise_themes(themes)
    by_canonical: dict[str, dict] = {}
    for theme in chosen:
        for name in THEME_PANTRY_STAPLES.get(theme, []):
            canonical = name.lower()
            entry = by_canonical.get(canonical)
            if entry:
                if theme not in entry["themes"]:
                    entry["themes"].append(theme)
            else:
                by_canonical[canonical] = {"name": name, "canonical": canonical, "themes": [theme]}
    return list(by_canonical.values())
