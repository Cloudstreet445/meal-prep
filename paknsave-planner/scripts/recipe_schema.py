"""
Recipe schema — single source of truth for valid field values and validation.

History:
  MEA-68  — queryable metadata (tags, primaryProtein, season, dietaryFlags)
  MEA-69  — clean ingredient shape (no price data on recipes)
  MEA-109 — recipe schema v2 (protein substitutes, time breakdown, equipment,
            leftovers object, nutrition, cost tier, source, quality flags)
  MEA-110 — ingredient schema v2 (structured amount, searchKeyVariants,
            category, substitutes, optional, pantryStaple, prepNote)

Import from here in generation_prompt.py, bulk_generate.py, backfill_v2.py,
validate_schema_v2.py — never redefine enums locally.

Two validators are exposed:
  validate_recipe(doc)            — structural + enum checks. Lenient about
                                    null/unfilled v2 fields so backfilled v1
                                    records still pass.
  validate_generated_recipe(doc)  — strict checks for FRESH v2 generation
                                    output (substitutes present, variants
                                    populated, time coherent, staples flagged).
"""

import re
from typing import TypedDict, Optional

SCHEMA_VERSION = 3  # v2-milestone schema. v1=1, MEA-68/69 migration=2, this=3.

# ---------------------------------------------------------------------------
# Recipe-level enums
# ---------------------------------------------------------------------------

VALID_PROTEINS = {
    "chicken", "pork", "beef", "lamb", "vegetarian", "seafood", "eggs",
}

# Proteins for which a recipe MUST carry at least one proteinSubstitute.
MEAT_PROTEINS = {"chicken", "pork", "beef", "lamb"}

VALID_SEASONS = {"all", "spring", "summer", "autumn", "winter"}

VALID_DIETARY_FLAGS = {
    "dairy-free", "gluten-free", "egg-free", "nut-free", "low-carb",
}

VALID_TAGS = {
    # Speed
    "quick", "medium", "slow",
    # Method
    "one-pan", "tray-bake", "slow-cooker", "stir-fry", "soup", "stew",
    "salad", "pasta", "rice", "curry", "bbq",
    # Character
    "freezer-friendly", "leftovers", "meal-prep", "budget",
    # Cuisine
    "asian", "chinese", "japanese", "korean", "thai", "vietnamese",
    "indian", "mexican", "italian", "mediterranean", "greek",
    "middle-eastern", "american", "nz-classic",
    # Season feel
    "winter-warmer", "summer-fresh",
}

# MEA-109 — equipment a recipe needs. Filterable in planner and PWA browser.
VALID_EQUIPMENT = {
    "oven", "stovetop", "slow-cooker", "air-fryer", "bbq",
    "single-pan", "blender", "rice-cooker",
}

VALID_SKILL_LEVELS = {"easy", "medium", "hard"}
VALID_SPICE_LEVELS = {0, 1, 2, 3}
VALID_MEAL_TYPES = {"dinner", "lunch", "breakfast"}
VALID_COST_TIERS = {"budget", "mid", "premium"}
VALID_ALLERGENS = {"gluten", "dairy", "egg", "nuts", "soy", "fish", "shellfish"}

# ---------------------------------------------------------------------------
# Ingredient-level enums
# ---------------------------------------------------------------------------

VALID_UNITS = {
    "g", "kg", "ml", "l", "tsp", "tbsp", "cup",
    "ea", "bunch", "can", "packet", "slice", "rasher",
}

# MEA-110 — supermarket aisle grouping + match category bias.
VALID_INGREDIENT_CATEGORIES = {
    "meat", "produce", "dairy", "pantry", "frozen", "bakery", "deli",
}

# Ingredients whose name contains one of these words should be pantryStaple.
# Used by the generator prompt rules and the MEA-114 validation audit.
STAPLE_KEYWORDS = {
    "salt", "pepper", "olive oil", "oil", "flour", "sugar", "soy sauce",
    "garlic", "cornflour", "baking powder", "vinegar", "stock cube",
}

# ---------------------------------------------------------------------------
# TypedDicts — documentation of the v2 document shape
# ---------------------------------------------------------------------------

