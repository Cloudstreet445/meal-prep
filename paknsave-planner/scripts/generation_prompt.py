"""
Recipe generation prompt builder — schema v2 (MEA-112).

Used by the bulk recipe puller (bulk_generate.py) and the paid-tier custom
planner. Produces the full v2 recipe shape defined in recipe_schema.py.

Enum lists are imported from recipe_schema so the prompt can never drift from
the validator. Update enums in ONE place: recipe_schema.py.

Informed by the MEA-77 pricing audit:
  - searchKeys must be short, generic, lowercase (no brand names)
  - Avoid canned whole tomatoes (use paste/passata), lamb mince, specialty imports
  - Fresh veg match well on generic names
"""

import json
import re
import hashlib

from recipe_schema import (
    VALID_PROTEINS, VALID_SEASONS, VALID_DIETARY_FLAGS, VALID_TAGS,
    VALID_EQUIPMENT, VALID_SKILL_LEVELS, VALID_MEAL_TYPES, VALID_COST_TIERS,
    VALID_ALLERGENS, VALID_UNITS, VALID_INGREDIENT_CATEGORIES,
)

# Bump this whenever the prompt changes meaningfully. Written to
# recipe.source.promptVersion so old records can be found and regenerated.
PROMPT_VERSION = "v2"

# Model used for generation. Kept here so source.model is recorded accurately.
GENERATION_MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Batch definitions for bulk generation
# ---------------------------------------------------------------------------

BATCHES = [
    {"id": 1,  "label": "chicken",           "focus": "chicken-based meals — drumsticks, thighs, breast, whole roast"},
    {"id": 2,  "label": "pork",              "focus": "pork — mince, shoulder, belly, chops, sausages"},
    {"id": 3,  "label": "beef",              "focus": "beef — mince, chuck, stewing steak, sausages"},
    {"id": 4,  "label": "lamb",              "focus": "lamb — shoulder chops, leg, forequarter (avoid lamb mince — unavailable)"},
    {"id": 5,  "label": "vegetarian",        "focus": "vegetarian — eggs, lentils, canned beans, tofu, chickpeas"},
    {"id": 6,  "label": "quick",             "focus": "quick meals under 30 minutes — any protein"},
    {"id": 7,  "label": "slow-oven",         "focus": "slow oven meals over 60 minutes — tray bakes, roasts, braises"},
    {"id": 8,  "label": "asian",             "focus": "Asian-inspired — stir fries, noodle soups, fried rice, curries"},
    {"id": 9,  "label": "winter-warmers",    "focus": "soups, stews, casseroles perfect for NZ winter (June-August)"},
    {"id": 10, "label": "budget",            "focus": "ultra-budget meals under $10 NZD for 4 serves"},
    {"id": 11, "label": "italian",           "focus": "Italian-style — pasta bakes, bolognese and ragù, risotto, gnocchi, minestrone"},
    {"id": 12, "label": "vietnamese",        "focus": "Vietnamese-style — caramelised pork, lemongrass chicken, noodle salads, pho-inspired soups (using ingredients sold at a standard NZ PAK'nSAVE)"},
    {"id": 13, "label": "thai",              "focus": "Thai-style — red, green and yellow curries, basil stir fries, noodle dishes (using curry pastes and ingredients sold at PAK'nSAVE)"},
    {"id": 14, "label": "indian",            "focus": "Indian-style — curries, dhal, butter chicken, spiced rice and lentil dishes (using supermarket spices and ingredients)"},
    {"id": 15, "label": "mexican",           "focus": "Mexican-style — tacos, burritos, nachos, chilli con carne, fajita bowls"},
    {"id": 16, "label": "quick-skillet",     "focus": "extra-quick weeknight dinners under 25 minutes — fast one-pan and skillet meals"},
    {"id": 17, "label": "summer-fresh",      "focus": "summer meals for NZ (December-February) — salads, BBQ plates, light fresh dishes"},
    {"id": 18, "label": "spring-greens",     "focus": "spring meals for NZ (September-November) — asparagus, peas, leafy greens, lighter plates"},
    {"id": 19, "label": "autumn-harvest",    "focus": "autumn meals for NZ (March-May) — pumpkin, kumara, apples, root vegetables"},
    {"id": 20, "label": "one-pan",           "focus": "one-pan and sheet-pan dinners — minimal washing up, tray bakes and skillet meals"},
    {"id": 21, "label": "pasta-noodles",     "focus": "pasta and noodle mains — comforting, family-sized, pantry-friendly"},
    {"id": 22, "label": "freezer-batch",     "focus": "batch-cook and freezer-friendly meals — make ahead, portion and freeze"},
    {"id": 23, "label": "family-favourites", "focus": "kid-friendly family favourites — crowd-pleasing classics"},
    {"id": 24, "label": "comfort-bakes",     "focus": "baked comfort dishes — savoury pies, gratins, bakes, stuffed vegetables"},
    {"id": 25, "label": "breakfast-brunch",  "focus": "breakfast and brunch meals — hearty starts and weekend brunches (mealType breakfast)"},
]


