"""
Migrate paknsave-pricing.products from the flat price schema to the nested
`storePrice.{storeSlug}` map (MEA-115 schema alignment).

Flat (legacy):
    { _id, name, category, size, sourceSite, storeId: "PAK'nSAVE Lower Hutt",
      currentPrice, unitPrice, isSpecial, priceHistory, firstSeen,
      lastChecked, lastPriceChange, avgPrice90d, minPrice90d, maxPrice90d }

Nested (canonical):
    { _id, name, category, size, sourceSite,
      storePrice: { "paknsave-lower-hutt": {
          currentPrice, unitPrice, isSpecial, priceHistory, firstSeen,
          lastChecked, lastPriceChange, avgPrice90d, minPrice90d, maxPrice90d } } }

This mirrors MigrateAndUpdateProduct in pakn-scraper/src/MongoDB.cs so a
migrated doc is byte-identical to what the scraper would produce. Idempotent:
products that already have `storePrice` are skipped.

Usage (from paknsave-planner/scripts/):
    python migrate_to_nested.py --uri <MONGO_URI> --dry-run
    python migrate_to_nested.py --uri <MONGO_URI>
"""

import argparse
import sys

try:
    from pymongo import MongoClient, UpdateOne
except ImportError:
    print("pymongo not installed. Run: pip install pymongo --break-system-packages")
    sys.exit(1)

# Full storeId name (as written by the legacy flat scraper) -> store slug
# (the key used in the nested storePrice map and by the planner/matcher).
STORE_SLUG_BY_NAME = {
    "PAK'nSAVE Lower Hutt": "paknsave-lower-hutt",
    "PAK'nSAVE Porirua":    "paknsave-porirua",
    "PAK'nSAVE Petone":     "paknsave-petone",
    "PAK'nSAVE Kilbirnie":  "paknsave-kilbirnie",
}

# Flat price fields lifted into the storePrice entry, then removed from top level.
PRICE_FIELDS = [
    "currentPrice", "unitPrice", "isSpecial", "priceHistory", "firstSeen",
    "lastChecked", "lastPriceChange", "avgPrice90d", "minPrice90d", "maxPrice90d",
]


def store_slug(store_id: str) -> str:
    """Resolve a full storeId name to its slug; warn + fall back if unknown."""
    slug = STORE_SLUG_BY_NAME.get(store_id)
    if slug is None:
        slug = store_id.lower().replace("'", "").replace(" ", "-")
        print(f"  WARN unknown storeId {store_id!r} — using derived slug {slug!r}")
    return slug


def build_entry(doc: dict) -> dict:
    """Lift the doc's flat price fields into a storePrice entry."""
    return {f: doc[f] for f in PRICE_FIELDS if f in doc}


def run(uri: str, db_name: str, dry_run: bool):
    client = MongoClient(uri)
    products = client[db_name]["products"]

    total = products.estimated_document_count()
    already_nested = products.count_documents({"storePrice": {"$exists": True}})
    legacy = products.count_documents({
        "storePrice": {"$exists": False},
        "currentPrice": {"$exists": True},
    })
    print(f"{'[DRY RUN] ' if dry_run else ''}Migrating {db_name}.products")
    print("-" * 60)
    print(f"  total products:      {total}")
    print(f"  already nested:      {already_nested}")
    print(f"  legacy flat to move: {legacy}")

    if legacy == 0:
        print("\nNothing to migrate.")
        client.close()
        return

    ops = []
    skipped_no_store = 0
    cursor = products.find({
        "storePrice": {"$exists": False},
        "currentPrice": {"$exists": True},
    })
    for doc in cursor:
        store_id = doc.get("storeId")
        if not store_id:
            skipped_no_store += 1
            continue
        slug = store_slug(store_id)
        update = {
            "$set": {f"storePrice.{slug}": build_entry(doc)},
            "$unset": {f: "" for f in PRICE_FIELDS + ["storeId"]},
        }
        ops.append(UpdateOne({"_id": doc["_id"]}, update))

    if skipped_no_store:
        print(f"  WARN {skipped_no_store} products had no storeId — skipped")

    if dry_run:
        print(f"\n[DRY RUN] would migrate {len(ops)} products")
        client.close()
        return

    if ops:
        result = products.bulk_write(ops, ordered=False)
        print(f"\n  migrated: {result.modified_count} products")

    # Verify
    remaining = products.count_documents({
        "storePrice": {"$exists": False},
        "currentPrice": {"$exists": True},
    })
    nested_now = products.count_documents({"storePrice": {"$exists": True}})
    print(f"  nested now:          {nested_now}")
    print(f"  legacy remaining:    {remaining}")
    if remaining == 0:
        print("\nMigration complete.")
    else:
        print(f"\nWARNING: {remaining} legacy docs remain — re-run or inspect.")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flat -> nested storePrice migration")
    parser.add_argument("--uri", required=True, help="MongoDB URI")
    parser.add_argument("--db", default="paknsave-pricing", help="Pricing database name")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    run(args.uri, args.db, args.dry_run)