class Amount(TypedDict):
    value: Optional[float]   # numeric quantity, None if unparseable
    unit: Optional[str]      # one of VALID_UNITS, None if unparseable
    display: str             # human string, always present, e.g. "1kg"


class Substitute(TypedDict):
    name: str
    searchKey: str
    ratio: float             # multiplier vs the original quantity
    note: str


class Ingredient(TypedDict):
    name: str
    amount: Amount
    searchKey: str
    searchKeyVariants: list   # ordered fallback list, [0] = highest confidence
    category: str             # one of VALID_INGREDIENT_CATEGORIES
    substitutes: list         # list of Substitute
    optional: bool
    pantryStaple: bool
    prepNote: Optional[str]


class TimeBreakdown(TypedDict):
    prepMinutes: Optional[int]
    activeCookMinutes: Optional[int]
    passiveCookMinutes: Optional[int]
    totalRangeMinutes: list   # [low, high], low < high


class Leftovers(TypedDict):
    keepsInFridgeDays: Optional[int]
    freezable: Optional[bool]
    reheatMethod: Optional[str]
    lunchFriendly: Optional[bool]


class Recipe(TypedDict):
    recipeId: str
    name: str
    description: str
    serves: int
    recipeUrl: str
    primaryProtein: str
    proteinSubstitutes: list
    time: TimeBreakdown
    cookTime: str             # denormalised human alias
    cookTimeMinutes: int      # denormalised alias = time.totalRangeMinutes[1]
    equipment: list
    skillLevel: Optional[str]
    spiceLevel: Optional[int]
    mealType: str
    tags: list
    season: list
    dietaryFlags: list
    allergens: list
    costTier: Optional[str]
    leftovers: Leftovers
    nutritionPerServe: dict
    imageUrl: Optional[str]
    ingredients: list
    method: list
    source: dict
    qualityFlags: dict
    schemaVersion: int


# ---------------------------------------------------------------------------
# Amount parsing — shared by backfill and the generator
# ---------------------------------------------------------------------------

_AMOUNT_PATTERNS = [
    (r'^([\d.]+)\s*kg\b', "kg"),
    (r'^([\d.]+)\s*g\b', "g"),
    (r'^([\d.]+)\s*ml\b', "ml"),
    (r'^([\d.]+)\s*l\b', "l"),
    (r'^([\d.]+)\s*tsp\b', "tsp"),
    (r'^([\d.]+)\s*tbsp\b', "tbsp"),
    (r'^([\d.]+)\s*cup', "cup"),
    (r'^([\d.]+)\s*slice', "slice"),
    (r'^([\d.]+)\s*rasher', "rasher"),
    (r'^([\d.]+)\s*bunch', "bunch"),
    (r'^([\d.]+)\s*can', "can"),
    (r'^([\d.]+)\s*packet', "packet"),
]


def parse_amount(amount_str) -> dict:
    """
    Parse a human amount string into a structured {value, unit, display}.

      "1kg"        -> {"value": 1.0,   "unit": "kg",  "display": "1kg"}
      "500g"       -> {"value": 500.0, "unit": "g",   "display": "500g"}
      "2 medium"   -> {"value": 2.0,   "unit": "ea",  "display": "2 medium"}
      "to taste"   -> {"value": None,  "unit": None,  "display": "to taste"}

    Always returns a dict; falls back to {value: None, unit: None, display: s}.
    """
    if amount_str is None:
        return {"value": None, "unit": None, "display": ""}

    # Already structured — pass through, repairing missing display.
    if isinstance(amount_str, dict):
        display = amount_str.get("display") or ""
        return {
            "value": amount_str.get("value"),
            "unit": amount_str.get("unit"),
            "display": display,
        }

    display = str(amount_str).strip()
    s = display.lower()

    for pattern, unit in _AMOUNT_PATTERNS:
        m = re.match(pattern, s)
        if m:
            try:
                return {"value": float(m.group(1)), "unit": unit, "display": display}
            except ValueError:
                pass

    # Bare leading number with no recognised unit -> "ea" (each / whole items).
    m = re.match(r'^([\d.]+)', s)
    if m:
        try:
            return {"value": float(m.group(1)), "unit": "ea", "display": display}
        except ValueError:
            pass

    return {"value": None, "unit": None, "display": display}


