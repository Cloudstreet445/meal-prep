"""
Mass recipe data puller — bulk recipe generation, schema v2.

  MEA-72  — original bulk generation script
  MEA-112 — v2 prompt + strict pre-insert validation

Designed so generation (which costs API spend) is fully separated from the
Mongo import. You generate to reviewable JSON staging files, inspect the
quality, and only then import. Nothing is written to Mongo until you have a
top-tier dataset you are happy with.

WORKFLOW
--------
  1. Generate recipes to local staging files (calls the Anthropic API):

       python bulk_generate.py generate --batch 1
       python bulk_generate.py generate --all
       python bulk_generate.py generate --all --from-batch 4   # resume

  2. Review the staged dataset — no API calls, no DB writes:

       python bulk_generate.py review

  3. Import the staged dataset into MongoDB once you are happy with it:

       python bulk_generate.py import --dry-run    # preview
       python bulk_generate.py import

Raw API responses are checkpointed to recipe_data/raw/ so a crash mid-run
never loses spent tokens. Re-running `generate` overwrites a batch's staging
file; already-generated batches can be skipped with --from-batch.

Requirements:
    pip install pymongo anthropic --break-system-packages

Environment:
    ANTHROPIC_API_KEY=sk-...
    MONGO_URI=mongodb://localhost:27017
    RECIPES_DB=paknsave-meals          # defaults to paknsave-meals
"""

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone

from generation_prompt import (
    BATCHES, SYSTEM_PROMPT, GENERATION_MODEL, PROMPT_VERSION,
    build_user_prompt, parse_generation_response, make_recipe_id,
)
from recipe_schema import SCHEMA_VERSION, validate_generated_recipe

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
# The recipes collection lives in paknsave-meals (see src/config.py MEALS_DB).
RECIPES_DB = (
    os.environ.get("RECIPES_DB")
    or os.environ.get("MONGO_DB")
    or "paknsave-meals"
)

MAX_TOKENS = 8000
RECIPES_PER_BATCH = 20
SLEEP_BETWEEN_BATCHES = 3      # seconds, to stay under rate limits
API_MAX_RETRIES = 4
API_BACKOFF_BASE = 2          # seconds: 2, 4, 8, 16

# Local data directories — reviewable JSON, never committed (see .gitignore).
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "recipe_data")
STAGING_DIR = os.path.join(DATA_DIR, "staging")
RAW_DIR = os.path.join(DATA_DIR, "raw")


def _staging_path(batch: dict) -> str:
    return os.path.join(STAGING_DIR, f"batch-{batch['id']:02d}-{batch['label']}.json")


