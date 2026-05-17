"""
Product name tokeniser (MEA-111).

Produces the normalised `searchTokens` array stored on every product document
in `paknsave-pricing.products`. Precomputing tokens at scrape time means the
fuzzy ingredient matcher does no heavy normalisation per plan generation.

IMPORTANT: the C# scraper (pakn-scraper/src/Utilities.cs GenerateSearchTokens)
MUST produce byte-identical output to tokenise() here. The stop-word list
below is the contract — if you change it, change both sides and re-run the
searchTokens backfill (pricing_enhance.py).
"""

import re

# Brand names, NZ qualifiers, product descriptors, and bare unit words that
# add no discriminating value to an ingredient search.
TOKEN_STOP_WORDS = {
    # Brands
    "pams", "anchor", "meadow", "fresh", "dairyworks", "hellers",
    "wattie", "watties", "homebrand", "san", "remo", "mainland", "value",
    "tegel", "countdown", "essentials", "budget",
    # NZ / origin qualifiers
    "nz", "new", "zealand", "imported",
    # Product descriptors
    "pack", "free", "range", "boneless", "skinless", "brushed",
    "organic", "trim", "lean", "premium", "classic", "select",
    "large", "medium", "small", "extra", "family", "bulk",
    # Bare unit words (numbers are stripped entirely)
    "kg", "g", "ml", "l", "pk", "ea", "each",
}


def tokenise(name: str) -> list:
    """
    Normalise a product name into a deduplicated, order-preserving token list.

      "Pams Fresh NZ Chicken Drumsticks 1kg" -> ["chicken", "drumsticks"]
      "Anchor Butter 500g"                   -> ["butter"]
      "Wattie's Tomato Paste"                -> ["tomato", "paste"]

    A token is dropped if it is a stop word, a single character, or starts
    with a digit (size tokens like "1kg", "500g", "400ml").
    """
    if not name:
        return []
    lowered = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    tokens = []
    for t in lowered.split():
        if len(t) <= 1 or t in TOKEN_STOP_WORDS or t[0].isdigit():
            continue
        if t not in tokens:  # dedupe, preserve first-seen order
            tokens.append(t)
    return tokens
