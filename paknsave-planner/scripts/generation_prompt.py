"""
Recipe generation prompt builder.
Used by the bulk generation script (MEA-72) and the paid-tier custom planner.

Informed by MEA-77 audit findings:
  - searchKeys must be short generic lowercase terms
  - Avoid: canned tomatoes (use tomato paste/passata), lamb mince, mince-sausages category
  - Fresh veg: generic names work well
  - Proteins: use common cuts available at PaknSave NZ
"""

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Batch definitions for bulk generation (MEA-72)
# ---------------------------------------------------------------------------

BATCHES = [
    {"id": 1,  "label": "chicken",         "focus": "chicken-based meals — drumsticks, thighs, breast, whole roast"},
    {"id": 2,  "label": "pork",            "focus": "pork — mince, shoulder, belly, chops, sausages"},
    {"id": 3,  "label": "beef",            "focus": "beef — mince, chuck, stewing steak, sausages"},
    {"id": 4,  "label": "lamb",            "focus": "lamb — shoulder chops, leg, forequarter (avoid lamb mince — unavailable)"},
    {"id": 5,  "label": "vegetarian",      "focus": "vegetarian — eggs, lentils, canned beans, tofu, chickpeas"},
    {"id": 6,  "label": "quick",           "focus": "quick meals under 30 minutes — any protein"},
    {"id": 7,  "label": "slow-oven",       "focus": "slow oven meals over 60 minutes — tray bakes, roasts, braises"},
    {"id": 8,  "label": "asian",           "focus": "Asian-inspired — stir fries, noodle soups, fried rice, curries"},
    {"id": 9,  "label": "winter-warmers",  "focus": "soups, stews, casseroles perfect for NZ winter (June-August)"},
    {"id": 10, "label": "budget",          "focus": "ultra-budget meals under $10 NZD for 4 serves"},
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a recipe developer for a New Zealand budget meal planning app called Kai Planner.
Your recipes are used by NZ families shopping at PaknSave supermarkets.

CRITICAL RULES — follow these exactly:
1. ALL ingredients must be available at a standard NZ PaknSave supermarket.
2. NO specialty imports, no Asian grocery-only items, no deli items.
3. Total ingredient cost must be realistic for 4 serves:
   - Budget meals: under $10 NZD
   - Standard meals: $10–$15 NZD  
   - Premium meals: up to $20 NZD (maximum)
4. Avoid these ingredients — they are unavailable or poorly matched in PaknSave:
   - Canned whole tomatoes (use tomato paste or passata instead)
   - Lamb mince (use lamb shoulder chops or forequarter instead)
   - Fresh herbs in large quantities (use dried herbs)
   - Specialty cheeses (use Edam, Colby, or cream cheese)
5. Prefer shared ingredients across a batch — e.g. if you use brown onions in one recipe, use them in others too.
6. Method steps must be clear, specific, and sequential. No vague steps like "cook until done".
7. Serving sizes are NZ-standard: 4 serves = typical NZ family dinner.
8. Output ONLY valid JSON — no preamble, no markdown fences, no commentary.

SEARCHKEY RULES:
- searchKey is a short (2–4 words), lowercase, generic term used to find this ingredient in the supermarket database.
- Strip brand names (Pams, Anchor, NZ, Value Pack, Free Range, Boneless, Brushed).
- Examples:
  - "NZ Chicken Drumsticks Value Pack" → "chicken drumsticks"
  - "Pams Brushed Agria Potatoes" → "agria potatoes"
  - "Anchor Butter" → "butter"
  - "Brown Onions" → "brown onions"
  - "Pams Tomato Paste" → "tomato paste"

VALID VALUES:
primaryProtein: "chicken" | "pork" | "beef" | "lamb" | "vegetarian" | "seafood" | "eggs"
season: array of "all" | "spring" | "summer" | "autumn" | "winter"
tags: array from ["quick","medium","slow","one-pan","tray-bake","slow-cooker","stir-fry",
       "soup","stew","salad","pasta","rice","curry","freezer-friendly","leftovers",
       "meal-prep","budget","asian","mexican","italian","nz-classic","mediterranean",
       "winter-warmer","summer-fresh"]
unit: "g" | "kg" | "ml" | "l" | "tsp" | "tbsp" | "cup" | "ea" | "bunch" | "can" | "packet" | "slice" | "rasher"
"""

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------

def build_user_prompt(batch: dict, count: int = 20, existing_names: Optional[list] = None) -> str:
    existing_note = ""
    if existing_names:
        sample = existing_names[:15]
        existing_note = f"""
Avoid duplicating these already-generated recipes:
{chr(10).join(f"  - {n}" for n in sample)}
{"  ... and more" if len(existing_names) > 15 else ""}
"""

    return f"""Generate {count} distinct recipes focused on: {batch['focus']}
{existing_note}
Output a JSON array of {count} recipe objects. Each object must match this exact shape:

{{
  "name": "Recipe Name",
  "description": "1–2 sentence description of the dish and why it's good value.",
  "serves": 4,
  "cookTime": "45 min",
  "cookTimeMinutes": 45,
  "primaryProtein": "chicken",
  "tags": ["medium", "tray-bake", "one-pan"],
  "season": ["all"],
  "dietaryFlags": [],
  "leftovers": true,
  "recipeUrl": "",
  "ingredients": [
    {{
      "name": "NZ Chicken Drumsticks Value Pack",
      "amount": "1kg (approximately 6 drumsticks)",
      "quantity": 1,
      "unit": "kg",
      "searchKey": "chicken drumsticks"
    }}
  ],
  "method": [
    "Step 1: ...",
    "Step 2: ..."
  ]
}}

Rules for this batch:
- Focus: {batch['focus']}
- Each recipe must be meaningfully different from the others
- 5–10 ingredients per recipe
- 4–8 method steps, each specific and actionable
- leftovers: true only if the recipe genuinely makes more than 4 serves

Output ONLY the JSON array. No other text."""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

import json
import re

def parse_generation_response(raw: str) -> list:
    """
    Parse the raw Claude response into a list of recipe dicts.
    Strips any accidental markdown fences.
    """
    # Strip markdown fences if present
    cleaned = re.sub(r'^```(?:json)?\s*', '', raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r'\s*```$', '', cleaned.strip(), flags=re.MULTILINE)
    cleaned = cleaned.strip()

    # Parse
    data = json.loads(cleaned)
    if isinstance(data, dict):
        # Sometimes Claude wraps in {"recipes": [...]}
        data = data.get("recipes", [data])
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data)}")

    return data


# ---------------------------------------------------------------------------
# Recipe ID generation
# ---------------------------------------------------------------------------

import hashlib
import re as _re

def make_recipe_id(name: str) -> str:
    """
    "Roasted Pumpkin and Chicken Drumstick Tray Bake" →
    "roasted-pumpkin-and-chicken-drumstick-tray-bake-cc8254"
    """
    slug = _re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    hash_suffix = hashlib.md5(name.encode()).hexdigest()[:6]
    return f"{slug}-{hash_suffix}"
