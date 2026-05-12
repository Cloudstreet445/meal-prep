#!/usr/bin/env python3
"""Backfill existing recipe documents to the Phase 0 schema.

What this does:
  - Computes baselineCost from legacy per-ingredient estimatedCost (before stripping)
  - Removes estimatedCost, fromSpecial, sharedWith from every ingredient
  - Adds unit, quantity, searchKey (empty defaults) to ingredients that lack them
  - Adds primaryProtein, tags, season, dietaryFlags, cookTimeMinutes to recipes that lack them

Usage (from paknsave-planner/):
    python scripts/migrate_recipe_schema.py [--dry-run]
"""

import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from db.mongodb import _client, MEALS_DB
from datetime import datetime

DRY_RUN = "--dry-run" in sys.argv

_PRICE_FIELDS = {"estimatedCost", "fromSpecial", "sharedWith"}

_PROTEIN_KEYWORDS = {
    "chicken": ["chicken"],
    "pork":    ["pork", "sausage"],
    "beef":    ["beef", "mince"],
    "lamb":    ["lamb"],
}

_COOK_TIME_RE = re.compile(r'(\d+)')


def _infer_protein(recipe: dict) -> str:
    text = " ".join(i.get("name", "").lower() for i in recipe.get("ingredients", []))
    text += " " + recipe.get("name", "").lower()
    for protein, keywords in _PROTEIN_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return protein
    return "other"


def _parse_cook_time_minutes(cook_time: str) -> int:
    if not cook_time:
        return 0
    m = _COOK_TIME_RE.search(cook_time)
    return int(m.group(1)) if m else 0


def migrate():
    db = _client[MEALS_DB]
    recipes = list(db["recipes"].find({}))

    print(f"Found {len(recipes)} recipes to migrate.")
    if DRY_RUN:
        print("DRY RUN — no writes will be made.\n")

    updated = 0
    skipped = 0

    for recipe in recipes:
        recipe_id = recipe.get("recipeId", str(recipe["_id"]))
        ingredients = recipe.get("ingredients", [])

        # Compute baselineCost from legacy estimatedCost before stripping
        baseline = sum(i.get("estimatedCost", 0) for i in ingredients)

        # Build clean ingredient list
        clean_ingredients = []
        for ing in ingredients:
            clean = {k: v for k, v in ing.items() if k not in _PRICE_FIELDS}
            clean.setdefault("unit", "")
            clean.setdefault("quantity", 0.0)
            clean.setdefault("searchKey", "")
            clean_ingredients.append(clean)

        update = {
            "ingredients":     clean_ingredients,
            "primaryProtein":  recipe.get("primaryProtein") or _infer_protein(recipe),
            "tags":            recipe.get("tags", []),
            "season":          recipe.get("season", ["all"]),
            "dietaryFlags":    recipe.get("dietaryFlags", []),
            "cookTimeMinutes": recipe.get("cookTimeMinutes") or _parse_cook_time_minutes(recipe.get("cookTime", "")),
            "baselineCost":    recipe.get("baselineCost", baseline),
            "updatedAt":       datetime.now(),
        }

        needs_update = (
            any(f in ing for ing in ingredients for f in _PRICE_FIELDS)
            or "primaryProtein" not in recipe
            or "tags" not in recipe
            or "season" not in recipe
            or "dietaryFlags" not in recipe
            or "cookTimeMinutes" not in recipe
            or "baselineCost" not in recipe
        )

        if not needs_update:
            skipped += 1
            continue

        print(f"  {'[DRY] ' if DRY_RUN else ''}Updating {recipe_id} — baselineCost=${baseline:.2f}, protein={update['primaryProtein']}, cookTimeMinutes={update['cookTimeMinutes']}")

        if not DRY_RUN:
            db["recipes"].update_one(
                {"_id": recipe["_id"]},
                {"$set": update}
            )
        updated += 1

    print(f"\nDone. {updated} updated, {skipped} already up to date.")


if __name__ == "__main__":
    migrate()
