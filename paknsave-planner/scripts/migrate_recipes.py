"""
Migration: backfill existing recipes to new schema.
Covers MEA-68 (add metadata fields) and MEA-69 (clean ingredient shape).

Run once against your MongoDB instance:
    python migrate_recipes.py --uri mongodb://localhost:27017 --db kai --dry-run
    python migrate_recipes.py --uri mongodb://localhost:27017 --db kai

What this does:
  1. Removes estimatedCost, fromSpecial, sharedWith from all ingredients
  2. Adds quantity + unit parsed from the amount string (best-effort)
  3. Adds searchKey derived from ingredient name (lowercase, stripped)
  4. Adds primaryProtein inferred from ingredient names
  5. Adds tags inferred from cookTimeMinutes and existing fields
  6. Adds season: ["all"] as a safe default (can be refined later)
  7. Adds cookTimeMinutes parsed from cookTime string
  8. Adds dietaryFlags: [] as default
"""

import argparse
import re
import sys
from datetime import datetime, timezone

try:
    from pymongo import MongoClient, UpdateOne
except ImportError:
    print("pymongo not installed. Run: pip install pymongo --break-system-packages")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def parse_cook_time_minutes(cook_time_str: str) -> int:
    """
    Parse "45 min", "1 hr 15 min", "60 min" → integer minutes.
    Returns 30 as a safe default if unparseable.
    """
    if not cook_time_str:
        return 30
    s = cook_time_str.lower()
    minutes = 0
    hr = re.search(r'(\d+)\s*hr', s)
    mn = re.search(r'(\d+)\s*min', s)
    if hr:
        minutes += int(hr.group(1)) * 60
    if mn:
        minutes += int(mn.group(1))
    return minutes if minutes > 0 else 30


def parse_quantity_and_unit(amount_str: str):
    """
    Best-effort parse of amount strings like:
      "1kg" → (1.0, "kg")
      "500g" → (500.0, "g")
      "2 medium" → (2.0, "ea")
      "1 tbsp" → (1.0, "tbsp")
      "400ml" → (400.0, "ml")
    Returns (quantity: float, unit: str)
    """
    if not amount_str:
        return 1.0, "ea"

    s = amount_str.lower().strip()

    # Try unit patterns
    patterns = [
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
        (r'^([\d.]+)', "ea"),   # fallback: just a number
    ]

    for pattern, unit in patterns:
        m = re.match(pattern, s)
        if m:
            try:
                qty = float(m.group(1))
                return qty, unit
            except ValueError:
                pass

    return 1.0, "ea"


def derive_search_key(ingredient_name: str) -> str:
    """
    Derive a short lowercase searchKey from an ingredient name.
    "NZ Chicken Drumsticks Value Pack" → "chicken drumsticks"
    "Pams Brushed Agria Potatoes" → "potatoes"
    """
    # Strip common brand/qualifier prefixes
    stop_prefixes = [
        "nz ", "pams ", "anchor ", "meadow fresh ", "dairyworks ",
        "hellers ", "san remo ", "wattie's ", "watties ", "homebrand ",
        "value pack ", "fresh ", "free range ", "boneless ", "skinless ",
        "brushed ", "agria ",
    ]
    name = ingredient_name.lower()
    for prefix in stop_prefixes:
        name = name.replace(prefix, "")

    # Strip trailing qualifiers in parentheses or after comma
    name = re.sub(r'\(.*?\)', '', name)
    name = name.split(',')[0]

    # Clean up extra whitespace
    name = ' '.join(name.split()).strip()

    # Truncate to 40 chars max
    return name[:40]


def infer_primary_protein(ingredients: list) -> str:
    """
    Infer primaryProtein from ingredient names.
    Returns the best match from PROTEIN_KEYWORDS or "vegetarian".
    """
    PROTEIN_KEYWORDS = [
        ("chicken", "chicken"),
        ("pork", "pork"),
        ("beef", "beef"),
        ("lamb", "lamb"),
        ("mince", "beef"),      # default mince → beef
        ("sausage", "pork"),
        ("salmon", "seafood"),
        ("fish", "seafood"),
        ("prawn", "seafood"),
        ("tuna", "seafood"),
        ("egg", "eggs"),
        ("tofu", "vegetarian"),
        ("lentil", "vegetarian"),
        ("chickpea", "vegetarian"),
        ("bean", "vegetarian"),
    ]

    all_names = " ".join(
        ing.get("name", "").lower() for ing in ingredients
    )

    for keyword, protein in PROTEIN_KEYWORDS:
        if keyword in all_names:
            return protein

    return "vegetarian"