def _enum_line(values) -> str:
    """Render an enum set as a stable, sorted, quoted list for the prompt."""
    return " | ".join(f'"{v}"' for v in sorted(values))


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = f"""You are a recipe developer for a New Zealand budget meal planning app called Kai Planner.
Your recipes are used by NZ families shopping at PAK'nSAVE Lower Hutt.

CRITICAL RULES — follow these exactly:
1. ALL ingredients must be purchasable at a standard NZ PAK'nSAVE supermarket.
2. NO specialty imports, no Asian grocery-only items, no deli-counter items.
3. Total ingredient cost for 4 serves must be realistic:
   - costTier "budget":  under $10 NZD
   - costTier "mid":     $10-$15 NZD
   - costTier "premium": $15-$20 NZD (hard maximum $20)
4. Avoid these — unavailable or poorly matched at PAK'nSAVE:
   - Canned whole tomatoes (use tomato paste or passata)
   - Lamb mince (use lamb shoulder chops or forequarter)
   - Large quantities of fresh herbs (use dried herbs)
   - Specialty cheeses (use Edam, Colby, mozzarella, or cream cheese)
5. Reuse ingredients across the batch where natural (e.g. brown onions, carrots).
6. Method steps must be specific and sequential. No vague steps like "cook until done".
7. Output ONLY a valid JSON array — no preamble, no markdown fences, no commentary.

SEARCHKEY RULES (used to look the ingredient up in the price database):
- searchKey: lowercase, generic, AT MOST 3 words. Strip brands and qualifiers
  (Pams, Anchor, NZ, Value Pack, Free Range, Boneless, Brushed).
- searchKeyVariants: an ordered list of AT LEAST 2 alternative search terms,
  best guess first. Cover plural/singular and NZ vs generic naming.
  Example: "chicken drumsticks" -> ["chicken drumsticks", "drumsticks", "chicken drumstick"]
- Examples:
  - "NZ Chicken Drumsticks Value Pack" -> searchKey "chicken drumsticks"
  - "Pams Brushed Agria Potatoes"      -> searchKey "agria potatoes"
  - "Anchor Butter"                    -> searchKey "butter"
  - "Pams Tomato Paste"                -> searchKey "tomato paste"

PANTRY STAPLES:
- Set "pantryStaple": true for oil, olive oil, salt, pepper, flour, sugar,
  soy sauce, vinegar, cornflour, baking powder, stock cubes, and dried herbs.
- The user already owns these — they are excluded from the weekly shopping total.

SUBSTITUTES:
- Every meat recipe MUST include at least one entry in "proteinSubstitutes".
- Per-ingredient "substitutes" are optional but encouraged for key ingredients.
- ratio is a quantity multiplier vs the original (1.0 = same amount).

NUTRITION:
- nutritionPerServe values are rough estimates based on typical NZ supermarket
  products. Approximate honestly; do not fabricate precision.

VALID ENUM VALUES — use ONLY these:
primaryProtein: {_enum_line(VALID_PROTEINS)}
season:         array of {_enum_line(VALID_SEASONS)}
dietaryFlags:   array of {_enum_line(VALID_DIETARY_FLAGS)}
allergens:      array of {_enum_line(VALID_ALLERGENS)}
equipment:      array of {_enum_line(VALID_EQUIPMENT)}
skillLevel:     {_enum_line(VALID_SKILL_LEVELS)}
spiceLevel:     0 | 1 | 2 | 3
mealType:       {_enum_line(VALID_MEAL_TYPES)}
costTier:       {_enum_line(VALID_COST_TIERS)}
tags:           array from {_enum_line(VALID_TAGS)}
ingredient category: {_enum_line(VALID_INGREDIENT_CATEGORIES)}
amount unit:    {_enum_line(VALID_UNITS)}
"""

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------

