"""Minimal HTTP server — exposes POST /generate so meal-api can trigger plan generation."""

import os
import sys
import json
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# Allow imports from src/
sys.path.insert(0, os.path.dirname(__file__))

from planner import get_market_data
from ai.claude import generate_meal_plan
from db.mongodb import store_recipes, store_bundle

app = FastAPI(title="Paknsave Planner", docs_url=None, redoc_url=None)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate")
def generate():
    """Run the full meal plan generation pipeline and store results to MongoDB."""
    store_id = os.environ.get("STORE_ID", "paknsave-lower-hutt")

    # Step 1 — market data
    market_data = get_market_data(store_id)
    if not market_data.any_data():
        raise HTTPException(status_code=503, detail="No pricing data found — has the scraper run?")

    # Step 2 — generate via Claude
    plan = generate_meal_plan(market_data)

    # Step 3 — store
    week_id = datetime.now().strftime("%Y-%m-%d")
    recipe_count, recipe_ids = store_recipes(plan, week_id)
    bundle_id = store_bundle(plan, week_id, recipe_ids)

    # Step 4 — save output JSON alongside the container's working dir
    output_file = f"meal_plan_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    try:
        with open(output_file, "w") as f:
            json.dump(plan, f, indent=2)
    except OSError:
        pass  # output file is best-effort

    return {
        "bundleId": bundle_id,
        "week": week_id,
        "recipeCount": recipe_count,
        "estimatedTotal": plan.get("estimatedTotal"),
        "weekSummary": plan.get("weekSummary"),
    }
