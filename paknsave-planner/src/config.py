"""Central configuration for Pak'nSave meal planner."""

import os
from dotenv import load_dotenv

load_dotenv()

# ── MongoDB ───────────────────────────────────────────────────────
MONGO_URI    = os.environ.get("MONGO_URI")
MONGO_DB     = os.environ.get("MONGO_DB")
MEALS_DB     = "paknsave-meals"

# ── Anthropic ─────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS = 8000

# ── Planner preferences ───────────────────────────────────────────
BUDGET       = float(os.environ.get("BUDGET", 60.00))
SERVES       = int(os.environ.get("SERVES", 2))
LEFTOVERS    = True

# ── Protein config ────────────────────────────────────────────────
PROTEIN_CATS          = ["chicken", "pork", "beef-lamb", "mince-sausages"]
BEEF_MINCE_SPECIAL_ONLY = True

# ── Exclusions ────────────────────────────────────────────────────
EXCLUDE_CATS = ["seafood", "canned-fish", "frozen-seafood"]
EXCLUDE_KEYS = ["mushroom", "seafood", "fish", "prawn", "shrimp", "salmon", "tuna"]

# ── Price thresholds ──────────────────────────────────────────────
MAX_PROTEIN_PRICE = 15.00
MAX_VEG_PRICE     = 5.00
MAX_PANTRY_PRICE  = 6.00
MAX_DAIRY_PRICE   = 8.00

# ── Scraper freshness ─────────────────────────────────────────────
MAX_DATA_AGE_DAYS = 5   # ignore products not checked within this many days

# ── Paths ─────────────────────────────────────────────────────────
RESPONSE_JSON = "response.json"
