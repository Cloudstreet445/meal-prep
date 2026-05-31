"""MongoDB connections for meal-api."""

import logging
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI   = os.environ["MONGO_URI"]
MEALS_DB    = "paknsave-meals"
PRICING_DB  = "paknsave-pricing"

_client = MongoClient(MONGO_URI)
_log = logging.getLogger(__name__)


def _idx(collection, keys, **kwargs):
    """Create a single index, logging a warning on failure instead of crashing."""
    try:
        collection.create_index(keys, **kwargs)
    except Exception as exc:
        _log.warning("Could not create index %r on %s: %s", keys, collection.name, exc)


def _ensure_indexes():
    db = _client[MEALS_DB]
    _idx(db["recipes"], "recipeId", unique=True)
    _idx(db["recipes"], "usageHistory")
    _idx(db["recipes"], "bundleHistory")
    _idx(db["bundles"], "bundleId", unique=True)
    _idx(db["bundles"], [("week", 1), ("active", 1)])
    _idx(db["bundles"], [("active", 1), ("week", -1), ("createdAt", -1)])
    _idx(db["bundles"], [("week", -1), ("createdAt", -1)])
    # Bundles are queried per household (active plan, history, week, by-id)
    _idx(db["bundles"], [("householdId", 1), ("active", 1), ("week", -1), ("createdAt", -1)])
    _idx(db["settings"], "key", sparse=True)
    _idx(db["settings"], "userId", sparse=True, unique=True)
    _idx(db["users"], "userId", unique=True)
    _idx(db["users"], "email", unique=True)
    _idx(db["magic_tokens"], "token", unique=True)
    _idx(db["magic_tokens"], "expiresAt", expireAfterSeconds=0)
    _idx(db["household_invites"], "token", unique=True)
    _idx(db["household_invites"], "expiresAt", expireAfterSeconds=0)
    _idx(db["households"], "householdId", unique=True)
    _idx(db["user_pantry"], [("userId", 1), ("canonical", 1)], unique=True)
    _idx(db["enhancements"], "enhancementId", unique=True)
    _idx(db["enhancements"], "tags")
    _idx(db["sessions"], "sessionId", unique=True)
    _idx(db["sessions"], "userId")
    _idx(db["sessions"], "expiresAt", expireAfterSeconds=0)
    _idx(db["password_reset_tokens"], "token", unique=True)
    _idx(db["password_reset_tokens"], "expiresAt", expireAfterSeconds=0)
    pricing_db = _client[PRICING_DB]
    _idx(pricing_db["products"], "category")

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