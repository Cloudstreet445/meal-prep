"""MongoDB connections for meal-api."""

import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI   = os.environ["MONGO_URI"]
MEALS_DB    = "paknsave-meals"
PRICING_DB  = "paknsave-pricing"


def get_db():
    """Return paknsave-meals database."""
    return MongoClient(MONGO_URI)[MEALS_DB]


def get_pricing_db():
    """Return paknsave-pricing database (for live price enrichment)."""
    return MongoClient(MONGO_URI)[PRICING_DB]


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