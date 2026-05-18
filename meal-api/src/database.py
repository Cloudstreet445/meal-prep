"""MongoDB connections for meal-api."""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI   = os.environ["MONGO_URI"]
MEALS_DB    = "paknsave-meals"
PRICING_DB  = "paknsave-pricing"

_client = MongoClient(MONGO_URI)


def _ensure_indexes():
    try:
        db = _client[MEALS_DB]
        db["recipes"].create_index("recipeId", unique=True)
        db["recipes"].create_index("usageHistory")
        db["recipes"].create_index("bundleHistory")
        db["bundles"].create_index("bundleId", unique=True)
        db["bundles"].create_index([("week", 1), ("active", 1)])
        # ESR index for find_one({"active": True}, sort=[("week", -1), ("createdAt", -1)])
        db["bundles"].create_index([("active", 1), ("week", -1), ("createdAt", -1)])
        # Index to support aggregation pipeline initial sort
        db["bundles"].create_index([("week", -1), ("createdAt", -1)])
        db["settings"].create_index("key", sparse=True)
        db["settings"].create_index("userId", sparse=True, unique=True)
        db["users"].create_index("userId", unique=True)
        db["users"].create_index("email", unique=True)
        db["magic_tokens"].create_index("token", unique=True)
        db["magic_tokens"].create_index("expiresAt", expireAfterSeconds=0)
        db["household_invites"].create_index("token", unique=True)
        db["household_invites"].create_index("expiresAt", expireAfterSeconds=0)
        db["households"].create_index("householdId", unique=True)
        db["user_pantry"].create_index([("userId", 1), ("canonical", 1)], unique=True)
        db["enhancements"].create_index("enhancementId", unique=True)
        db["enhancements"].create_index("tags")
        pricing_db = _client[PRICING_DB]
        pricing_db["products"].create_index("category")
    except Exception:
        pass

_ensure_indexes()


def get_db():
    """Return paknsave-meals database."""
    return _client[MEALS_DB]


def get_pricing_db():
    """Return paknsave-pricing database (for live price enrichment)."""
    return _client[PRICING_DB]


def clean(doc: dict) -> dict:
    if not doc:
        return {}
    doc["_id"] = str(doc["_id"])
    for key, val in doc.items():
        if hasattr(val, "isoformat"):
            doc[key] = val.isoformat()
    return doc


def clean_list(docs: list) -> list:
    return [clean(doc) for doc in docs]