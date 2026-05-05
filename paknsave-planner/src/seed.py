#!/usr/bin/env python3
"""Seed test data into MongoDB.

Usage (from paknsave-planner/):
    python src/seed.py
"""

import glob
import json
import sys
import os

# Ensure src/ is on the path so local imports work
sys.path.insert(0, os.path.dirname(__file__))

from mongodb import store_recipes, store_bundle

# Resolve test-data/ relative to this file, not cwd
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DIR  = os.path.join(BASE_DIR, "test-data")
PATTERN   = os.path.join(TEST_DIR, "test-*-response.json")


def main():
    files = sorted(glob.glob(PATTERN))

    if not files:
        print(f"❌  No files found at {PATTERN}")
        sys.exit(1)

    print(f"\n🌱  Seeding {len(files)} test bundles...\n")

    for path in files:
        filename = os.path.basename(path)
        print(f"  📂  {filename}")

        with open(path) as f:
            plan = json.load(f)

        week_id = plan.get("week")
        if not week_id:
            print(f"       ⚠️  No 'week' field — skipping")
            continue

        try:
            recipe_count, recipe_ids = store_recipes(plan, week_id)
            bundle_id = store_bundle(plan, week_id, recipe_ids)
            print(f"       ✓  {recipe_count} recipes  |  week: {week_id}")
            print(f"       ✓  bundle: {bundle_id}")
        except Exception as e:
            print(f"       ❌  Failed: {e}")

    print(f"\n✅  Done\n")


if __name__ == "__main__":
    main()