def infer_tags(doc: dict, cook_time_minutes: int) -> list:
    """Infer tags from existing recipe fields."""
    tags = []

    # Speed
    if cook_time_minutes <= 30:
        tags.append("quick")
    elif cook_time_minutes <= 60:
        tags.append("medium")
    else:
        tags.append("slow")

    # Leftovers
    if doc.get("leftovers"):
        tags.append("leftovers")
        tags.append("meal-prep")

    # Method hints from description/name
    text = (doc.get("name", "") + " " + doc.get("description", "")).lower()
    if "tray bake" in text or "traybake" in text:
        tags.append("tray-bake")
        tags.append("one-pan")
    if "soup" in text:
        tags.append("soup")
    if "stew" in text or "casserole" in text:
        tags.append("stew")
    if "stir fry" in text or "stir-fry" in text:
        tags.append("stir-fry")
    if "curry" in text:
        tags.append("curry")
        tags.append("asian")
    if "pasta" in text or "penne" in text or "spaghetti" in text:
        tags.append("pasta")
    if "rice" in text or "fried rice" in text:
        tags.append("rice")
    if "noodle" in text or "udon" in text or "ramen" in text:
        tags.append("asian")
    if "asian" in text or "soy" in text:
        if "asian" not in tags:
            tags.append("asian")
    if "winter" in text or "warming" in text or "hearty" in text:
        tags.append("winter-warmer")

    return list(set(tags))  # deduplicate


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def migrate_ingredient(ing: dict) -> dict:
    """Transform a single ingredient to the new clean shape."""
    name = ing.get("name", "")
    amount = ing.get("amount", "")
    quantity, unit = parse_quantity_and_unit(amount)
    search_key = derive_search_key(name)

    return {
        "name": name,
        "amount": amount,
        "quantity": quantity,
        "unit": unit,
        "searchKey": search_key,
        # Intentionally omitted: estimatedCost, fromSpecial, sharedWith
    }


def build_update(doc: dict) -> dict:
    """Build the $set payload for a recipe document."""
    cook_time_minutes = parse_cook_time_minutes(doc.get("cookTime", ""))
    ingredients_raw = doc.get("ingredients", [])
    clean_ingredients = [migrate_ingredient(i) for i in ingredients_raw]
    primary_protein = infer_primary_protein(ingredients_raw)
    tags = infer_tags(doc, cook_time_minutes)

    return {
        # MEA-68: new metadata fields
        "cookTimeMinutes": cook_time_minutes,
        "primaryProtein": primary_protein,
        "tags": tags,
        "season": doc.get("season", ["all"]),          # preserve if already set
        "dietaryFlags": doc.get("dietaryFlags", []),   # preserve if already set
        # MEA-69: clean ingredients
        "ingredients": clean_ingredients,
        # Bookkeeping
        "updatedAt": datetime.now(timezone.utc),
        "schemaVersion": 2,
    }


def run_migration(uri: str, db_name: str, collection: str, dry_run: bool):
    client = MongoClient(uri)
    db = client[db_name]
    col = db[collection]

    total = col.count_documents({})
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Migrating {total} recipes in '{db_name}.{collection}'...")
    print("-" * 60)

    ops = []
    skipped = 0
    errors = []

    for doc in col.find({}):
        recipe_id = doc.get("recipeId", str(doc["_id"]))

        # Skip if already migrated
        if doc.get("schemaVersion", 1) >= 2:
            skipped += 1
            continue

        try:
            update_payload = build_update(doc)

            if dry_run:
                # Show a preview
                print(f"\n  Recipe: {doc.get('name', '?')}")
                print(f"    cookTimeMinutes: {update_payload['cookTimeMinutes']}")
                print(f"    primaryProtein:  {update_payload['primaryProtein']}")
                print(f"    tags:            {update_payload['tags']}")
                print(f"    season:          {update_payload['season']}")
                sample_ing = update_payload["ingredients"][0] if update_payload["ingredients"] else {}
                print(f"    ingredients[0]:  {sample_ing}")
            else:
                ops.append(UpdateOne(
                    {"_id": doc["_id"]},
                    {"$set": update_payload}
                ))

        except Exception as e:
            errors.append(f"  {recipe_id}: {e}")

    if not dry_run and ops:
        result = col.bulk_write(ops, ordered=False)
        print(f"\n✅ Modified:  {result.modified_count}")
        print(f"   Skipped:   {skipped} (already at schemaVersion 2)")
        if errors:
            print(f"\n⚠️  Errors ({len(errors)}):")
            for e in errors:
                print(e)
    elif dry_run:
        print(f"\n[DRY RUN] Would update {total - skipped} recipes ({skipped} already migrated)")
        if errors:
            print(f"Errors found: {len(errors)}")
    else:
        print("Nothing to migrate.")

    client.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate recipes to schema v2 (MEA-68 + MEA-69)")
    parser.add_argument("--uri", default="mongodb://localhost:27017", help="MongoDB URI")
    parser.add_argument("--db", default="kai", help="Database name")
    parser.add_argument("--collection", default="recipes", help="Collection name")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    run_migration(args.uri, args.db, args.collection, args.dry_run)
