"""MongoDB operations for storing meal plans and recipes."""

import os
import re
import hashlib
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from dotenv import load_dotenv
from config import MEALS_DB

# Resolve .env relative to this file (src/.env) so the planner runs from any CWD.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

MONGO_URI = os.environ["MONGO_URI"]

_client = MongoClient(MONGO_URI)


def _ensure_indexes():
    try:
        db = _client[MEALS_DB]
        db["recipes"].create_index("recipeId", unique=True)
        db["recipes"].create_index("usageHistory")
        db["recipes"].create_index("bundleHistory")
        db["recipes"].create_index("primaryProtein")
        db["recipes"].create_index("tags")
        db["recipes"].create_index("season")
        db["recipes"].create_index("cookTimeMinutes")
        db["recipes"].create_index("lastUsedWeek")
        db["recipes"].create_index([
            ("primaryProtein", 1), ("cookTimeMinutes", 1), ("lastUsedWeek", 1)
        ])
        db["bundles"].create_index("bundleId", unique=True)
        db["bundles"].create_index([("week", 1), ("active", 1)])
        db["bundles"].create_index([("active", 1), ("week", -1), ("createdAt", -1)])
        db["bundles"].create_index([("week", -1), ("createdAt", -1)])
        pricing_db = _client[os.environ.get("PRICING_DB", "paknsave-pricing")]
        pricing_db["products"].create_index("category")
        pricing_db["products"].create_index([("name", "text")])
        pricing_db["products"].create_index([("category", 1)])
    except Exception:
        pass

_ensure_indexes()


def clean(doc: dict) -> dict:
    """Convert MongoDB document to JSON-safe format."""
    if doc is None:
        return {}
    doc["_id"] = str(doc["_id"])
    for key, val in doc.items():
        if hasattr(val, "isoformat"):
            doc[key] = val.isoformat()
    return doc


def clean_list(docs: list) -> list:
    return [clean(doc) for doc in docs]


# ── ID generators ─────────────────────────────────────────────────

def generate_recipe_id(meal: dict) -> str:
    """Deterministic slug-hash ID from meal name."""
    slug = re.sub(r'[^a-z0-9]+', '-', meal["name"].lower()).strip('-')
    short_hash = hashlib.md5(meal["name"].encode()).hexdigest()[:6]
    return f"{slug}-{short_hash}"


def generate_bundle_id(week_summary: str, week_id: str) -> str:
    """Deterministic slug-hash ID from summary + week. Same plan = same ID = safe upsert."""
    combined = f"{week_summary}-{week_id}"
    slug = re.sub(r'[^a-z0-9]+', '-', week_summary.lower()).strip('-')[:40]
    short_hash = hashlib.md5(combined.encode()).hexdigest()[:6]
    return f"{slug}-{short_hash}"


# ── Recipes ───────────────────────────────────────────────────────

