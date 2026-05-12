"""
Create all MongoDB indexes for Phase 0.
MEA-76: Recipe library query indexes + pricing text search.

Run once:
    python create_indexes.py --uri mongodb://localhost:27017 --db kai
"""

import argparse
import sys

try:
    from pymongo import MongoClient, ASCENDING, TEXT
except ImportError:
    print("pymongo not installed. Run: pip install pymongo --break-system-packages")
    sys.exit(1)


def create_indexes(uri: str, db_name: str):
    client = MongoClient(uri)
    db = client[db_name]

    print(f"\nCreating indexes on '{db_name}'...")
    print("-" * 60)

    # -----------------------------------------------------------------------
    # recipes collection
    # -----------------------------------------------------------------------
    recipes = db["recipes"]

    indexes = [
        # Single-field filters used by the planner query pipeline
        ([("primaryProtein", ASCENDING)], {"name": "idx_primaryProtein"}),
        ([("tags", ASCENDING)], {"name": "idx_tags"}),
        ([("season", ASCENDING)], {"name": "idx_season"}),
        ([("cookTimeMinutes", ASCENDING)], {"name": "idx_cookTimeMinutes"}),
        ([("lastUsedWeek", ASCENDING)], {"name": "idx_lastUsedWeek"}),
        ([("source", ASCENDING)], {"name": "idx_source"}),
        ([("schemaVersion", ASCENDING)], {"name": "idx_schemaVersion"}),

        # Compound — most common planner query:
        # {primaryProtein, season, lastUsedWeek} filtered, sorted by cookTimeMinutes
        (
            [
                ("primaryProtein", ASCENDING),
                ("season", ASCENDING),
                ("lastUsedWeek", ASCENDING),
                ("cookTimeMinutes", ASCENDING),
            ],
            {"name": "idx_planner_query"},
        ),

        # Ratings-based sorting
        ([("ratings", ASCENDING)], {"name": "idx_ratings"}),
    ]

    for index_spec, kwargs in indexes:
        try:
            name = recipes.create_index(index_spec, **kwargs)
            print(f"  ✅ recipes.{kwargs['name']}")
        except Exception as e:
            print(f"  ⚠️  recipes.{kwargs['name']}: {e}")

    # -----------------------------------------------------------------------
    # paknsave-pricing collection
    # -----------------------------------------------------------------------
    pricing = db["paknsave-pricing"]

    pricing_indexes = [
        # Text search — used by fuzzy ingredient matcher
        ([("name", TEXT)], {"name": "idx_name_text"}),

        # Category + store compound — used to filter candidates before text match
        (
            [("category", ASCENDING), ("storeId", ASCENDING)],
            {"name": "idx_category_store"},
        ),

        # isSpecial — for "show me what's on special" queries
        ([("isSpecial", ASCENDING)], {"name": "idx_isSpecial"}),

        # lastChecked — for freshness checks
        ([("lastChecked", ASCENDING)], {"name": "idx_lastChecked"}),
    ]

    for index_spec, kwargs in pricing_indexes:
        try:
            name = pricing.create_index(index_spec, **kwargs)
            print(f"  ✅ paknsave-pricing.{kwargs['name']}")
        except Exception as e:
            print(f"  ⚠️  paknsave-pricing.{kwargs['name']}: {e}")

    print("\nDone.")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create MongoDB indexes (MEA-76)")
    parser.add_argument("--uri", default="mongodb://localhost:27017", help="MongoDB URI")
    parser.add_argument("--db", default="kai", help="Database name")
    args = parser.parse_args()

    create_indexes(args.uri, args.db)
