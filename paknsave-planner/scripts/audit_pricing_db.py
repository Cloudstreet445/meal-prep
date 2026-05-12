#!/usr/bin/env python3
"""Audit the paknsave-pricing database.

Produces a structured report of:
  - Categories present and product count per category
  - Sample product names per key category (name patterns for prompt writing)
  - Common ingredient keyword checks (coverage gaps)
  - Price range summary per key protein/veg category

Usage (from paknsave-planner/):
    python scripts/audit_pricing_db.py [--store paknsave-lower-hutt]
    python scripts/audit_pricing_db.py --json   # machine-readable output
"""

import sys
import os
import json
import re
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", ".env"))

from pymongo import MongoClient

MONGO_URI  = os.environ["MONGO_URI"]
PRICING_DB = os.environ.get("PRICING_DB", "paknsave-pricing")
STORE_ID   = next((a.split("--store")[1].strip() for a in sys.argv if "--store" in a), None) or \
             next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == "--store" and i+1 < len(sys.argv)), "paknsave-lower-hutt")
JSON_MODE  = "--json" in sys.argv

client   = MongoClient(MONGO_URI)
products = client[PRICING_DB]["products"]

_STORE_NAME_MAP = {
    "paknsave-lower-hutt": "PAK'nSAVE Lower Hutt",
    "paknsave-porirua":    "PAK'nSAVE Porirua",
    "paknsave-petone":     "PAK'nSAVE Petone",
    "paknsave-kilbirnie":  "PAK'nSAVE Kilbirnie",
}
STORE_NAME   = _STORE_NAME_MAP.get(STORE_ID)
STORE_FILTER = {"storeId": STORE_NAME} if STORE_NAME else {}

# ── 1. Category counts ────────────────────────────────────────────

