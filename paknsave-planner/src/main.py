#!/usr/bin/env python3
"""
Pak'nSave Weekly Meal Planner
------------------------------
Orchestrates the full pipeline:
  1. Query MongoDB for current prices       (planner.py)
  2. Generate meal plan via Claude API      (claude.py)
     OR load from file for testing
  3. Store recipes and bundle in MongoDB    (mongodb.py)
  4. Print summary to console

Usage:
  python src/main.py          # load response.json + store
  python src/main.py api      # call Claude API + store
  python src/main.py seed     # seed test-data files (delegates to seed.py)
"""

import os
import sys
import json
from datetime import datetime
from config import BUDGET, SERVES, RESPONSE_JSON
from planner import get_market_data
from ai.claude import generate_meal_plan, load_from_file
from db.mongodb import store_recipes, store_bundle


USE_API  = "api"  in sys.argv
USE_SEED = "seed" in sys.argv


# ── Print helpers ─────────────────────────────────────────────────

def print_market_summary(market_data):
    print(f"  Proteins on special: {len(market_data.proteins_on_special)}")
    print(f"  Cheap proteins:      {len(market_data.proteins_cheap)}")
    print(f"  Beef mince special:  {len(market_data.beef_mince_special)}")
    print(f"  Cheap vegetables:    {len(market_data.veges_cheap)}")
    print(f"  Pantry items:        {len(market_data.pantry)}")
    print(f"  Dairy items:         {len(market_data.dairy)}")


def print_meal_plan(plan: dict):
    print("\n" + "="*60)
    print("🛒  WEEKLY MEAL PLAN — PAK'nSAVE Lower Hutt")
    print(f"📅  Week of {datetime.now().strftime('%d %B %Y')}")
    print(f"💰  Estimated Total: ${plan['estimatedTotal']:.2f} / ${BUDGET:.2f} budget")
    print(f"📝  {plan['weekSummary']}")
    print("="*60)

    for meal in plan["meals"]:
        print(f"\n{'─'*60}")
        print(f"🍽   {meal['id']}: {meal['name']}")
        print(f"     ⏱  {meal['cookTime']}  |  Serves {meal['serves']}", end="")
        print(f"  |  {'♻️  Leftovers!' if meal.get('leftovers') else ''}")
        print(f"     {meal.get('description', '')}")
        print(f"     🔗 {meal.get('recipeUrl', '')}")
        print(f"\n     Ingredients:")
        for ing in meal.get("ingredients", []):
            special = "🔥" if ing.get("fromSpecial") else "  "
            print(f"       {special} {ing['amount']} {ing['name']} — ${ing['estimatedCost']:.2f}")

    print(f"\n{'='*60}")
    print("🛒  SHOPPING LIST (from Claude — API will re-derive with live prices)")
    print(f"{'='*60}")
    total = 0
    for item in plan.get("shoppingList", []):
        special  = "🔥 SPECIAL" if item.get("isSpecial") else ""
        used_in  = ", ".join(item.get("usedIn", []))
        print(f"  {'${:.2f}'.format(item['estimatedCost']):>8}  {item['amount']} {item['name']} {special}")
        print(f"             Used in: {used_in}")
        total += item.get("estimatedCost", 0)
    print(f"\n  {'─'*40}")
    print(f"  {'TOTAL':>8}  ${total:.2f}")


# ── Main ──────────────────────────────────────────────────────────

def main():
    if USE_SEED:
        import subprocess
        subprocess.run([sys.executable, "scripts/seed.py"], check=True)
        return

    # Step 1 — Get market data
    print("📊 Querying Pak'nSave price data from MongoDB...")
    market_data = get_market_data(os.environ.get("STORE_ID", "paknsave-lower-hutt"))
    print_market_summary(market_data)

    if not market_data.any_data():
        print("❌ No data found in MongoDB — has the scraper run yet?")
        sys.exit(1)

    # Step 2 — Generate or load meal plan
    if USE_API:
        plan = generate_meal_plan(market_data)
    else:
        print(f"\n📂 Loading from {RESPONSE_JSON} (pass 'api' to call Claude)...")
        plan = load_from_file()

    # Step 3 — Print summary
    print_meal_plan(plan)

    # Step 4 — Store in MongoDB
    print("\n💾 Storing to MongoDB...")
    week_id = datetime.now().strftime("%Y-%m-%d")

    recipe_count, recipe_ids = store_recipes(plan, week_id)
    print(f"  ✓ {recipe_count} recipes stored/updated")
    print(f"  ✓ Recipe IDs: {recipe_ids}")

    bundle_id = store_bundle(plan, week_id, recipe_ids)
    print(f"  ✓ Bundle stored — ID: {bundle_id}  week: {week_id}  active: True")
    print(f"  ℹ️  Other bundles for week {week_id} have been deactivated")
    print(f"  ℹ️  Bundles from other weeks are unchanged")

    # Step 5 — Save dated output JSON
    output_file = f"meal_plan_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(output_file, "w") as f:
        json.dump(plan, f, indent=2)
    print(f"  ✓ Saved to {output_file}")

    print(f"\n✨ Done! Bundle ID: {bundle_id}")


if __name__ == "__main__":
    main()