_RECIPE_SHAPE = """{
  "name": "Recipe Name",
  "description": "One-line blurb for the recipe browser — what it is and why it's good value.",
  "serves": 4,
  "primaryProtein": "chicken",
  "proteinSubstitutes": [
    { "name": "chicken breast", "searchKey": "chicken breast", "ratio": 0.9, "note": "reduce cook time by 5 min" }
  ],
  "time": {
    "prepMinutes": 15,
    "activeCookMinutes": 20,
    "passiveCookMinutes": 25,
    "totalRangeMinutes": [55, 70]
  },
  "equipment": ["oven", "stovetop"],
  "skillLevel": "easy",
  "spiceLevel": 1,
  "mealType": "dinner",
  "tags": ["one-pan", "winter-warmer", "freezer-friendly"],
  "season": ["winter", "autumn"],
  "dietaryFlags": [],
  "allergens": ["gluten"],
  "costTier": "budget",
  "leftovers": {
    "keepsInFridgeDays": 3,
    "freezable": true,
    "reheatMethod": "microwave or stovetop",
    "lunchFriendly": true
  },
  "nutritionPerServe": { "calories": 480, "proteinG": 34 },
  "recipeUrl": "",
  "ingredients": [
    {
      "name": "NZ Chicken Drumsticks Value Pack",
      "amount": { "value": 1, "unit": "kg", "display": "1kg (approx 6 drumsticks)" },
      "searchKey": "chicken drumsticks",
      "searchKeyVariants": ["chicken drumsticks", "drumsticks", "chicken drumstick"],
      "category": "meat",
      "substitutes": [
        { "name": "chicken thigh fillets", "searchKey": "chicken thigh fillets", "ratio": 1.0, "note": "add 5 min cook time" }
      ],
      "optional": false,
      "pantryStaple": false,
      "prepNote": "pat dry before seasoning"
    },
    {
      "name": "Olive Oil",
      "amount": { "value": 2, "unit": "tbsp", "display": "2 tbsp" },
      "searchKey": "olive oil",
      "searchKeyVariants": ["olive oil", "cooking oil"],
      "category": "pantry",
      "substitutes": [],
      "optional": false,
      "pantryStaple": true,
      "prepNote": null
    }
  ],
  "method": [
    "Step 1: ...",
    "Step 2: ..."
  ]
}"""


def build_user_prompt(batch: dict, count: int = 20, existing_names=None) -> str:
    existing_note = ""
    if existing_names:
        sample = existing_names[:20]
        more = "  ... and more" if len(existing_names) > 20 else ""
        existing_note = (
            "\nDo NOT duplicate or closely rework these existing recipes:\n"
            + "\n".join(f"  - {n}" for n in sample)
            + (f"\n{more}" if more else "")
            + "\n"
        )

    return f"""Generate {count} distinct recipes focused on: {batch['focus']}
{existing_note}
Output a JSON array of {count} recipe objects. Each object MUST match this exact shape:

{_RECIPE_SHAPE}

Rules for this batch:
- Focus: {batch['focus']}
- Each recipe must be meaningfully different from the others.
- 5-12 ingredients per recipe.
- 4-9 method steps, each specific and actionable.
- time.totalRangeMinutes[0] must be strictly less than time.totalRangeMinutes[1].
- prepMinutes + activeCookMinutes + passiveCookMinutes should roughly equal
  totalRangeMinutes[1].
- Every meat recipe needs >=1 proteinSubstitutes entry.
- Every ingredient needs >=2 searchKeyVariants.
- Flag oil, salt, pepper, flour, sugar, soy sauce etc. with "pantryStaple": true.
- leftovers.freezable / lunchFriendly should reflect the actual dish honestly.

Output ONLY the JSON array. No other text."""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def parse_generation_response(raw: str) -> list:
    """
    Parse a raw Claude response into a list of recipe dicts.
    Tolerates markdown fences and a {"recipes": [...]} wrapper.
    """
    cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'\s*```$', '', cleaned.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip()

    data = json.loads(cleaned)
    if isinstance(data, dict):
        data = data.get("recipes", [data])
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data)}")
    return data


# ---------------------------------------------------------------------------
# Recipe ID generation
# ---------------------------------------------------------------------------

def make_recipe_id(name: str) -> str:
    """
    "Roasted Pumpkin and Chicken Drumstick Tray Bake"
      -> "roasted-pumpkin-and-chicken-drumstick-tray-bake-cc8254"
    """
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    hash_suffix = hashlib.md5(name.encode()).hexdigest()[:6]
    return f"{slug}-{hash_suffix}"
