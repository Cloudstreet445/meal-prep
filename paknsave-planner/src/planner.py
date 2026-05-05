"""Market data queries from Pak'nSave pricing database."""

from datetime import datetime, timedelta
from pymongo import MongoClient
from config import (
    MONGO_URI, MONGO_DB,
    PROTEIN_CATS, BEEF_MINCE_SPECIAL_ONLY,
    EXCLUDE_CATS, EXCLUDE_KEYS,
    MAX_PROTEIN_PRICE, MAX_VEG_PRICE, MAX_PANTRY_PRICE, MAX_DAIRY_PRICE,
    MAX_DATA_AGE_DAYS
)
from models import MarketData


def get_market_data() -> MarketData:
    """Query MongoDB for current prices, specials, and cheap staples."""
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    products = db["products"]

    cutoff = (datetime.now() - timedelta(days=MAX_DATA_AGE_DAYS)).strftime("%Y-%m-%d")

    def query(filter_dict, limit=20) -> list:
        results = []
        for p in products.find(filter_dict).sort("currentPrice", 1).limit(limit):
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
        "lastChecked": {"$gte": cutoff}
    }, limit=15)

    proteins_cheap = query({
        "category":     {"$in": ["chicken", "pork"]},
        "currentPrice": {"$lte": MAX_PROTEIN_PRICE},
        "lastChecked":  {"$gte": cutoff}
    }, limit=15)

    beef_mince = query({
        "category":    "mince-sausages",
        "isSpecial":   True,
        "lastChecked": {"$gte": cutoff},
        "$or": [
            {"name": {"$regex": "beef",  "$options": "i"}},
            {"name": {"$regex": "mince", "$options": "i"}}
        ]
    }, limit=5) if BEEF_MINCE_SPECIAL_ONLY else []

    veges_cheap = query({
        "category":     {"$in": ["fresh-vegetables", "fruit"]},
        "currentPrice": {"$lte": MAX_VEG_PRICE},
        "lastChecked":  {"$gte": cutoff}
    }, limit=20)

    veges_special = query({
        "category":    {"$in": ["fresh-vegetables"]},
        "isSpecial":   True,
        "lastChecked": {"$gte": cutoff}
    }, limit=10)

    pantry = query({
        "category":     {"$in": ["pasta", "noodles", "rice", "sauces",
                                  "beans-spaghetti", "oils-vinegars", "butter"]},
        "currentPrice": {"$lte": MAX_PANTRY_PRICE},
        "lastChecked":  {"$gte": cutoff}
    }, limit=20)

    dairy = query({
        "category":     {"$in": ["cream", "milk", "butter", "cheese"]},
        "currentPrice": {"$lte": MAX_DAIRY_PRICE},
        "lastChecked":  {"$gte": cutoff}
    }, limit=10)

    client.close()

    return MarketData(
        proteins_on_special=proteins_on_special,
        proteins_cheap=proteins_cheap,
        beef_mince_special=beef_mince,
        veges_cheap=veges_cheap,
        veges_special=veges_special,
        pantry=pantry,
        dairy=dairy,
    )
