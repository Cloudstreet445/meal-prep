"""
Recipe schema constants and validation.
MEA-68: New queryable metadata fields
MEA-69: Clean ingredient shape (no price data on recipes)

This module is the single source of truth for valid field values.
Import from here in seed.py, planner.py, and the generation prompt builder.
"""

from typing import TypedDict, Literal, Optional

# ---------------------------------------------------------------------------
# Valid enum values
# ---------------------------------------------------------------------------

VALID_PROTEINS = {
    "chicken",
    "pork",
    "beef",
    "lamb",
    "vegetarian",
    "seafood",
    "eggs",
}

VALID_SEASONS = {"all", "spring", "summer", "autumn", "winter"}

VALID_DIETARY_FLAGS = {
    "dairy-free",
    "gluten-free",
    "egg-free",
    "nut-free",
    "low-carb",
}

VALID_TAGS = {
    # Speed
    "quick",          # under 30 min
    "medium",         # 30–60 min
    "slow",           # 60+ min
    # Method
    "one-pan",
    "tray-bake",
    "slow-cooker",
    "stir-fry",
    "soup",
    "stew",
    "salad",
    "pasta",
    "rice",
    "curry",
    # Character
    "freezer-friendly",
    "leftovers",
    "meal-prep",
    "budget",         # under $10 for 4 serves
    # Cuisine
    "asian",
    "mexican",
    "italian",
    "nz-classic",
    "mediterranean",
    # Season feel
    "winter-warmer",
    "summer-fresh",
}

# ---------------------------------------------------------------------------
# Ingredient shape (MEA-69: no price data)
# ---------------------------------------------------------------------------

VALID_UNITS = {
    "g", "kg",
    "ml", "l",
    "tsp", "tbsp", "cup",
    "ea",           # each / whole items
    "bunch",
    "can",
    "packet",
    "slice",
    "rasher",
}

class Ingredient(TypedDict):
    name: str           # generic/canonical name, e.g. "chicken drumsticks"
    amount: str         # human string, e.g. "1kg" or "2 medium"
    quantity: float     # numeric quantity for aggregation
    unit: str           # one of VALID_UNITS
    searchKey: str      # short lowercase term for paknsave-pricing lookup
    # NOTE: NO estimatedCost, fromSpecial, or sharedWith — those are pricing concerns

# ---------------------------------------------------------------------------
# Full recipe shape
# ---------------------------------------------------------------------------

class Recipe(TypedDict):
    recipeId: str               # slug-hash, e.g. "chicken-curry-abc123"
    name: str
    serves: int
    cookTime: str               # human string, e.g. "45 min"
    cookTimeMinutes: int        # integer for range queries — MEA-68
    description: str
    recipeUrl: str
    ingredients: list           # list of Ingredient
    method: list                # list of step strings
    # New fields — MEA-68
    primaryProtein: str         # one of VALID_PROTEINS
    tags: list                  # subset of VALID_TAGS
    season: list                # subset of VALID_SEASONS
    dietaryFlags: list          # subset of VALID_DIETARY_FLAGS
    leftovers: bool
    # Lifecycle
    source: str                 # "claude" | "user"
    usageHistory: list          # ["2026-05-05", ...]
    bundleHistory: list         # ["bundle-id-1", ...]
    lastUsedWeek: Optional[str]
    createdAt: str
    updatedAt: str

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_recipe(doc: dict) -> list:
    """
    Returns a list of validation error strings.
    Empty list = valid.
    """
    errors = []

    # Required fields
    for field in ["recipeId", "name", "serves", "cookTime", "cookTimeMinutes",
                  "description", "ingredients", "method",
                  "primaryProtein", "tags", "season"]:
        if field not in doc:
            errors.append(f"Missing required field: {field}")

    # Protein
    protein = doc.get("primaryProtein")
    if protein and protein not in VALID_PROTEINS:
        errors.append(f"Invalid primaryProtein '{protein}'. Must be one of: {VALID_PROTEINS}")

    # Season
    for s in doc.get("season", []):
        if s not in VALID_SEASONS:
            errors.append(f"Invalid season value '{s}'. Must be one of: {VALID_SEASONS}")

    # Tags
    for t in doc.get("tags", []):
        if t not in VALID_TAGS:
            errors.append(f"Unknown tag '{t}' — add to VALID_TAGS if intentional")

    # cookTimeMinutes must be int
    ctm = doc.get("cookTimeMinutes")
    if ctm is not None and not isinstance(ctm, int):
        errors.append(f"cookTimeMinutes must be int, got {type(ctm)}")

    # Ingredients
    for i, ing in enumerate(doc.get("ingredients", [])):
        prefix = f"ingredients[{i}]"

        # Banned fields (MEA-69)
        for banned in ["estimatedCost", "fromSpecial", "sharedWith"]:
            if banned in ing:
                errors.append(f"{prefix}: contains banned field '{banned}' — remove price data from recipes")

        # Required ingredient fields
        for req in ["name", "amount", "quantity", "unit", "searchKey"]:
            if req not in ing:
                errors.append(f"{prefix}: missing '{req}'")

        # Unit check
        unit = ing.get("unit")
        if unit and unit not in VALID_UNITS:
            errors.append(f"{prefix}: invalid unit '{unit}'. Must be one of: {VALID_UNITS}")

        # searchKey should be short lowercase
        sk = ing.get("searchKey", "")
        if sk and sk != sk.lower():
            errors.append(f"{prefix}: searchKey '{sk}' should be lowercase")
        if sk and len(sk) > 50:
            errors.append(f"{prefix}: searchKey too long ({len(sk)} chars) — keep it short")

    return errors


def validate_and_raise(doc: dict):
    """Validate a recipe doc and raise ValueError if invalid."""
    errors = validate_recipe(doc)
    if errors:
        raise ValueError(f"Recipe validation failed for '{doc.get('name', '?')}':\n" +
                         "\n".join(f"  - {e}" for e in errors))
