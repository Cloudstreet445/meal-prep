"""
Ingredient match validation script.
MEA-75: Report match rates across the full recipe library.

Usage:
    python validate_matches.py --uri mongodb://localhost:27017 --db kai --store "PAK'nSAVE Lower Hutt"
    python validate_matches.py --uri mongodb://localhost:27017 --db kai --store "PAK'nSAVE Lower Hutt" --output report.json
"""

import argparse
import json
import sys
from collections import defaultdict

try:
    from pymongo import MongoClient
except ImportError:
    print("pymongo not installed. Run: pip install pymongo --break-system-packages")
    sys.exit(1)

from ingredient_matcher import IngredientMatcher

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

THRESHOLD_EXACT = 0.9
THRESHOLD_GOOD = 0.7
THRESHOLD_WEAK = 0.5  # anything below this = unmatched


def run_validation(uri: str, db_name: str, store_id: str, output_path: str = None):
    client = MongoClient(uri)
    db = client[db_name]
    matcher = IngredientMatcher(db)
    recipes = db["recipes"]

    total_ingredients = 0
    exact_matches = 0     # confidence >= 0.9
    good_matches = 0      # 0.7 <= confidence < 0.9
    weak_matches = 0      # 0.5 <= confidence < 0.7
    unmatched = 0         # confidence < 0.5

    unmatched_details = []    # {searchKey, recipeName, bestScore}
    weak_details = []         # {searchKey, recipeName, matchedProduct, confidence}

    searchkey_results = defaultdict(list)  # searchKey → list of confidence scores

    print(f"\nValidating ingredient matches against store: {store_id}")
    print(f"DB: {db_name}.recipes")
    print("-" * 60)

    recipe_count = 0
    for recipe in recipes.find({}, {"name": 1, "ingredients": 1}):
        recipe_name = recipe.get("name", "?")
        recipe_count += 1

        for ing in recipe.get("ingredients", []):
            sk = ing.get("searchKey") or ing.get("name", "")
            if not sk:
                continue

            total_ingredients += 1
            result = matcher.match(sk, store_id)

            if result is None:
                confidence = 0.0
            else:
                confidence = result.confidence

            searchkey_results[sk].append(confidence)

            if confidence >= THRESHOLD_EXACT:
                exact_matches += 1
            elif confidence >= THRESHOLD_GOOD:
                good_matches += 1
                weak_details.append({
                    "searchKey": sk,
                    "recipeName": recipe_name,
                    "matchedProduct": result.product_name if result else None,
                    "confidence": confidence,
                })
            elif confidence >= THRESHOLD_WEAK:
                weak_matches += 1
                weak_details.append({
                    "searchKey": sk,
                    "recipeName": recipe_name,
                    "matchedProduct": result.product_name if result else None,
                    "confidence": confidence,
                })
            else:
                unmatched += 1
                unmatched_details.append({
                    "searchKey": sk,
                    "recipeName": recipe_name,
                    "bestConfidence": confidence,
                })

    # Aggregate unmatched by searchKey (deduplicate)
    unmatched_by_key = {}
    for d in unmatched_details:
        sk = d["searchKey"]
        if sk not in unmatched_by_key:
            unmatched_by_key[sk] = {"count": 0, "recipes": [], "bestConfidence": 0}
        unmatched_by_key[sk]["count"] += 1
        unmatched_by_key[sk]["recipes"].append(d["recipeName"])
        unmatched_by_key[sk]["bestConfidence"] = max(
            unmatched_by_key[sk]["bestConfidence"], d["bestConfidence"]
        )

    top_unmatched = sorted(
        unmatched_by_key.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:30]

    # Print report
    print(f"\nRecipes checked:      {recipe_count}")
    print(f"Total ingredients:    {total_ingredients}")
    print()
    pct = lambda n: f"{n/total_ingredients*100:.1f}%" if total_ingredients else "N/A"
    print(f"Exact match (≥0.9):   {exact_matches:4d}  ({pct(exact_matches)})")
    print(f"Good match  (≥0.7):   {good_matches:4d}  ({pct(good_matches)})")
    print(f"Weak match  (≥0.5):   {weak_matches:4d}  ({pct(weak_matches)})")
    print(f"Unmatched   (<0.5):   {unmatched:4d}  ({pct(unmatched)})")
    matched_total = exact_matches + good_matches + weak_matches
    print(f"\nOverall match rate:   {pct(matched_total)}")

    print(f"\n--- Top unmatched searchKeys ---")
    for sk, info in top_unmatched:
        print(f"  '{sk}'  ×{info['count']} recipes  (best score: {info['bestConfidence']:.2f})")

    # Save JSON report
    report = {
        "store_id": store_id,
        "recipe_count": recipe_count,
        "total_ingredients": total_ingredients,
        "exact_matches": exact_matches,
        "good_matches": good_matches,
        "weak_matches": weak_matches,
        "unmatched": unmatched,
        "match_rate_pct": round(matched_total / total_ingredients * 100, 1) if total_ingredients else 0,
        "top_unmatched": [
            {"searchKey": sk, **info}
            for sk, info in top_unmatched
        ],
        "weak_matches_detail": sorted(weak_details, key=lambda x: x["confidence"])[:50],
    }

    if output_path:
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {output_path}")

    client.close()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate ingredient→product match rates (MEA-75)")
    parser.add_argument("--uri", default="mongodb://localhost:27017")
    parser.add_argument("--db", default="kai")
    parser.add_argument("--store", default="PAK'nSAVE Lower Hutt", help="storeId to match against")
    parser.add_argument("--output", help="Save JSON report to this path")
    args = parser.parse_args()

    run_validation(args.uri, args.db, args.store, args.output)