def _raw_path(batch: dict) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return os.path.join(RAW_DIR, f"batch-{batch['id']:02d}-{batch['label']}-{stamp}.txt")


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _call_anthropic(client, user_prompt: str) -> str:
    """Call the API with exponential-backoff retries on transient errors."""
    import anthropic

    for attempt in range(API_MAX_RETRIES):
        try:
            response = client.messages.create(
                model=GENERATION_MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except (anthropic.RateLimitError, anthropic.APIStatusError,
                anthropic.APIConnectionError) as e:
            if attempt == API_MAX_RETRIES - 1:
                raise
            wait = API_BACKOFF_BASE ** (attempt + 1)
            print(f"  API error ({type(e).__name__}); retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError("unreachable")


def generate_batch(client, batch: dict, existing_names: list) -> dict:
    """Generate one batch, validate it, and return a staging payload dict."""
    print(f"\nGenerating batch {batch['id']}: {batch['label']} — {batch['focus']}")

    user_prompt = build_user_prompt(batch, count=RECIPES_PER_BATCH,
                                    existing_names=existing_names)
    raw = _call_anthropic(client, user_prompt)

    # Checkpoint the raw response before parsing — protects spent tokens.
    raw_file = _raw_path(batch)
    with open(raw_file, "w") as f:
        f.write(raw)

    recipes = parse_generation_response(raw)
    print(f"  Parsed {len(recipes)} recipes.")

    valid, invalid = [], []
    for recipe in recipes:
        errors = validate_generated_recipe(recipe)
        if errors:
            invalid.append({
                "name": recipe.get("name", "?"),
                "errors": errors,
                "recipe": recipe,
            })
        else:
            valid.append(recipe)

    print(f"  Valid: {len(valid)}  |  Invalid (rejected): {len(invalid)}")
    for bad in invalid:
        print(f"    REJECTED '{bad['name']}': {'; '.join(bad['errors'][:3])}")

    return {
        "batchId": batch["id"],
        "batchLabel": batch["label"],
        "promptVersion": PROMPT_VERSION,
        "model": GENERATION_MODEL,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "rawResponseFile": os.path.relpath(raw_file, DATA_DIR),
        "validCount": len(valid),
        "invalidCount": len(invalid),
        "recipes": valid,
        "invalid": invalid,
    }


def run_generate(batch_ids: list):
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    import anthropic
    os.makedirs(STAGING_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Seed dedup list with names already staged from earlier batches.
    existing_names = _staged_recipe_names()
    print(f"Recipes already staged: {len(existing_names)}")
    print(f"Batches to generate: {batch_ids}")

    total_valid = 0
    for batch_id in batch_ids:
        batch = next((b for b in BATCHES if b["id"] == batch_id), None)
        if not batch:
            print(f"  Unknown batch ID {batch_id}, skipping.")
            continue

        try:
            payload = generate_batch(client, batch, existing_names)
        except Exception as e:
            print(f"  GENERATION FAILED for batch {batch_id}: {e}")
            continue

        with open(_staging_path(batch), "w") as f:
            json.dump(payload, f, indent=2)
        print(f"  Staged -> {os.path.relpath(_staging_path(batch), DATA_DIR)}")

        total_valid += payload["validCount"]
        existing_names.extend(r.get("name", "") for r in payload["recipes"])

        if batch_id != batch_ids[-1]:
            time.sleep(SLEEP_BETWEEN_BATCHES)

    print(f"\nDone. {total_valid} valid recipes staged across {len(batch_ids)} batch(es).")
    print("Next: `python bulk_generate.py review`")


# ---------------------------------------------------------------------------
# Staging helpers
# ---------------------------------------------------------------------------

def _load_staging() -> list:
    """Load every staging payload file. Returns list of payload dicts."""
    if not os.path.isdir(STAGING_DIR):
        return []
    payloads = []
    for fname in sorted(os.listdir(STAGING_DIR)):
        if fname.endswith(".json"):
            with open(os.path.join(STAGING_DIR, fname)) as f:
                payloads.append(json.load(f))
    return payloads


def _staged_recipe_names() -> list:
    names = []
    for payload in _load_staging():
        names.extend(r.get("name", "") for r in payload.get("recipes", []))
    return names


# ---------------------------------------------------------------------------
# Review — quality summary, no API calls, no DB writes
# ---------------------------------------------------------------------------

def run_review():
    payloads = _load_staging()
    if not payloads:
        print(f"No staging files in {STAGING_DIR}. Run `generate` first.")
        sys.exit(1)

    all_recipes = []
    total_invalid = 0
    print("\n=== STAGED DATASET REVIEW ===\n")
    for p in payloads:
        all_recipes.extend(p.get("recipes", []))
        total_invalid += p.get("invalidCount", 0)
        print(f"  batch {p['batchId']:>2} {p['batchLabel']:<14} "
              f"valid {p['validCount']:>3}  rejected {p['invalidCount']:>2}")

    proteins = Counter(r.get("primaryProtein", "?") for r in all_recipes)
    cost_tiers = Counter(r.get("costTier", "?") for r in all_recipes)
    skills = Counter(r.get("skillLevel", "?") for r in all_recipes)
    seasons = Counter(s for r in all_recipes for s in (r.get("season") or []))

    names = [r.get("name", "") for r in all_recipes]
    dupes = [n for n, c in Counter(names).items() if c > 1]

    print(f"\n  Total valid recipes staged: {len(all_recipes)}")
    print(f"  Total rejected by validation: {total_invalid}")
    print(f"  Duplicate names within staging: {len(dupes)}")
    print(f"\n  Protein spread:  {dict(proteins)}")
    print(f"  Cost tier spread: {dict(cost_tiers)}")
    print(f"  Skill spread:     {dict(skills)}")
    print(f"  Season spread:    {dict(seasons)}")

    meat = [r for r in all_recipes
            if r.get("primaryProtein") in {"chicken", "pork", "beef", "lamb"}]
    missing_subs = [r["name"] for r in meat if not r.get("proteinSubstitutes")]
    if missing_subs:
        print(f"\n  WARNING: {len(missing_subs)} meat recipes lack proteinSubstitutes")

    print("\n  If this looks top-tier, run: `python bulk_generate.py import`")


# ---------------------------------------------------------------------------
# Import — enrich staged recipes and write to MongoDB
# ---------------------------------------------------------------------------

def enrich_recipe(recipe: dict, batch_label: str) -> dict:
    """Add system + lifecycle fields, deriving v1 denormalised aliases."""
    now = datetime.now(timezone.utc)
    name = recipe.get("name", "Unnamed Recipe")

    time_obj = recipe.get("time") or {}
    rng = time_obj.get("totalRangeMinutes")
    cook_minutes = rng[1] if isinstance(rng, list) and len(rng) == 2 else 45

    return {
        **recipe,
        "recipeId": make_recipe_id(name),
        # Denormalised v1 aliases — keep existing indexes/queries working.
        "cookTime": f"{cook_minutes} min",
        "cookTimeMinutes": cook_minutes,
        "source": {
            "promptVersion": PROMPT_VERSION,
            "generationDate": now.strftime("%Y-%m-%d"),
            "model": GENERATION_MODEL,
        },
        "qualityFlags": {
            "userRating": None,
            "timesUsed": 0,
            "lastUsedWeek": None,
            "userNotes": None,
            "needsRegen": False,
        },
        "imageUrl": recipe.get("imageUrl"),
        "usageHistory": [],
        "bundleHistory": [],
        "lastUsedWeek": None,
        "schemaVersion": SCHEMA_VERSION,
        "generationBatch": batch_label,
        "createdAt": now,
        "updatedAt": now,
    }


def run_import(dry_run: bool):
    payloads = _load_staging()
    if not payloads:
        print(f"No staging files in {STAGING_DIR}. Run `generate` first.")
        sys.exit(1)

    from pymongo import MongoClient

    client = MongoClient(MONGO_URI)
    col = client[RECIPES_DB]["recipes"]

    existing_ids = set()
    if not dry_run:
        existing_ids = {d["recipeId"] for d in col.find({}, {"recipeId": 1})}

    inserted = skipped = revalidation_failed = 0
    seen_ids = set()
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Importing into {RECIPES_DB}.recipes\n")

    for payload in payloads:
        for recipe in payload.get("recipes", []):
            # Re-validate at import — staging files may have been hand-edited.
            errors = validate_generated_recipe(recipe)
            if errors:
                print(f"  REJECTED '{recipe.get('name', '?')}': {errors[0]}")
                revalidation_failed += 1
                continue

            doc = enrich_recipe(recipe, payload.get("batchLabel", "?"))
            rid = doc["recipeId"]

            if rid in existing_ids or rid in seen_ids:
                print(f"  skip duplicate: {doc['name']}")
                skipped += 1
                continue
            seen_ids.add(rid)

            if dry_run:
                print(f"  [DRY RUN] would insert: {doc['name']}")
                inserted += 1
            else:
                col.insert_one(doc)
                print(f"  inserted: {doc['name']}")
                inserted += 1

    print("\n" + "=" * 60)
    print(f"{'[DRY RUN] ' if dry_run else ''}IMPORT SUMMARY")
    print(f"  Inserted:              {inserted}")
    print(f"  Skipped (duplicates):  {skipped}")
    print(f"  Rejected (validation): {revalidation_failed}")
    if not dry_run:
        print(f"  Total recipes in DB:   {col.count_documents({})}")
    print("=" * 60)
    client.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Mass recipe data puller (MEA-72/112)")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Generate recipes to staging files")
    g.add_argument("--batch", type=int,
                   help=f"Run a single batch by ID (1-{len(BATCHES)})")
    g.add_argument("--all", action="store_true",
                   help=f"Run all {len(BATCHES)} batches")
    g.add_argument("--from-batch", type=int, default=1,
                   help="Start batch (use with --all)")

    sub.add_parser("review", help="Summarise the staged dataset quality")

    i = sub.add_parser("import", help="Import staged recipes into MongoDB")
    i.add_argument("--dry-run", action="store_true", help="Preview without writing")

    args = parser.parse_args()

    if args.command == "generate":
        if args.batch:
            run_generate([args.batch])
        elif args.all:
            run_generate(list(range(args.from_batch, len(BATCHES) + 1)))
        else:
            g.print_help()
            sys.exit(1)
    elif args.command == "review":
        run_review()
    elif args.command == "import":
        run_import(args.dry_run)


if __name__ == "__main__":
    main()