def store_recipes(plan: dict, week_id: str = None) -> tuple[int, list[str]]:
    """
    Upsert recipes from a generated plan.

    - Ingredients are stored WITHOUT sharedWith (computed dynamically by API)
    - Uses recipeId slug-hash as the stable identifier
    - Tracks usageHistory and bundleHistory

    Returns (count_upserted, list_of_recipe_ids)
    """
    if week_id is None:
        week_id = datetime.now().strftime("%Y-%m-%d")

    recipes = _client[MEALS_DB]["recipes"]
    count = 0
    recipe_ids = []

    _PRICE_FIELDS = {"estimatedCost", "fromSpecial", "sharedWith"}

    for meal in plan.get("meals", []):
        recipe_id = generate_recipe_id(meal)
        recipe_ids.append(recipe_id)

        # Strip price/relationship fields — these never belong on the recipe itself
        ingredients = [
            {k: v for k, v in ing.items() if k not in _PRICE_FIELDS}
            for ing in meal.get("ingredients", [])
        ]

        result = recipes.update_one(
            {"recipeId": recipe_id},
            {
                "$set": {
                    "recipeId":        recipe_id,
                    "name":            meal.get("name"),
                    "serves":          meal.get("serves"),
                    "leftovers":       meal.get("leftovers", False),
                    "cookTime":        meal.get("cookTime"),
                    "cookTimeMinutes": meal.get("cookTimeMinutes", 0),
                    "description":     meal.get("description"),
                    "recipeUrl":       meal.get("recipeUrl"),
                    "ingredients":     ingredients,
                    "method":          meal.get("method", []),
                    "primaryProtein":  meal.get("primaryProtein", ""),
                    "tags":            meal.get("tags", []),
                    "season":          meal.get("season", ["all"]),
                    "dietaryFlags":    meal.get("dietaryFlags", []),
                    "baselineCost":    meal.get("baselineCost", 0.0),
                    "source":          "claude",
                    "lastUsedWeek":    week_id,
                    "updatedAt":       datetime.now(),
                },
                "$addToSet": {
                    "usageHistory": week_id
                },
                "$setOnInsert": {
                    "createdAt":    datetime.now(),
                    "bundleHistory": []
                }
            },
            upsert=True
        )

        if result.upserted_id or result.modified_count > 0:
            count += 1

    return count, recipe_ids


# ── Bundles ───────────────────────────────────────────────────────

def store_bundle(plan: dict, week_id: str, recipe_ids: list[str]) -> str:
    """
    Upsert a bundle for the given week.

    Active flag is scoped PER WEEK — only deactivates other bundles
    for the same week, not across all weeks.

    Returns bundleId.
    """
    db = _client[MEALS_DB]

    bundle_id = generate_bundle_id(
        plan.get("weekSummary", "meal-plan"),
        week_id
    )

    # Deactivate other bundles for THIS WEEK ONLY
    db["bundles"].update_many(
        {"week": week_id, "bundleId": {"$ne": bundle_id}},
        {"$set": {"active": False}}
    )

    # Upsert this bundle as active
    db["bundles"].update_one(
        {"bundleId": bundle_id},
        {
            "$set": {
                "bundleId":          bundle_id,
                "week":              week_id,
                "active":            True,
                "weekSummary":       plan.get("weekSummary"),
                "estimatedTotal":    plan.get("estimatedTotal", 0),
                "recipeIds":         recipe_ids,
                "priceSnapshotDate": datetime.now().strftime("%Y-%m-%d"),
                "generatedBy":       "claude",
                "updatedAt":         datetime.now(),
            },
            "$setOnInsert": {
                "createdAt": datetime.now()
            }
        },
        upsert=True
    )

    # Add this bundleId to each recipe's bundleHistory
    db["recipes"].update_many(
        {"recipeId": {"$in": recipe_ids}},
        {"$addToSet": {"bundleHistory": bundle_id}}
    )

    return bundle_id


def get_settings() -> dict:
    """Read household settings from DB, falling back to config defaults."""
    from config import BUDGET, SERVES, EXCLUDE_KEYS
    try:
        doc = _client[MEALS_DB]["settings"].find_one({"key": "default"})
        if doc:
            return {
                "budget":     float(doc.get("budget", BUDGET)),
                "serves":     int(doc.get("serves", SERVES)),
                "exclusions": list(doc.get("exclusions", EXCLUDE_KEYS)),
            }
    except Exception:
        pass
    return {"budget": BUDGET, "serves": SERVES, "exclusions": list(EXCLUDE_KEYS)}


def get_latest_active_bundle() -> dict:
    """Get the active bundle for the most recent week."""
    latest_week = _client[MEALS_DB]["bundles"].find_one(
        {"active": True},
        sort=[("week", -1)]
    )
    return clean(latest_week) if latest_week else {}


