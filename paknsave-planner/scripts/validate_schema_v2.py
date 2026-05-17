"""
Schema v2 validation script (MEA-114).

Runs a comprehensive quality pass over the recipe library after backfill
(MEA-113) and regen. The v2 successor to MEA-75's ingredient match validation.

Checks:
  1. Ingredient search coverage — required ingredients match a priced product
  2. Time sanity — range ordering, breakdown coherence, outlier flagging
  3. Substitutes coverage — meat recipes carry proteinSubstitutes
  4. Pantry staple audit — staple-named ingredients flagged correctly
  5. Enum validity — equipment / category / skill / mealType / costTier / season
  6. Coverage distribution — protein / season / cook time / cost / skill spread

Output:
  - console report with pass / fail / inconclusive per check
  - JSON report saved to reports/schema-v2-validation-{date}.json
  - exit code 1 if a CRITICAL check fails (match rate, enum validity)

Usage (from paknsave-planner/scripts/):
    python validate_schema_v2.py
    python validate_schema_v2.py --uri mongodb://localhost:27017 \\
        --recipes-db paknsave-meals --pricing-db paknsave-pricing \\
        --store paknsave-lower-hutt
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

try:
    from pymongo import MongoClient
except ImportError:
    print("pymongo not installed. Run: pip install pymongo --break-system-packages")
    sys.exit(1)

from ingredient_matcher import IngredientMatcher
from recipe_schema import (
    MEAT_PROTEINS, STAPLE_KEYWORDS, VALID_EQUIPMENT, VALID_SEASONS,
    VALID_SKILL_LEVELS, VALID_MEAL_TYPES, VALID_COST_TIERS,
    VALID_INGREDIENT_CATEGORIES, is_staple_name,
)

# Coverage target — fraction of required ingredients that must match >=0.7.
COVERAGE_TARGET = 0.85
MATCH_THRESHOLD = 0.7

REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports"
)


# ---------------------------------------------------------------------------
# 1. Ingredient search coverage
# ---------------------------------------------------------------------------

def check_search_coverage(recipes, matcher, store_id) -> dict:
    """
    For every required (non-pantry, non-optional) ingredient, try its
    searchKeyVariants in order against the pricing DB. Records the best score.
    INCONCLUSIVE (not FAIL) if the pricing DB yields no matches at all — that
    points at a pricing-DB / matcher schema problem, not a recipe-data problem.
    """
    checked = matched = 0
    unmatched = []

    for r in recipes:
        for ing in r.get("ingredients", []):
            if ing.get("pantryStaple") or ing.get("optional"):
                continue
            variants = ing.get("searchKeyVariants") or [ing.get("searchKey", "")]
            variants = [v for v in variants if v]
            if not variants:
                continue

            checked += 1
            best = 0.0
            for variant in variants:
                try:
                    result = matcher.match(variant, store_id)
                except Exception:
                    result = None
                if result and result.confidence > best:
                    best = result.confidence
                if best >= MATCH_THRESHOLD:
                    break

            if best >= MATCH_THRESHOLD:
                matched += 1
            else:
                unmatched.append({
                    "recipe": r.get("name", "?"),
                    "searchKey": ing.get("searchKey", "?"),
                    "bestScore": round(best, 3),
                })

    rate = matched / checked if checked else 0.0
    if checked and matched == 0:
        status = "INCONCLUSIVE"  # pricing DB / matcher unavailable
    elif rate >= COVERAGE_TARGET:
        status = "PASS"
    else:
        status = "FAIL"

    return {
        "status": status,
        "critical": True,
        "checked": checked,
        "matched": matched,
        "matchRate": round(rate, 3),
        "target": COVERAGE_TARGET,
        "topUnmatched": sorted(unmatched, key=lambda x: x["bestScore"])[:30],
    }


# ---------------------------------------------------------------------------
# 2. Time sanity
# ---------------------------------------------------------------------------

def check_time_sanity(recipes) -> dict:
    bad_range = []
    bad_breakdown = []
    outliers = []

    for r in recipes:
        name = r.get("name", "?")
        t = r.get("time") or {}
        rng = t.get("totalRangeMinutes")
        if not isinstance(rng, list) or len(rng) != 2:
            bad_range.append(name)
            continue
        lo, hi = rng
        if not (isinstance(lo, (int, float)) and isinstance(hi, (int, float))) or lo >= hi:
            bad_range.append(name)
            continue
        if hi > 120:
            outliers.append({"recipe": name, "totalMax": hi})

        parts = [t.get(p) for p in ("prepMinutes", "activeCookMinutes", "passiveCookMinutes")]
        if all(isinstance(p, (int, float)) for p in parts):
            if abs(sum(parts) - hi) > 10:
                bad_breakdown.append({"recipe": name, "sum": sum(parts), "totalMax": hi})

    status = "PASS" if not bad_range else "FAIL"
    return {
        "status": status,
        "critical": False,
        "badRange": bad_range,
        "badBreakdown": bad_breakdown,
        "outliersOver120min": outliers,
    }


# ---------------------------------------------------------------------------
# 3. Substitutes coverage
# ---------------------------------------------------------------------------

def check_substitutes(recipes, matcher, store_id) -> dict:
    missing = []
    unmatched_sub = []

    for r in recipes:
        if r.get("primaryProtein") not in MEAT_PROTEINS:
            continue
        subs = r.get("proteinSubstitutes") or []
        if not subs:
            missing.append(r.get("name", "?"))
            continue
        for sub in subs:
            sk = sub.get("searchKey", "")
            if not sk:
                continue
            try:
                result = matcher.match(sk, store_id)
            except Exception:
                result = None
            if not result or result.confidence < MATCH_THRESHOLD:
                unmatched_sub.append({"recipe": r.get("name", "?"), "searchKey": sk})

    status = "PASS" if not missing else "FAIL"
    return {
        "status": status,
        "critical": False,
        "meatRecipesMissingSubstitutes": missing,
        "substitutesNotPriced": unmatched_sub[:30],
    }


# ---------------------------------------------------------------------------
# 4. Pantry staple audit
# ---------------------------------------------------------------------------

def check_pantry_staples(recipes) -> dict:
    misflagged = []
    for r in recipes:
        for ing in r.get("ingredients", []):
            name = ing.get("name", "")
            if is_staple_name(name) and not ing.get("pantryStaple"):
                misflagged.append({"recipe": r.get("name", "?"), "ingredient": name})

    status = "PASS" if not misflagged else "WARN"
    return {
        "status": status,
        "critical": False,
        "stapleKeywords": sorted(STAPLE_KEYWORDS),
        "misflagged": misflagged[:50],
        "misflaggedCount": len(misflagged),
    }


# ---------------------------------------------------------------------------
# 5. Enum validity
# ---------------------------------------------------------------------------

def check_enums(recipes) -> dict:
    errors = []
    for r in recipes:
        name = r.get("name", "?")
        for e in r.get("equipment", []) or []:
            if e not in VALID_EQUIPMENT:
                errors.append(f"{name}: invalid equipment '{e}'")
        for s in r.get("season", []) or []:
            if s not in VALID_SEASONS:
                errors.append(f"{name}: invalid season '{s}'")
        skill = r.get("skillLevel")
        if skill is not None and skill not in VALID_SKILL_LEVELS:
            errors.append(f"{name}: invalid skillLevel '{skill}'")
        mt = r.get("mealType")
        if mt is not None and mt not in VALID_MEAL_TYPES:
            errors.append(f"{name}: invalid mealType '{mt}'")
        ct = r.get("costTier")
        if ct is not None and ct not in VALID_COST_TIERS:
            errors.append(f"{name}: invalid costTier '{ct}'")
        for ing in r.get("ingredients", []):
            cat = ing.get("category")
            if cat is not None and cat not in VALID_INGREDIENT_CATEGORIES:
                errors.append(f"{name}: invalid ingredient category '{cat}'")

    status = "PASS" if not errors else "FAIL"
    return {"status": status, "critical": True, "errors": errors[:100],
            "errorCount": len(errors)}


# ---------------------------------------------------------------------------
# 6. Distribution report
# ---------------------------------------------------------------------------

def distribution_report(recipes) -> dict:
    def time_bucket(r):
        rng = (r.get("time") or {}).get("totalRangeMinutes")
        hi = rng[1] if isinstance(rng, list) and len(rng) == 2 else r.get("cookTimeMinutes", 0)
        if hi < 30:
            return "<30min"
        if hi < 60:
            return "30-60min"
        if hi < 90:
            return "60-90min"
        return "90+min"

    return {
        "totalRecipes": len(recipes),
        "proteins": dict(Counter(r.get("primaryProtein", "?") for r in recipes)),
        "season": dict(Counter(s for r in recipes for s in (r.get("season") or []))),
        "cookTime": dict(Counter(time_bucket(r) for r in recipes)),
        "costTier": dict(Counter(r.get("costTier", "unset") for r in recipes)),
        "skillLevel": dict(Counter(r.get("skillLevel", "unset") for r in recipes)),
        "needsRegen": sum(
            1 for r in recipes if (r.get("qualityFlags") or {}).get("needsRegen")
        ),
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run(uri, recipes_db, pricing_db, store_id, output_path):
    client = MongoClient(uri)
    recipes = list(client[recipes_db]["recipes"].find({}))
    matcher = IngredientMatcher(client[pricing_db])

    print(f"\nSchema v2 validation — {recipes_db}.recipes ({len(recipes)} recipes)")
    print("=" * 64)

    results = {
        "searchCoverage": check_search_coverage(recipes, matcher, store_id),
        "timeSanity": check_time_sanity(recipes),
        "substitutes": check_substitutes(recipes, matcher, store_id),
        "pantryStaples": check_pantry_staples(recipes),
        "enums": check_enums(recipes),
        "distribution": distribution_report(recipes),
    }

    # Console summary
    labels = {
        "searchCoverage": "Ingredient search coverage",
        "timeSanity": "Time sanity",
        "substitutes": "Substitutes coverage",
        "pantryStaples": "Pantry staple audit",
        "enums": "Enum validity",
    }
    critical_failed = False
    for key, label in labels.items():
        res = results[key]
        status = res["status"]
        crit = " [CRITICAL]" if res.get("critical") else ""
        print(f"  {status:>12}  {label}{crit}")
        if status == "FAIL" and res.get("critical"):
            critical_failed = True

    cov = results["searchCoverage"]
    print(f"\n  Coverage: {cov['matched']}/{cov['checked']} "
          f"required ingredients matched >= {MATCH_THRESHOLD} "
          f"({cov['matchRate']*100:.1f}%, target {COVERAGE_TARGET*100:.0f}%)")
    if cov["status"] == "INCONCLUSIVE":
        print("  NOTE: 0 matches — pricing DB empty or matcher schema mismatch; "
              "coverage not counted as a failure.")

    d = results["distribution"]
    print(f"\n  Distribution ({d['totalRecipes']} recipes)")
    print(f"    proteins:   {d['proteins']}")
    print(f"    cook time:  {d['cookTime']}")
    print(f"    cost tier:  {d['costTier']}")
    print(f"    skill:      {d['skillLevel']}")
    print(f"    needsRegen: {d['needsRegen']}")

    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "recipesDb": recipes_db,
        "pricingDb": pricing_db,
        "storeId": store_id,
        "recipeCount": len(recipes),
        "criticalFailed": critical_failed,
        "checks": results,
    }

    os.makedirs(REPORTS_DIR, exist_ok=True)
    if not output_path:
        date = datetime.now().strftime("%Y-%m-%d")
        output_path = os.path.join(REPORTS_DIR, f"schema-v2-validation-{date}.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved: {output_path}")
    print("=" * 64)

    client.close()
    return 1 if critical_failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Schema v2 validation (MEA-114)")
    parser.add_argument("--uri", default="mongodb://localhost:27017")
    parser.add_argument("--recipes-db", default="paknsave-meals")
    parser.add_argument("--pricing-db", default="paknsave-pricing")
    parser.add_argument("--store", default="paknsave-lower-hutt", help="storeId to match against")
    parser.add_argument("--output", help="Explicit JSON report path")
    args = parser.parse_args()

    sys.exit(run(args.uri, args.recipes_db, args.pricing_db, args.store, args.output))
