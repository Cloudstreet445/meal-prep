"""
Claude API - 4 call chained meal planning pipeline.

Call 1: Analyse market data → structured summary of what's cheap/special
Call 2: Plan 5 meals       → meal names, proteins, costs (no recipes yet)
Call 3: Generate recipes   → full ingredients + method for each meal
Call 4: Generate shopping list → deduplicated, combined, flagged shopping list
"""

import json
import re
import os
from anthropic import Anthropic
from dotenv import load_dotenv
from config import (
    CLAUDE_MODEL, CLAUDE_MAX_TOKENS,
    BUDGET, SERVES, RESPONSE_JSON
)
from models import MarketData

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]


def _client() -> Anthropic:
    return Anthropic(api_key=ANTHROPIC_API_KEY)


def _call(client: Anthropic, system: str, prompt: str, max_tokens: int = 2000) -> str:
    """Single Claude API call. Returns raw text response."""
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def _parse_json(raw: str, label: str) -> dict | list:
    """Parse JSON from Claude response, with repair fallback."""
    raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'^```\s*', '', raw, flags=re.MULTILINE)
    raw = raw.strip().strip('`')

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON parse error in {label}: {e} — attempting repair...")
        start = raw.find('[') if raw.lstrip().startswith('[') else raw.find('{')
        end   = raw.rfind(']') if raw.lstrip().startswith('[') else raw.rfind('}')
        if start >= 0 and end >= 0:
            cleaned = re.sub(r',(\s*[}\]])', r'\1', raw[start:end+1])
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as e2:
                print(f"  ❌ Repair failed: {e2}")
                print(f"  Raw ({label}):\n{raw[:500]}")
                raise ValueError(f"Could not parse {label} response as JSON") from e2
        raise ValueError(f"No JSON found in {label} response") from e


# ══════════════════════════════════════════════════════════════════
# CALL 1 — Analyse market data
# ══════════════════════════════════════════════════════════════════

SYSTEM_1 = """You are a budget grocery analyst for New Zealand supermarkets.
Analyse the provided Pak'nSave pricing data and return a clean structured summary.
Focus only on what is relevant for planning 5 budget winter dinners for 2 people.
Exclude: seafood, mushrooms, carcasses, offal, organ meats.

Respond ONLY with a valid JSON object. No markdown, no backticks, no explanation.

{
  "bestProteins": [
    {
      "name": "product name",
      "price": 0.00,
      "size": "1kg",
      "unitPrice": "0.00/kg",
      "isSpecial": true,
      "category": "chicken"
    }
  ],
  "bestVegetables": [
    {
      "name": "product name",
      "price": 0.00,
      "size": "500g",
      "isSpecial": false
    }
  ],
  "pantryAvailable": [
    {
      "name": "product name",
      "price": 0.00,
      "category": "pasta"
    }
  ],
  "dairyAvailable": [
    {
      "name": "product name",
      "price": 0.00
    }
  ],
  "specialsHighlight": "one sentence summary of the best deals this week",
  "budgetNotes": "one sentence on how to stretch the $60 budget this week"
}"""


def call1_analyse(market_data: MarketData) -> dict:
    """Call 1: Analyse market data into a clean summary."""
    print("  [1/4] Analysing market data...")

    data = market_data.to_dict()
    prompt = f"""Analyse this week's Pak'nSave Lower Hutt pricing data.
Budget: ${BUDGET} NZD for 5 dinners for {SERVES} people.

PROTEINS ON SPECIAL:
{json.dumps(data['proteins_on_special'], indent=2)}

CHEAP PROTEINS:
{json.dumps(data['proteins_cheap'], indent=2)}

BEEF/LAMB MINCE ON SPECIAL:
{json.dumps(data['beef_mince_special'], indent=2)}

CHEAP VEGETABLES (under $5):
{json.dumps(data['veges_cheap'], indent=2)}

VEGETABLES ON SPECIAL:
{json.dumps(data['veges_special'], indent=2)}

PANTRY STAPLES:
{json.dumps(data['pantry'], indent=2)}

DAIRY:
{json.dumps(data['dairy'], indent=2)}

Return a clean summary of the best options available this week."""

    client = _client()
    raw = _call(client, SYSTEM_1, prompt, max_tokens=1500)
    result = _parse_json(raw, "call1")

    print(f"     ✓ {len(result.get('bestProteins', []))} proteins, "
          f"{len(result.get('bestVegetables', []))} vegetables found")
    print(f"     💡 {result.get('specialsHighlight', '')}")

    return result