def get_active_bundle_for_week(week_id: str) -> dict:
    """Get the active bundle for a specific week."""
    doc = _client[MEALS_DB]["bundles"].find_one(
        {"week": week_id, "active": True},
        sort=[("createdAt", -1)]
    )
    return clean(doc) if doc else {}


def get_bundle_by_id(bundle_id: str) -> dict:
    """Get a specific bundle by bundleId."""
    doc = _client[MEALS_DB]["bundles"].find_one({"bundleId": bundle_id})
    return clean(doc) if doc else {}


def list_bundles_for_week(week_id: str) -> list:
    """All bundles for a specific week, newest first."""
    docs = list(_client[MEALS_DB]["bundles"].find(
        {"week": week_id},
        {"bundleId": 1, "weekSummary": 1, "estimatedTotal": 1,
         "createdAt": 1, "active": 1, "recipeIds": 1}
    ).sort("createdAt", -1))
    return clean_list(docs)


def list_all_weeks() -> list:
    """
    List all weeks that have bundles, with their active bundle summary.
    Returns one entry per week (the active bundle for that week).
    """
    pipeline = [
        {"$sort": {"week": -1, "createdAt": -1}},
        {"$group": {
            "_id": "$week",
            "week":          {"$first": "$week"},
            "bundleId":      {"$first": "$bundleId"},
            "weekSummary":   {"$first": {"$cond": [{"$eq": ["$active", True]}, "$weekSummary", None]}},
            "estimatedTotal":{"$first": {"$cond": [{"$eq": ["$active", True]}, "$estimatedTotal", None]}},
            "bundleCount":   {"$sum": 1},
            "active":        {"$first": "$active"},
        }},
        {"$sort": {"week": -1}}
    ]
    docs = list(_client[MEALS_DB]["bundles"].aggregate(pipeline))
    return [
        {
            "week":           d["_id"],
            "bundleId":       d.get("bundleId"),
            "weekSummary":    d.get("weekSummary"),
            "estimatedTotal": d.get("estimatedTotal"),
            "bundleCount":    d.get("bundleCount", 1),
        }
        for d in docs
    ]


def activate_bundle(bundle_id: str) -> bool:
    """
    Set a specific bundle as active for its week.
    Deactivates other bundles for SAME WEEK ONLY.
    """
    db = _client[MEALS_DB]

    bundle = db["bundles"].find_one({"bundleId": bundle_id})
    if not bundle:
        return False

    week_id = bundle["week"]

    # Deactivate all bundles for this week
    db["bundles"].update_many(
        {"week": week_id},
        {"$set": {"active": False}}
    )

    # Activate chosen bundle
    result = db["bundles"].update_one(
        {"bundleId": bundle_id},
        {"$set": {"active": True, "updatedAt": datetime.now()}}
    )

    return result.modified_count > 0


# ── Recipes ───────────────────────────────────────────────────────

def get_recipes(usage_week: str = None, bundle_id: str = None) -> list:
    """Retrieve recipes, optionally filtered by week or bundle."""
    filter_dict = {}
    if usage_week:
        filter_dict["usageHistory"] = usage_week
    if bundle_id:
        filter_dict["bundleHistory"] = bundle_id
    results = list(_client[MEALS_DB]["recipes"].find(filter_dict).sort("name", 1))
    return clean_list(results)


def get_recipe_by_id(recipe_id: str) -> dict:
    """Retrieve a specific recipe by recipeId."""
    result = _client[MEALS_DB]["recipes"].find_one({"recipeId": recipe_id})
    return clean(result) if result else {}


def get_recipes_by_ids(recipe_ids: list[str]) -> list:
    """Retrieve multiple recipes by their recipeIds, preserving order."""
    docs = list(_client[MEALS_DB]["recipes"].find(
        {"recipeId": {"$in": recipe_ids}}
    ))
    # Preserve the order of recipe_ids
    recipe_map = {d["recipeId"]: clean(d) for d in docs}
    return [recipe_map[rid] for rid in recipe_ids if rid in recipe_map]