def is_staple_name(name: str) -> bool:
    """True if an ingredient name looks like a pantry staple."""
    n = (name or "").lower()
    return any(kw in n for kw in STAPLE_KEYWORDS)


# ---------------------------------------------------------------------------
# Validation — structural + enum (lenient)
# ---------------------------------------------------------------------------

_RECIPE_REQUIRED = [
    "name", "serves", "description", "ingredients", "method",
    "primaryProtein", "tags", "season", "time",
]

_INGREDIENT_REQUIRED = [
    "name", "amount", "searchKey", "searchKeyVariants", "category",
]

_BANNED_INGREDIENT_FIELDS = ["estimatedCost", "fromSpecial", "sharedWith"]


def _validate_time(time_obj, errors: list):
    if not isinstance(time_obj, dict):
        errors.append("time: must be an object")
        return
    rng = time_obj.get("totalRangeMinutes")
    if not isinstance(rng, list) or len(rng) != 2:
        errors.append("time.totalRangeMinutes: must be a 2-element array [low, high]")
        return
    lo, hi = rng
    if not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)):
        errors.append("time.totalRangeMinutes: both values must be numbers")
    elif lo >= hi:
        errors.append(f"time.totalRangeMinutes: low ({lo}) must be < high ({hi})")


def _validate_ingredient(ing: dict, prefix: str, errors: list):
    for banned in _BANNED_INGREDIENT_FIELDS:
        if banned in ing:
            errors.append(f"{prefix}: banned field '{banned}' — price data must not live on recipes")

    for req in _INGREDIENT_REQUIRED:
        if req not in ing:
            errors.append(f"{prefix}: missing '{req}'")

    amount = ing.get("amount")
    if amount is not None and not isinstance(amount, dict):
        errors.append(f"{prefix}: amount must be a structured object {{value, unit, display}}")
    elif isinstance(amount, dict):
        unit = amount.get("unit")
        if unit is not None and unit not in VALID_UNITS:
            errors.append(f"{prefix}: invalid amount.unit '{unit}'")
        if "display" not in amount:
            errors.append(f"{prefix}: amount.display is required")

    category = ing.get("category")
    if category is not None and category not in VALID_INGREDIENT_CATEGORIES:
        errors.append(f"{prefix}: invalid category '{category}'")

    variants = ing.get("searchKeyVariants")
    if variants is not None and not isinstance(variants, list):
        errors.append(f"{prefix}: searchKeyVariants must be an array")

    sk = ing.get("searchKey", "")
    if sk and sk != sk.lower():
        errors.append(f"{prefix}: searchKey '{sk}' should be lowercase")

    for j, sub in enumerate(ing.get("substitutes", []) or []):
        if not isinstance(sub, dict):
            errors.append(f"{prefix}.substitutes[{j}]: must be an object")
        elif "searchKey" not in sub or "name" not in sub:
            errors.append(f"{prefix}.substitutes[{j}]: needs 'name' and 'searchKey'")


def validate_recipe(doc: dict) -> list:
    """
    Structural + enum validation. Lenient: null/absent optional v2 fields are
    allowed so backfilled v1 records still validate. Returns list of error
    strings (empty == valid).
    """
    errors = []

    for field in _RECIPE_REQUIRED:
        if field not in doc:
            errors.append(f"Missing required field: {field}")

    protein = doc.get("primaryProtein")
    if protein and protein not in VALID_PROTEINS:
        errors.append(f"Invalid primaryProtein '{protein}'")

    for s in doc.get("season", []) or []:
        if s not in VALID_SEASONS:
            errors.append(f"Invalid season value '{s}'")

    for t in doc.get("tags", []) or []:
        if t not in VALID_TAGS:
            errors.append(f"Unknown tag '{t}'")

    for f in doc.get("dietaryFlags", []) or []:
        if f not in VALID_DIETARY_FLAGS:
            errors.append(f"Invalid dietaryFlag '{f}'")

    for e in doc.get("equipment", []) or []:
        if e not in VALID_EQUIPMENT:
            errors.append(f"Invalid equipment value '{e}'")

    for a in doc.get("allergens", []) or []:
        if a not in VALID_ALLERGENS:
            errors.append(f"Invalid allergen '{a}'")

    skill = doc.get("skillLevel")
    if skill is not None and skill not in VALID_SKILL_LEVELS:
        errors.append(f"Invalid skillLevel '{skill}'")

    spice = doc.get("spiceLevel")
    if spice is not None and spice not in VALID_SPICE_LEVELS:
        errors.append(f"Invalid spiceLevel '{spice}' — must be 0-3")

    meal_type = doc.get("mealType")
    if meal_type is not None and meal_type not in VALID_MEAL_TYPES:
        errors.append(f"Invalid mealType '{meal_type}'")

    cost_tier = doc.get("costTier")
    if cost_tier is not None and cost_tier not in VALID_COST_TIERS:
        errors.append(f"Invalid costTier '{cost_tier}'")

    if "time" in doc:
        _validate_time(doc.get("time"), errors)

    for i, ing in enumerate(doc.get("ingredients", []) or []):
        _validate_ingredient(ing, f"ingredients[{i}]", errors)

    return errors