# ══════════════════════════════════════════════════════════════════
# CALL 2 — Plan 5 meals
# ══════════════════════════════════════════════════════════════════

SYSTEM_2 = """You are a practical New Zealand home cook and meal planner.
Given a summary of available ingredients and their prices, plan 5 winter dinners.

Rules:
- Budget: stay within the total budget across all 5 meals
- Proteins: chicken and pork preferred, lamb welcome, beef mince only if on special
- Exclude: seafood, mushrooms, carcasses, offal, organ meats, pre-made sauces
- Season: winter NZ — hearty, warming meals
- Encourage leftovers and batch cooking
- Share vegetables and pantry items across meals to reduce waste
- Only use ingredients from the provided market data

Respond ONLY with a valid JSON array. No markdown, no backticks, no explanation.

[
  {
    "id": "M1",
    "name": "Meal name",
    "protein": "specific product name from market data",
    "proteinCost": 0.00,
    "keyVegetables": ["veg1", "veg2"],
    "vegCost": 0.00,
    "pantryCost": 0.00,
    "dairyCost": 0.00,
    "estimatedMealCost": 0.00,
    "serves": 2,
    "leftovers": true,
    "cookTime": "45 min",
    "description": "one sentence description",
    "sharedIngredients": ["ingredient shared with other meals"]
  }
]"""


def call2_plan_meals(market_summary: dict) -> list:
    """Call 2: Plan 5 meals from the market summary."""
    print("  [2/4] Planning 5 meals...")

    prompt = f"""Plan 5 winter dinners for {SERVES} people within a ${BUDGET} NZD total budget.

Available this week:
{json.dumps(market_summary, indent=2)}

Requirements:
- Use proteins from bestProteins list only
- Use vegetables from bestVegetables list only
- Total of all estimatedMealCost must be under ${BUDGET}
- Meals should be hearty winter food
- Maximise shared ingredients to reduce waste
- At least 2 meals should produce leftovers"""

    client = _client()
    raw = _call(client, SYSTEM_2, prompt, max_tokens=2000)
    result = _parse_json(raw, "call2")

    total = sum(m.get('estimatedMealCost', 0) for m in result)
    print(f"     ✓ {len(result)} meals planned — estimated total: ${total:.2f}")
    for meal in result:
        print(f"     · {meal['id']}: {meal['name']} (${meal.get('estimatedMealCost', 0):.2f})")

    return result


# ══════════════════════════════════════════════════════════════════
# CALL 3 — Generate full recipes
# Note: NO sharedWith field — computed dynamically by the API
# ══════════════════════════════════════════════════════════════════

SYSTEM_3 = """You are a practical New Zealand home cook writing clear weeknight recipes.
Given an approved meal plan, write the full recipe details for each meal.

Rules:
- Only use ingredients that exist in the provided market data summary
- Be specific with amounts (e.g. 500g, 2 cloves, 1 tbsp)
- estimatedCost for each ingredient must be realistic based on market data prices
- Methods should be clear, numbered steps suitable for a home cook
- recipeUrl must be a real recipe website URL (not a Google search link)
  Preferred sites: recipetineats.com, taste.com.au, bbcgoodfood.com, allrecipes.com, myfoodbook.com.au

CRITICAL: Do NOT include a sharedWith field on ingredients.
The API will compute ingredient sharing dynamically.

Respond ONLY with a valid JSON array of meals. No markdown, no backticks, no explanation.

[
  {
    "id": "M1",
    "name": "Meal name",
    "serves": 2,
    "leftovers": true,
    "cookTime": "45 min",
    "description": "brief description",
    "recipeUrl": "https://www.recipetineats.com/...",
    "ingredients": [
      {
        "name": "ingredient name",
        "amount": "500g",
        "estimatedCost": 0.00,
        "fromSpecial": false
      }
    ],
    "method": [
      "Step 1: ...",
      "Step 2: ..."
    ]
  }
]"""


