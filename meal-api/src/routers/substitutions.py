"""Ingredient substitution suggestions via Claude."""

import os
import json
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from anthropic import Anthropic
from ..database import get_pricing_db

router = APIRouter()


class SubstituteRequest(BaseModel):
    ingredient: str
    store_id: str = "paknsave-lower-hutt"


@router.post("/suggest")
def suggest_substitutes(body: SubstituteRequest):
    """Return 2-3 AI-suggested substitutes for an ingredient, with price context."""
    pricing_db = get_pricing_db()

    # Look up current price for the ingredient to give Claude useful context
    words = [w for w in re.split(r'\W+', body.ingredient.lower()) if len(w) > 2]
    matched_product = None
    price_context = ""

    if words:
        product = pricing_db["products"].find_one(
            {
                "$text": {"$search": " ".join(words[:3])},
                f"storePrice.{body.store_id}": {"$exists": True},
            },
            {
                "name": 1,
                f"storePrice.{body.store_id}.currentPrice": 1,
            }
        )
        if product:
            matched_product = product.get("name")
            store_data = product.get("storePrice", {}).get(body.store_id, {})
            price = store_data.get("currentPrice")
            if price:
                price_context = f" (currently ${price:.2f} at PAK'nSave)"

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI substitutions not configured")

    client = Anthropic(api_key=api_key)

    prompt = f"""Ingredient: {body.ingredient}{price_context}

Suggest 2-3 practical alternatives that could substitute this in a typical weeknight dinner recipe in New Zealand. Prefer cheaper cuts or budget options where relevant.

Respond ONLY with a valid JSON array, no markdown:
[
  {{"name": "chicken thigh", "reason": "Cheaper cut, same flavour when slow-cooked", "estimatedPrice": 4.99}},
  ...
]"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'^```\s*', '', raw, flags=re.MULTILINE)
    raw = raw.strip().strip('`')

    try:
        suggestions = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Could not parse AI response")

    return {
        "ingredient": body.ingredient,
        "matchedProduct": matched_product,
        "suggestions": suggestions,
    }