cat_counts = list(products.aggregate([
    {"$match": STORE_FILTER},
    {"$group": {"_id": "$category", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
]))

# ── 2. Sample names per key category ─────────────────────────────

KEY_CATS = [
    "chicken", "pork", "beef-lamb", "mince-sausages",
    "fresh-vegetables", "fruit",
    "pasta", "noodles", "rice",
    "sauces", "oils-vinegars", "butter",
    "cream", "milk", "cheese",
    "canned-tomatoes", "beans-spaghetti",
    "frozen-vegetables", "eggs",
]

samples = {}
for cat in KEY_CATS:
    docs = list(products.find({**STORE_FILTER, "category": cat}).limit(25))
    samples[cat] = [d.get("name", "") for d in docs]

# ── 3. Coverage checks — common ingredient keywords ───────────────

INGREDIENT_CHECKS = [
    # Proteins
    ("chicken breast",    re.compile(r"chicken breast", re.I)),
    ("chicken thigh",     re.compile(r"chicken thigh", re.I)),
    ("chicken drumstick", re.compile(r"chicken drumstick|drumstick", re.I)),
    ("chicken whole",     re.compile(r"whole chicken|roast chicken", re.I)),
    ("pork mince",        re.compile(r"pork mince", re.I)),
    ("pork shoulder",     re.compile(r"pork shoulder|pork roast", re.I)),
    ("beef mince",        re.compile(r"beef mince|mince beef", re.I)),
    ("lamb shoulder",     re.compile(r"lamb shoulder|lamb roast", re.I)),
    ("lamb mince",        re.compile(r"lamb mince", re.I)),
    ("sausages",          re.compile(r"sausage", re.I)),
    # Veg
    ("onion",             re.compile(r"\bonion\b", re.I)),
    ("garlic",            re.compile(r"garlic", re.I)),
    ("potato",            re.compile(r"potato", re.I)),
    ("carrot",            re.compile(r"carrot", re.I)),
    ("broccoli",          re.compile(r"broccoli", re.I)),
    ("capsicum",          re.compile(r"capsicum|bell pepper", re.I)),
    ("courgette",         re.compile(r"courgette|zucchini", re.I)),
    ("cabbage",           re.compile(r"cabbage", re.I)),
    ("pumpkin",           re.compile(r"pumpkin|butternut", re.I)),
    ("celery",            re.compile(r"celery", re.I)),
    ("leek",              re.compile(r"leek", re.I)),
    ("spinach",           re.compile(r"spinach", re.I)),
    ("tomato",            re.compile(r"\btomato\b", re.I)),
    # Pantry
    ("pasta",             re.compile(r"\bpasta\b|spaghetti|penne|fettuccine|rigatoni", re.I)),
    ("rice",              re.compile(r"\brice\b", re.I)),
    ("noodles",           re.compile(r"\bnoodle", re.I)),
    ("canned tomatoes",   re.compile(r"canned tomato|crushed tomato|diced tomato", re.I)),
    ("canned beans",      re.compile(r"chickpea|kidney bean|black bean|baked bean", re.I)),
    ("coconut milk",      re.compile(r"coconut milk|coconut cream", re.I)),
    ("soy sauce",         re.compile(r"soy sauce", re.I)),
    ("olive oil",         re.compile(r"olive oil", re.I)),
    ("stock cube",        re.compile(r"stock|bouillon", re.I)),
    # Dairy
    ("butter",            re.compile(r"\bbutter\b", re.I)),
    ("milk",              re.compile(r"\bmilk\b", re.I)),
    ("cream",             re.compile(r"\bcream\b", re.I)),
    ("cheese",            re.compile(r"\bcheese\b", re.I)),
    ("eggs",              re.compile(r"\begg", re.I)),
]

coverage = {}
for label, pat in INGREDIENT_CHECKS:
    matches = list(products.find({**STORE_FILTER, "name": {"$regex": pat.pattern, "$options": "i"}}).limit(5))
    coverage[label] = {
        "count": len(matches),
        "examples": [m.get("name") for m in matches]
    }

# ── 4. Price ranges per protein category ─────────────────────────

price_summary = {}
for cat in ["chicken", "pork", "beef-lamb", "mince-sausages", "sausages"]:
    pipeline = [
        {"$match": {**STORE_FILTER, "category": cat, "currentPrice": {"$exists": True}}},
        {"$group": {
            "_id": None,
            "count":    {"$sum": 1},
            "minPrice": {"$min": "$currentPrice"},
            "maxPrice": {"$max": "$currentPrice"},
            "avgPrice": {"$avg": "$currentPrice"},
        }}
    ]
    result = list(products.aggregate(pipeline))
    if result:
        r = result[0]
        price_summary[cat] = {
            "count":    r["count"],
            "minPrice": round(r["minPrice"], 2),
            "maxPrice": round(r["maxPrice"], 2),
            "avgPrice": round(r["avgPrice"], 2),
        }


# ── Output ────────────────────────────────────────────────────────

if JSON_MODE:
    print(json.dumps({
        "store":          STORE_ID,
        "categorycounts": {c["_id"]: c["count"] for c in cat_counts},
        "samples":        samples,
        "coverage":       coverage,
        "priceRanges":    price_summary,
    }, indent=2))
    sys.exit(0)

print(f"\n{'='*60}")
print(f"  PAK'nSAVE PRICING DB AUDIT — {STORE_ID}")
print(f"{'='*60}")

print(f"\n── Categories ({len(cat_counts)} total) ──────────────────────────")
for c in cat_counts:
    bar = "█" * min(int(c["count"] / 5), 40)
    print(f"  {c['_id'] or '(none)':<30}  {c['count']:>4}  {bar}")

print(f"\n── Sample product names per category ────────────────────────")
for cat in KEY_CATS:
    names = samples.get(cat, [])
    if not names:
        print(f"\n  [{cat}]  ⚠️  NO PRODUCTS FOUND")
        continue
    print(f"\n  [{cat}]  ({len(names)} shown)")
    for n in names[:10]:
        print(f"    · {n}")

print(f"\n── Ingredient coverage checks ────────────────────────────────")
missing = []
for label, data in coverage.items():
    status = "✓" if data["count"] > 0 else "✗ MISSING"
    examples = ", ".join(data["examples"][:2]) if data["examples"] else "—"
    print(f"  {status:<10}  {label:<22}  ({data['count']} matches)  e.g. {examples}")
    if data["count"] == 0:
        missing.append(label)

if missing:
    print(f"\n  ⚠️  Missing ingredients: {', '.join(missing)}")
else:
    print(f"\n  ✓ All common ingredients have at least one matching product")

print(f"\n── Protein price ranges ({STORE_ID}) ─────────────────────────")
for cat, s in price_summary.items():
    print(f"  {cat:<22}  count={s['count']:>3}  "
          f"${s['minPrice']:.2f}–${s['maxPrice']:.2f}  avg=${s['avgPrice']:.2f}")

print(f"\n{'='*60}\n")
