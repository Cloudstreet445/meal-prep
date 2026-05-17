"""
Backfill existing recipes to schema v2 (MEA-113).

Brings pre-v2 recipes in `paknsave-meals.recipes` up to the v2 shape defined in
recipe_schema.py. Strategy: patch everything that can be inferred
automatically, then flag the record so a targeted v2 regen can replace it.

Steps:
  1. Patch — for every recipe missing `time`, add the v2 field set with
     inferred/default values and convert each ingredient to the v2 shape.
  2. Flag — mark every patched (prompt v1) recipe qualityFlags.needsRegen=true
     so the bulk puller's regen run knows to replace it.

The actual regen run is the bulk puller (bulk_generate.py); validation of the
result is validate_schema_v2.py (MEA-114).

Usage (from paknsave-planner/scripts/):
    python backfill_v2.py --dry-run
    python backfill_v2.py
    python backfill_v2.py --uri mongodb://localhost:27017 --db paknsave-meals
"""

import argparse
import sys
from datetime import datetime, timezone

try:
    from pymongo import MongoClient, UpdateOne
except ImportError:
    print("pymongo not installed. Run: pip install pymongo --break-system-packages")
    sys.exit(1)

from recipe_schema import SCHEMA_VERSION, parse_amount, is_staple_name
from migrate_recipes import parse_cook_time_minutes

# ---------------------------------------------------------------------------
# Ingredient migration — v1 flat shape -> v2 structured shape
# ---------------------------------------------------------------------------

def migrate_ingredient_v2(ing: dict) -> dict:
    """Convert a v1 ingredient to the v2 shape, preserving what's known."""
    name = ing.get("name", "")
    search_key = ing.get("searchKey", "")

    # Build the structured amount. Prefer the v1 quantity+unit pair when both
    # are present and sane; otherwise parse the human amount string.
    qty = ing.get("quantity")
    unit = ing.get("unit")
    raw_amount = ing.get("amount")
    if isinstance(raw_amount, dict):
        amount = parse_amount(raw_amount)
    elif isinstance(qty, (int, float)) and unit:
        display = str(raw_amount) if raw_amount else f"{qty}{unit}"
        amount = {"value": float(qty), "unit": unit, "display": display}
    else:
        amount = parse_amount(raw_amount)

    return {
        "name": name,
        "amount": amount,
        "searchKey": search_key,
        # Variants default to [searchKey] until the v2 regen fills them out.
        "searchKeyVariants": [search_key] if search_key else [],
        "category": ing.get("category"),         # None — regen infers this
        "substitutes": ing.get("substitutes", []),
        "optional": bool(ing.get("optional", False)),
        "pantryStaple": bool(ing.get("pantryStaple", is_staple_name(name))),
        "prepNote": ing.get("prepNote"),
    }


# ---------------------------------------------------------------------------
# Recipe patch
# ---------------------------------------------------------------------------

def build_v2_patch(doc: dict) -> dict:
    """Build the $set payload that lifts a v1 recipe to the v2 shape."""
    cook_minutes = doc.get("cookTimeMinutes") or parse_cook_time_minutes(
        doc.get("cookTime", "")
    )

    # v1 stored leftovers as a bool — carry the signal into lunchFriendly.
    old_leftovers = doc.get("leftovers")
    leftovers_obj = {
        "keepsInFridgeDays": None,
        "freezable": None,
        "reheatMethod": None,
        "lunchFriendly": old_leftovers if isinstance(old_leftovers, bool) else None,
    }

    ingredients = [migrate_ingredient_v2(i) for i in doc.get("ingredients", [])]

    return {
        "time": {
            "prepMinutes": None,
            "activeCookMinutes": None,
            "passiveCookMinutes": None,
            "totalRangeMinutes": [max(5, cook_minutes - 10), cook_minutes + 10],
        },
        "proteinSubstitutes": doc.get("proteinSubstitutes", []),
        "equipment": doc.get("equipment", []),
        "skillLevel": doc.get("skillLevel"),
        "spiceLevel": doc.get("spiceLevel"),
        "mealType": doc.get("mealType", "dinner"),
        "allergens": doc.get("allergens", []),
        "costTier": doc.get("costTier"),
        "leftovers": leftovers_obj,
        "nutritionPerServe": doc.get("nutritionPerServe", {"calories": None, "proteinG": None}),
        "description": doc.get("description"),
        "imageUrl": doc.get("imageUrl"),
        "source": {
            "promptVersion": "v1",
            "generationDate": None,
            "model": "claude-sonnet-4",
        },
        "qualityFlags": {
            "userRating": doc.get("userRating"),
            "timesUsed": doc.get("timesUsed", 0),
            "lastUsedWeek": doc.get("lastUsedWeek"),
            "userNotes": None,
            "needsRegen": True,
        },
        "ingredients": ingredients,
        "cookTimeMinutes": cook_minutes,
        "schemaVersion": SCHEMA_VERSION,
        "updatedAt": datetime.now(timezone.utc),
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run(uri: str, db_name: str, collection: str, dry_run: bool):
    client = MongoClient(uri)
    col = client[db_name][collection]

    total = col.count_documents({})
    needs_patch = col.count_documents({"time": {"$exists": False}})
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Backfill to schema v2 — "
          f"{db_name}.{collection}")
    print(f"  Total recipes:        {total}")
    print(f"  Missing v2 schema:    {needs_patch}")
    print("-" * 60)

    ops = []
    errors = []
    for doc in col.find({"time": {"$exists": False}}):
        name = doc.get("name", "?")
        try:
            patch = build_v2_patch(doc)
        except Exception as e:
            errors.append(f"  {name}: {e}")
            continue

        if dry_run:
            ing0 = patch["ingredients"][0] if patch["ingredients"] else {}
            print(f"  {name}")
            print(f"    time.totalRangeMinutes: {patch['time']['totalRangeMinutes']}")
            print(f"    ingredient[0].amount:   {ing0.get('amount')}")
        else:
            ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": patch}))

    patched = 0
    if not dry_run and ops:
        patched = col.bulk_write(ops, ordered=False).modified_count
        print(f"\n  Patched to v2: {patched}")

    # Step 2 — flag v1 recipes for regen. Idempotent; safe to re-run.
    flagged = 0
    if not dry_run:
        flagged = col.update_many(
            {"source.promptVersion": "v1"},
            {"$set": {"qualityFlags.needsRegen": True}},
        ).modified_count
    print(f"  Flagged needsRegen: "
          f"{flagged if not dry_run else col.count_documents({'time': {'$exists': False}})}")

    if errors:
        print(f"\n  Errors ({len(errors)}):")
        for e in errors:
            print(e)

    if dry_run:
        print(f"\n[DRY RUN] Would patch {needs_patch} recipes. No writes made.")
    else:
        print(f"\nDone. Next: regen flagged recipes with bulk_generate.py, "
              f"then validate with validate_schema_v2.py")

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill recipes to schema v2 (MEA-113)")
    parser.add_argument("--uri", default="mongodb://localhost:27017", help="MongoDB URI")
    parser.add_argument("--db", default="paknsave-meals", help="Database name")
    parser.add_argument("--collection", default="recipes", help="Collection name")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    run(args.uri, args.db, args.collection, args.dry_run)
