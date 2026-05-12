"""
Bulk recipe generation script.
MEA-72: Generate 200+ recipes and insert into MongoDB.

Usage:
    # Dry run — generate but don't insert
    python bulk_generate.py --batch 1 --dry-run

    # Run a single batch
    python bulk_generate.py --batch 1

    # Run all 10 batches
    python bulk_generate.py --all

    # Resume from a specific batch (if earlier batches completed)
    python bulk_generate.py --from-batch 4 --all

Requirements:
    pip install pymongo anthropic --break-system-packages

Environment:
    ANTHROPIC_API_KEY=sk-...
    MONGO_URI=mongodb://localhost:27017
    MONGO_DB=kai
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

try:
    import anthropic
except ImportError:
    print("anthropic not installed. Run: pip install anthropic --break-system-packages")
    sys.exit(1)

try:
    from pymongo import MongoClient
except ImportError:
    print("pymongo not installed. Run: pip install pymongo --break-system-packages")
    sys.exit(1)

from generation_prompt import (
    BATCHES, SYSTEM_PROMPT, build_user_prompt,
    parse_generation_response, make_recipe_id
)

try:
    from recipe_schema import validate_recipe
    VALIDATE = True
except ImportError:
    print("Warning: recipe_schema.py not found — skipping validation")
    VALIDATE = False

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB", "kai")
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 8000
RECIPES_PER_BATCH = 20
SLEEP_BETWEEN_BATCHES = 3  # seconds, to avoid rate limits

# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_batch(client: anthropic.Anthropic, batch: dict, existing_names: list, dry_run: bool) -> list:
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Generating batch {batch['id']}: {batch['label']}...")

    user_prompt = build_user_prompt(batch, count=RECIPES_PER_BATCH, existing_names=existing_names)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text
    recipes = parse_generation_response(raw)
    print(f"  Parsed {len(recipes)} recipes from response.")
    return recipes


def enrich_recipe(recipe: dict, source_batch: dict) -> dict:
    """Add system fields before inserting into MongoDB."""
    now = datetime.now(timezone.utc)
    name = recipe.get("name", "Unnamed Recipe")
    recipe_id = make_recipe_id(name)

    return {
        **recipe,
        "recipeId": recipe_id,
        "source": "claude",
        "usageHistory": [],
        "bundleHistory": [],
        "lastUsedWeek": None,
        "schemaVersion": 2,
        "generationBatch": source_batch["label"],
        "createdAt": now,
        "updatedAt": now,
    }


def insert_recipes(col, recipes: list, dry_run: bool) -> tuple:
    """Insert recipes, skipping duplicates. Returns (inserted, skipped, errors)."""
    inserted = 0
    skipped = 0
    errors = []

    for recipe in recipes:
        recipe_id = recipe.get("recipeId")
        name = recipe.get("name", "?")

        # Validate
        if VALIDATE:
            validation_errors = validate_recipe(recipe)
            if validation_errors:
                errors.append(f"  INVALID '{name}': {'; '.join(validation_errors[:3])}")
                continue

        # Deduplication check
        if col.find_one({"recipeId": recipe_id}):
            print(f"  ⏭  Skipping duplicate: {name}")
            skipped += 1
            continue

        if dry_run:
            print(f"  [DRY RUN] Would insert: {name}")
            inserted += 1
        else:
            try:
                col.insert_one(recipe)
                print(f"  ✅ Inserted: {name}")
                inserted += 1
            except Exception as e:
                errors.append(f"  DB ERROR '{name}': {e}")

    return inserted, skipped, errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(batch_ids: list, dry_run: bool):
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        sys.exit(1)

    ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client[MONGO_DB]
    col = db["recipes"]

    total_inserted = 0
    total_skipped = 0
    all_errors = []

    # Load existing recipe names for dedup in prompts
    existing_names = [doc["name"] for doc in col.find({}, {"name": 1})]
    print(f"Starting generation. Existing recipes in DB: {len(existing_names)}")
    print(f"Batches to run: {[b for b in batch_ids]}")
    print(f"Target: {len(batch_ids) * RECIPES_PER_BATCH} new recipes\n")

    for batch_id in batch_ids:
        batch = next((b for b in BATCHES if b["id"] == batch_id), None)
        if not batch:
            print(f"  Unknown batch ID: {batch_id}, skipping.")
            continue

        try:
            raw_recipes = generate_batch(ai_client, batch, existing_names, dry_run)
        except Exception as e:
            print(f"  ❌ Generation failed for batch {batch_id}: {e}")
            all_errors.append(f"Batch {batch_id} generation: {e}")
            continue

        # Enrich with system fields
        enriched = [enrich_recipe(r, batch) for r in raw_recipes]

        # Insert
        inserted, skipped, errors = insert_recipes(col, enriched, dry_run)
        total_inserted += inserted
        total_skipped += skipped
        all_errors.extend(errors)

        # Add new names to dedup list
        existing_names.extend(r.get("name", "") for r in raw_recipes)

        if len(batch_ids) > 1 and batch_id != batch_ids[-1]:
            print(f"  Sleeping {SLEEP_BETWEEN_BATCHES}s before next batch...")
            time.sleep(SLEEP_BETWEEN_BATCHES)

    # Summary
    print("\n" + "=" * 60)
    print(f"{'[DRY RUN] ' if dry_run else ''}SUMMARY")
    print(f"  Inserted:  {total_inserted}")
    print(f"  Skipped:   {total_skipped} (duplicates or validation failures)")
    final_count = col.count_documents({})
    print(f"  Total recipes in DB now: {final_count}")
    if all_errors:
        print(f"\n  ⚠️  Errors ({len(all_errors)}):")
        for e in all_errors:
            print(e)
    print("=" * 60)
    mongo_client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk recipe generation (MEA-72)")
    parser.add_argument("--batch", type=int, help="Run a single batch by ID (1–10)")
    parser.add_argument("--all", action="store_true", help="Run all 10 batches")
    parser.add_argument("--from-batch", type=int, default=1, help="Start from this batch ID (use with --all)")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't insert")
    args = parser.parse_args()

    if args.batch:
        batch_ids = [args.batch]
    elif args.all:
        batch_ids = list(range(args.from_batch, 11))
    else:
        parser.print_help()
        sys.exit(1)

    run(batch_ids, args.dry_run)
