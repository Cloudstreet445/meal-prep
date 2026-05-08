"""Market data queries from Pak'nSave pricing database."""

from datetime import datetime, timedelta
from config import (
    PROTEIN_CATS, BEEF_MINCE_SPECIAL_ONLY,
    EXCLUDE_CATS, EXCLUDE_KEYS,
    MAX_PROTEIN_PRICE, MAX_VEG_PRICE, MAX_PANTRY_PRICE, MAX_DAIRY_PRICE,
    MAX_DATA_AGE_DAYS
)
from models import MarketData
from db.mongodb import _client, MEALS_DB
import os

PRICING_DB = os.environ.get("PRICING_DB", "paknsave-pricing")
DEFAULT_STORE_ID = os.environ.get("STORE_ID", "paknsave-lower-hutt")


def get_market_data(store_id: str = DEFAULT_STORE_ID) -> MarketData:
    """Query MongoDB for current prices, specials, and cheap staples for a given store."""
    products = _client[PRICING_DB]["products"]

    cutoff = (datetime.now() - timedelta(days=MAX_DATA_AGE_DAYS)).strftime("%Y-%m-%d")
    sp = f"storePrice.{store_id}"

    def query(filter_dict, limit=20) -> list:
        results = []
        for p in products.find(filter_dict).sort(f"{sp}.currentPrice", 1).limit(limit):
            name = p.get("name", "")
            if any(kw in name.lower() for kw in EXCLUDE_KEYS):
                continue
            if p.get("category", "") in EXCLUDE_CATS:
                continue
            store_data = (p.get("storePrice") or {}).get(store_id, {})
            results.append({
                "name":        name,
                "size":        p.get("size", ""),
                "price":       round(store_data.get("currentPrice", 0), 2),
                "unitPrice":   store_data.get("unitPrice", ""),
                "category":    p.get("category", ""),
                "isSpecial":   store_data.get("isSpecial", False),
                "wasPrice":    round(store_data.get("maxPrice90d", 0), 2),
                "avgPrice90d": round(store_data.get("avgPrice90d", 0), 2),
                "lastChecked": store_data.get("lastChecked", ""),
            })
        return results

    proteins_on_special = query({
        "category":              {"$in": PROTEIN_CATS},
        f"{sp}.isSpecial":       True,
        f"{sp}.lastChecked":     {"$gte": cutoff}
    }, limit=15)

    proteins_cheap = query({
        "category":              {"$in": ["chicken", "pork"]},
        f"{sp}.currentPrice":    {"$lte": MAX_PROTEIN_PRICE},
        f"{sp}.lastChecked":     {"$gte": cutoff}
    }, limit=15)

    beef_mince = query({
        "category":              "mince-sausages",
        f"{sp}.isSpecial":       True,
        f"{sp}.lastChecked":     {"$gte": cutoff},
        "$or": [
            {"name": {"$regex": "beef",  "$options": "i"}},
            {"name": {"$regex": "mince", "$options": "i"}}
        ]
    }, limit=5) if BEEF_MINCE_SPECIAL_ONLY else []

    veges_cheap = query({
        "category":              {"$in": ["fresh-vegetables", "fruit"]},
        f"{sp}.currentPrice":    {"$lte": MAX_VEG_PRICE},
        f"{sp}.lastChecked":     {"$gte": cutoff}
    }, limit=20)

    veges_special = query({
        "category":              {"$in": ["fresh-vegetables"]},
        f"{sp}.isSpecial":       True,
        f"{sp}.lastChecked":     {"$gte": cutoff}
    }, limit=10)

    pantry = query({
        "category":              {"$in": ["pasta", "noodles", "rice", "sauces",
                                          "beans-spaghetti", "oils-vinegars", "butter"]},
        f"{sp}.currentPrice":    {"$lte": MAX_PANTRY_PRICE},
        f"{sp}.lastChecked":     {"$gte": cutoff}
    }, limit=20)

    dairy = query({
        "category":              {"$in": ["cream", "milk", "butter", "cheese"]},
        f"{sp}.currentPrice":    {"$lte": MAX_DAIRY_PRICE},
        f"{sp}.lastChecked":     {"$gte": cutoff}
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
