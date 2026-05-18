"""Market data queries from Pak'nSave pricing database."""

from datetime import datetime, timedelta
from config import (
    PROTEIN_CATS, BEEF_MINCE_SPECIAL_ONLY,
    EXCLUDE_CATS, EXCLUDE_KEYS,
    MAX_PROTEIN_PRICE, MAX_VEG_PRICE, MAX_PANTRY_PRICE, MAX_DAIRY_PRICE,
    MAX_DATA_AGE_DAYS
)
from models import MarketData
from db.mongodb import _client
import os

PRICING_DB = os.environ.get("PRICING_DB", "paknsave-pricing")
DEFAULT_STORE_ID = os.environ.get("STORE_ID", "paknsave-lower-hutt")

# Price fields that live inside the per-store storePrice.{slug} sub-document.
# Filters on these keys are rewritten to their nested path; everything else
# (category, name, $or, ...) stays top-level.
_STORE_FIELDS = {"currentPrice", "isSpecial", "lastChecked"}


def get_market_data(store_id: str = DEFAULT_STORE_ID) -> MarketData:
    """Query MongoDB for current prices, specials, and cheap staples for a given store.

    The pricing DB uses the nested schema: each product carries a
    storePrice.{storeSlug} map, and currentPrice/isSpecial/lastChecked/
    avgPrice90d etc. live inside that per-store entry. store_id is the slug
    used as the map key (e.g. "paknsave-lower-hutt").
    """
    products = _client[PRICING_DB]["products"]

    cutoff = (datetime.now() - timedelta(days=MAX_DATA_AGE_DAYS)).strftime("%Y-%m-%d")
    price_prefix = f"storePrice.{store_id}"

    def query(filter_dict, limit=20) -> list:
        # Rewrite per-store field filters to their nested path.
        translated = {}
        for key, val in filter_dict.items():
            if key in _STORE_FIELDS:
                translated[f"{price_prefix}.{key}"] = val
            else:
                translated[key] = val
        combined = {price_prefix: {"$exists": True}, **translated}

        results = []
        for p in products.find(combined).sort(f"{price_prefix}.currentPrice", 1).limit(limit):
            name = p.get("name", "")
            if any(kw in name.lower() for kw in EXCLUDE_KEYS):
                continue
            if p.get("category", "") in EXCLUDE_CATS:
                continue
            sp = p.get("storePrice", {}).get(store_id, {})
            results.append({
                "name":        name,
                "size":        p.get("size", ""),
                "price":       round(sp.get("currentPrice", 0), 2),
                "unitPrice":   sp.get("unitPrice", ""),
                "category":    p.get("category", ""),
                "isSpecial":   sp.get("isSpecial", False),
                "wasPrice":    round(sp.get("maxPrice90d", 0), 2),
                "avgPrice90d": round(sp.get("avgPrice90d", 0), 2),
                "lastChecked": sp.get("lastChecked", ""),
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