# ---------------------------------------------------------------------------
# Validation — strict (fresh v2 generation output, MEA-112)
# ---------------------------------------------------------------------------

def validate_generated_recipe(doc: dict) -> list:
    """
    Strict validation for freshly generated v2 recipes, run before insert by
    the bulk puller. Includes everything validate_recipe checks, plus the
    quality gates from MEA-112. Returns list of error strings.
    """
    errors = validate_recipe(doc)

    # Time breakdown must be fully populated for fresh generation.
    time_obj = doc.get("time") or {}
    for part in ("prepMinutes", "activeCookMinutes", "passiveCookMinutes"):
        if time_obj.get(part) is None:
            errors.append(f"time.{part}: required for generated recipes")
    rng = time_obj.get("totalRangeMinutes")
    if isinstance(rng, list) and len(rng) == 2:
        breakdown_sum = sum(
            time_obj.get(p) or 0
            for p in ("prepMinutes", "activeCookMinutes", "passiveCookMinutes")
        )
        if breakdown_sum and abs(breakdown_sum - rng[1]) > 15:
            errors.append(
                f"time: prep+active+passive ({breakdown_sum}) should be near "
                f"totalRangeMinutes[1] ({rng[1]})"
            )

    protein = doc.get("primaryProtein")
    if protein in MEAT_PROTEINS:
        subs = doc.get("proteinSubstitutes") or []
        if len(subs) < 1:
            errors.append("proteinSubstitutes: meat recipes need at least 1 entry")
        for k, sub in enumerate(subs):
            if not isinstance(sub, dict) or not sub.get("searchKey"):
                errors.append(f"proteinSubstitutes[{k}]: needs name, searchKey, ratio, note")

    if not doc.get("description"):
        errors.append("description: required for generated recipes")

    has_real_searchkey = False
    for i, ing in enumerate(doc.get("ingredients", []) or []):
        prefix = f"ingredients[{i}]"
        variants = ing.get("searchKeyVariants") or []
        if len(variants) < 2:
            errors.append(f"{prefix}: searchKeyVariants must have >=2 entries")
        sk = ing.get("searchKey", "")
        if sk and len(sk.split()) > 3:
            errors.append(f"{prefix}: searchKey '{sk}' should be <=3 words")
        if ing.get("category") is None:
            errors.append(f"{prefix}: category is required")
        if not ing.get("optional") and not ing.get("pantryStaple") and sk:
            has_real_searchkey = True
        # Staple keyword but not flagged as pantryStaple.
        if is_staple_name(ing.get("name", "")) and not ing.get("pantryStaple"):
            errors.append(f"{prefix}: '{ing.get('name')}' looks like a staple — set pantryStaple:true")

    if not has_real_searchkey:
        errors.append("ingredients: at least one required ingredient must carry a searchKey")

    return errors


def validate_and_raise(doc: dict):
    """Validate a recipe doc and raise ValueError if invalid."""
    errors = validate_recipe(doc)
    if errors:
        raise ValueError(
            f"Recipe validation failed for '{doc.get('name', '?')}':\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
