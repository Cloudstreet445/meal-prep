"""Market data queries from Pak'nSave pricing database."""

from datetime import datetime, timedelta
from config import (
    PROTEIN_CATS, BEEF_MINCE_SPECIAL_ONLY,
    EXCLUDE_CATS, EXCLUDE_KEYS,
    MAX_PROTEIN_PRICE, MAX_VEG_PRICE, MAX_PANTRY_PRICE, MAX_DAIRY_PRICE,
    MAX_DATA_AGE_DAYS, STORE_NAME_MAP
)
from models import MarketData
from db.mongodb import _client, MEALS_DB
import os

PRICING_DB = os.environ.get("PRICING_DB", "paknsave-pricing")
DEFAULT_STORE_ID = os.environ.get("STORE_ID", "paknsave-lower-hutt")


def get_market_data(store_id: str = DEFAULT_STORE_ID) -> MarketData:
    """Query MongoDB for current prices, specials, and cheap staples for a given store.

    The pricing DB uses a flat schema: currentPrice, isSpecial, lastChecked, avgPrice90d
    are top-level fields. storeId is the full store name (e.g. "PAK'nSAVE Lower Hutt").
    STORE_NAME_MAP maps slug IDs to full names for filtering.
    """
    products = _client[PRICING_DB]["products"]

    cutoff = (datetime.now() - timedelta(days=MAX_DATA_AGE_DAYS)).strftime("%Y-%m-%d")

    # Build optional storeId filter — if slug not in map, query all stores
    store_name = STORE_NAME_MAP.get(store_id)
    store_filter = {"storeId": store_name} if store_name else {}

    def query(filter_dict, limit=20) -> list:
        combined = {**store_filter, **filter_dict}
        results = []
        for p in products.find(combined).sort("currentPrice", 1).limit(limit):
            name = p.get("name", "")
            if any(kw in name.lower() for kw in EXCLUDE_KEYS):
                continue
            if p.get("category", "") in EXCLUDE_CATS:
                continue
            results.append({
                "name":        name,
                "size":        p.get("size", ""),
                "price":       round(p.get("currentPrice", 0), 2),
                "unitPrice":   p.get("unitPrice", ""),
                "category":    p.get("category", ""),
                "isSpecial":   p.get("isSpecial", False),
                "wasPrice":    round(p.get("maxPrice90d", 0), 2),
                "avgPrice90d": round(p.get("avgPrice90d", 0), 2),
                "lastChecked": p.get("lastChecked", ""),
            })
        return results

    proteins_on_special = query({
        "category":    {"$in": PROTEIN_CATS},
        "isSpecial":   True,
        "lastChecked": {"$gte": cutoff},
    }, limit=15)

    proteins_cheap = query({
        "category":     {"$in": ["chicken", "pork"]},
        "currentPrice": {"$lte": MAX_PROTEIN_PRICE},
        "lastChecked":  {"$gte": cutoff},
    }, limit=15)

    beef_mince = query({
        "category":    {"$in": ["beef-lamb", "mince-sausages", "sausages"]},
        "isSpecial":   True,
        "lastChecked": {"$gte": cutoff},
        "$or": [
            {"name": {"$regex": "beef",  "$options": "i"}},
            {"name": {"$regex": "mince", "$options": "i"}},
        ],
    }, limit=5) if BEEF_MINCE_SPECIAL_ONLY else []

    veges_cheap = query({
        "category":     {"$in": ["fresh-vegetables", "fruit"]},
        "currentPrice": {"$lte": MAX_VEG_PRICE},
        "lastChecked":  {"$gte": cutoff},
    }, limit=20)

    veges_special = query({
        "category":    {"$in": ["fresh-vegetables"]},
        "isSpecial":   True,
        "lastChecked": {"$gte": cutoff},
    }, limit=10)

    pantry = query({
        "category":     {"$in": ["pasta", "noodles", "rice", "sauces",
                                  "beans-spaghetti", "oils-vinegars", "butter"]},
        "currentPrice": {"$lte": MAX_PANTRY_PRICE},
        "lastChecked":  {"$gte": cutoff},
    }, limit=20)

    dairy = query({
        "category":     {"$in": ["cream", "milk", "butter", "cheese"]},
        "currentPrice": {"$lte": MAX_DAIRY_PRICE},
        "lastChecked":  {"$gte": cutoff},
    }, limit=10)

    return MarketData(
        proteins_on_special=proteins_on_special,
        proteins_cheap=proteins_cheap,
        beef_mince_special=beef_mince,
        veges_cheap=veges_cheap,
        veges_special=veges_special,
        pantry=pantry,
        dairy=dairy,
    )
