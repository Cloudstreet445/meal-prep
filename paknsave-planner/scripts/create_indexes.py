"""
Create all MongoDB indexes for the recipe library and pricing DB.

  MEA-76  — recipe query indexes + pricing text search
  MEA-109 — schema v2 indexes (time range, equipment, mealType, skill,
            costTier, allergens, qualityFlags)

Recipes live in the `paknsave-meals` database; products live in the separate
`paknsave-pricing` database. searchTokens text index + match-cache indexes are
handled by pricing_enhance.py (MEA-111).

Run once:
    python create_indexes.py --uri mongodb://localhost:27017
    python create_indexes.py --recipes-db paknsave-meals --pricing-db paknsave-pricing
"""

import argparse
import sys

try:
    from pymongo import MongoClient, ASCENDING, TEXT
except ImportError:
    print("pymongo not installed. Run: pip install pymongo --break-system-packages")
    sys.exit(1)


def _create(collection, spec, name, **kwargs):
    try:
        collection.create_index(spec, name=name, **kwargs)
        print(f"  ok  {collection.name}.{name}")
    except Exception as e:
        print(f"  --  {collection.name}.{name}: {e}")


def create_indexes(uri: str, recipes_db: str, pricing_db: str):
    client = MongoClient(uri)

    print(f"\nRecipe indexes — {recipes_db}.recipes")
    print("-" * 60)
    recipes = client[recipes_db]["recipes"]

    # MEA-76 — single-field planner filters
    _create(recipes, [("primaryProtein", ASCENDING)], "idx_primaryProtein")
    _create(recipes, [("tags", ASCENDING)], "idx_tags")
    _create(recipes, [("season", ASCENDING)], "idx_season")
    _create(recipes, [("cookTimeMinutes", ASCENDING)], "idx_cookTimeMinutes")
    _create(recipes, [("lastUsedWeek", ASCENDING)], "idx_lastUsedWeek")
    _create(recipes, [("source.promptVersion", ASCENDING)], "idx_promptVersion")
    _create(recipes, [("schemaVersion", ASCENDING)], "idx_schemaVersion")

    # MEA-76 — compound planner query
    _create(
        recipes,
        [
            ("primaryProtein", ASCENDING),
            ("season", ASCENDING),
            ("lastUsedWeek", ASCENDING),
            ("cookTimeMinutes", ASCENDING),
        ],
        "idx_planner_query",
    )

    # MEA-109 — schema v2 query filters
    _create(recipes, [("time.totalRangeMinutes", ASCENDING)], "idx_time_range")
    _create(recipes, [("equipment", ASCENDING)], "idx_equipment")
    _create(recipes, [("mealType", ASCENDING)], "idx_mealType")
    _create(recipes, [("skillLevel", ASCENDING)], "idx_skillLevel")
    _create(recipes, [("costTier", ASCENDING)], "idx_costTier")
    _create(recipes, [("allergens", ASCENDING)], "idx_allergens")
    _create(recipes, [("qualityFlags.needsRegen", ASCENDING)], "idx_needsRegen")
    _create(recipes, [("qualityFlags.lastUsedWeek", ASCENDING)], "idx_qf_lastUsedWeek")

    print(f"\nPricing indexes — {pricing_db}.products")
    print("-" * 60)
    products = client[pricing_db]["products"]
    _create(products, [("name", TEXT)], "idx_name_text")
    _create(products, [("category", ASCENDING)], "idx_category")
    _create(products, [("lastChecked", ASCENDING)], "idx_lastChecked")
    print("  note  searchTokens text index + match-cache indexes: run pricing_enhance.py")

    print("\nDone.")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create MongoDB indexes (MEA-76 + MEA-109)")
    parser.add_argument("--uri", default="mongodb://localhost:27017", help="MongoDB URI")
    parser.add_argument("--recipes-db", default="paknsave-meals", help="Recipes database")
    parser.add_argument("--pricing-db", default="paknsave-pricing", help="Pricing database")
    args = parser.parse_args()

    create_indexes(args.uri, args.recipes_db, args.pricing_db)
