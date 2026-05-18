"""
Pricing DB enhancements for fuzzy ingredient matching (MEA-111).

Applies three improvements to the `paknsave-pricing` database so ingredient
lookups are faster and more resilient to NZ vs generic naming:

  1. searchTokens — backfill the precomputed token array on every product in
     the `products` collection (new products get it from the scraper; see
     pakn-scraper/src/Utilities.cs GenerateSearchTokens).
  2. ingredient_synonyms — seed the NZ/UK/US naming collection.
  3. ingredient_match_cache — create the reverse-lookup cache collection with
     a unique searchKey index and a 7-day TTL index.

Also creates the `searchTokens` text index on `products`.

Usage (from paknsave-planner/scripts/):
    python pricing_enhance.py --all
    python pricing_enhance.py --tokens --dry-run
    python pricing_enhance.py --synonyms
    python pricing_enhance.py --cache
    python pricing_enhance.py --all --uri mongodb://localhost:27017
"""

import argparse
import sys

try:
    from pymongo import MongoClient, UpdateOne, ASCENDING
except ImportError:
    print("pymongo not installed. Run: pip install pymongo --break-system-packages")
    sys.exit(1)

from pricing_tokens import tokenise
from ingredient_synonyms import SYNONYMS

CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 604800 — one week


# ---------------------------------------------------------------------------
# 1. searchTokens backfill
# ---------------------------------------------------------------------------

def backfill_search_tokens(db, dry_run: bool):
    products = db["products"]
    total = products.count_documents({})
    print(f"\n[searchTokens] {total} products in 'products' collection")

    ops = []
    changed = 0
    for doc in products.find({}, {"name": 1, "searchTokens": 1}):
        tokens = tokenise(doc.get("name", ""))
        if doc.get("searchTokens") == tokens:
            continue
        changed += 1
        if not dry_run:
            ops.append(UpdateOne({"_id": doc["_id"]},
                                 {"$set": {"searchTokens": tokens}}))

    if dry_run:
        print(f"[searchTokens] [DRY RUN] would update {changed} products")
        return

    if ops:
        result = products.bulk_write(ops, ordered=False)
        print(f"[searchTokens] updated {result.modified_count} products")
    else:
        print("[searchTokens] all products already up to date")

    # Plain multikey index — serves the matcher's `$in` token query (MEA-115).
    # No text index: Mongo allows only one $text index per collection and the
    # matcher uses `$in`, not `$text`, so a text index on searchTokens is moot.
    products.create_index([("searchTokens", ASCENDING)], name="idx_searchTokens")
    print("[searchTokens] created index idx_searchTokens")


# ---------------------------------------------------------------------------
# 2. ingredient_synonyms seed
# ---------------------------------------------------------------------------

def seed_synonyms(db, dry_run: bool):
    col = db["ingredient_synonyms"]
    print(f"\n[synonyms] seeding {len(SYNONYMS)} entries into 'ingredient_synonyms'")

    if dry_run:
        print(f"[synonyms] [DRY RUN] would upsert {len(SYNONYMS)} canonical entries")
        return

    ops = [
        UpdateOne(
            {"canonical": entry["canonical"]},
            {"$set": {"canonical": entry["canonical"], "variants": entry["variants"]}},
            upsert=True,
        )
        for entry in SYNONYMS
    ]
    result = col.bulk_write(ops, ordered=False)
    col.create_index([("canonical", ASCENDING)], unique=True, name="idx_canonical")
    col.create_index([("variants", ASCENDING)], name="idx_variants")
    print(f"[synonyms] upserted={result.upserted_count} modified={result.modified_count}")
    print("[synonyms] created indexes idx_canonical (unique), idx_variants")


# ---------------------------------------------------------------------------
# 3. ingredient_match_cache collection
# ---------------------------------------------------------------------------

def create_match_cache(db, dry_run: bool):
    print("\n[cache] preparing 'ingredient_match_cache' collection")

    if dry_run:
        print("[cache] [DRY RUN] would create unique searchKey index + TTL index")
        return

    col = db["ingredient_match_cache"]
    col.create_index([("searchKey", ASCENDING)], unique=True, name="idx_searchKey")
    # TTL — Mongo expires docs CACHE_TTL_SECONDS after `matchedAt`.
    # `matchedAt` must be written as a BSON date for the TTL monitor to act.
    col.create_index([("matchedAt", ASCENDING)],
                     expireAfterSeconds=CACHE_TTL_SECONDS, name="idx_matchedAt_ttl")
    print(f"[cache] created idx_searchKey (unique) and idx_matchedAt_ttl "
          f"(expireAfterSeconds={CACHE_TTL_SECONDS})")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run(uri: str, db_name: str, do_tokens: bool, do_synonyms: bool,
        do_cache: bool, dry_run: bool):
    client = MongoClient(uri)
    db = client[db_name]
    print(f"{'[DRY RUN] ' if dry_run else ''}Enhancing pricing DB: {db_name}")
    print("-" * 60)

    if do_tokens:
        backfill_search_tokens(db, dry_run)
    if do_synonyms:
        seed_synonyms(db, dry_run)
    if do_cache:
        create_match_cache(db, dry_run)

    print("\nDone.")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pricing DB enhancements (MEA-111)")
    parser.add_argument("--uri", default="mongodb://localhost:27017", help="MongoDB URI")
    parser.add_argument("--db", default="paknsave-pricing", help="Pricing database name")
    parser.add_argument("--tokens", action="store_true", help="Backfill searchTokens")
    parser.add_argument("--synonyms", action="store_true", help="Seed ingredient_synonyms")
    parser.add_argument("--cache", action="store_true", help="Create ingredient_match_cache")
    parser.add_argument("--all", action="store_true", help="Run all three steps")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    if not (args.tokens or args.synonyms or args.cache or args.all):
        parser.print_help()
        sys.exit(1)

    run(
        args.uri, args.db,
        do_tokens=args.tokens or args.all,
        do_synonyms=args.synonyms or args.all,
        do_cache=args.cache or args.all,
        dry_run=args.dry_run,
    )