def call3_generate_recipes(meal_plan: list, market_summary: dict) -> list:
    """Call 3: Generate full recipes for each planned meal."""
    print("  [3/4] Writing recipes...")

    prompt = f"""Write full recipes for these approved meals.
Only use ingredients available in the market data.

APPROVED MEAL PLAN:
{json.dumps(meal_plan, indent=2)}

AVAILABLE INGREDIENTS (use only these):
{json.dumps(market_summary, indent=2)}

Write clear step-by-step methods. Be specific with amounts and costs.
Do NOT include a sharedWith field on any ingredient."""

    client = _client()
    raw = _call(client, SYSTEM_3, prompt, max_tokens=4000)
    result = _parse_json(raw, "call3")

    print(f"     ✓ {len(result)} recipes generated")
    for meal in result:
        print(f"     · {meal['id']}: {len(meal.get('ingredients', []))} ingredients, "
              f"{len(meal.get('method', []))} steps")

    return result


# ══════════════════════════════════════════════════════════════════
# CALL 4 — Generate shopping list
# ══════════════════════════════════════════════════════════════════

SYSTEM_4 = """You are generating a deduplicated shopping list from a set of recipes.

Rules:
- Combine the same ingredient used across multiple meals into one line item
- Sum the costs for combined items
- Note which meal IDs each item is used in (use the id field from the recipe e.g. "M1")
- Flag items that are on special (fromSpecial: true in any recipe)
- Round costs to 2 decimal places
- Sort by category: proteins first, then vegetables, then pantry, then dairy

Respond ONLY with a valid JSON object. No markdown, no backticks, no explanation.

{
  "weekSummary": "one sentence theme for the week",
  "estimatedTotal": 0.00,
  "shoppingList": [
    {
      "name": "ingredient name",
      "amount": "total amount needed",
      "estimatedCost": 0.00,
      "isSpecial": false,
      "category": "protein",
      "usedIn": ["M1", "M2"]
    }
  ]
}"""


def call4_shopping_list(recipes: list) -> dict:
    """Call 4: Generate deduplicated shopping list from recipes."""
    print("  [4/4] Building shopping list...")

    prompt = f"""Generate a deduplicated shopping list from these 5 recipes.
Combine shared ingredients, sum costs, note which meal IDs use each item.

RECIPES:
{json.dumps(recipes, indent=2)}"""

    client = _client()
    raw = _call(client, SYSTEM_4, prompt, max_tokens=2000)
    result = _parse_json(raw, "call4")

    total = result.get('estimatedTotal', 0)
    items = result.get('shoppingList', [])
    print(f"     ✓ {len(items)} items — total: ${total:.2f}")

    return result


# ══════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════

def generate_meal_plan(market_data: MarketData) -> dict:
    """
    Run the full 4-call pipeline and return a complete meal plan.

    Returns:
        {
            "weekSummary": str,
            "estimatedTotal": float,
            "meals": [...],        # from call 3 — no sharedWith on ingredients
            "shoppingList": [...]  # from call 4 — usedIn uses M1/M2 IDs
        }
    """
    print("\n🤖 Running 4-call meal planning pipeline...")

    market_summary = call1_analyse(market_data)
    meal_plan      = call2_plan_meals(market_summary)
    recipes        = call3_generate_recipes(meal_plan, market_summary)
    shopping       = call4_shopping_list(recipes)

    final = {
        "weekSummary":    shopping.get("weekSummary", "This week's meal plan"),
        "estimatedTotal": shopping.get("estimatedTotal", 0),
        "meals":          recipes,
        "shoppingList":   shopping.get("shoppingList", [])
    }

    with open(RESPONSE_JSON, "w") as f:
        json.dump(final, f, indent=2)
    print(f"\n✅ Pipeline complete — saved to {RESPONSE_JSON}")
    print(f"   Total: ${final['estimatedTotal']:.2f} / ${BUDGET:.2f} budget")

    return final


def load_from_file(path: str = None) -> dict:
    """Load meal plan from a saved JSON file (bypasses API calls)."""
    path = path or RESPONSE_JSON
    print(f"📂 Loading meal plan from {path}...")
    try:
        with open(path, "r") as f:
            raw = f.read()
        raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'^```\s*', '', raw, flags=re.MULTILINE)
        raw = raw.strip().strip('`')
        return json.loads(raw)
    except FileNotFoundError:
        print(f"❌ File not found: {path}")
        raise
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {path}: {e}")
        raise