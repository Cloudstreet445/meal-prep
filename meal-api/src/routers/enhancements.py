"""Meal enhancement endpoints.

Enhancements are small optional add-ons (garnishes, sides, toppings) that improve a
meal for a few extra dollars. They are stored in the `enhancements` collection and
matched to recipes via keyword tags on ingredients and recipe names.

MEA-53 tagging approach: enhancements carry `compatibleIngredients` (ingredient name
keywords from the recipe that signal a match) and `compatibleRecipeKeywords` (words
in the recipe name or description that signal a match). Either match triggers.
"""

import re
from fastapi import APIRouter, HTTPException
from ..database import get_db

router = APIRouter()


def _clean(doc) -> dict:
    if not doc:
        return {}
    doc["_id"] = str(doc["_id"])
    return doc


def _matches_recipe(enhancement: dict, recipe: dict) -> bool:
    """Return True if the enhancement is relevant to the given recipe."""
    ingredient_names = " ".join(
        i.get("name", "") for i in recipe.get("ingredients", [])
    ).lower()
    recipe_text = (
        recipe.get("name", "") + " " + recipe.get("description", "")
    ).lower()

    for keyword in enhancement.get("compatibleIngredients", []):
        if keyword.lower() in ingredient_names:
            return True

    for keyword in enhancement.get("compatibleRecipeKeywords", []):
        if keyword.lower() in recipe_text:
            return True

    return False


@router.get("/")
def list_enhancements():
    """List all available meal enhancements."""
    db = get_db()
    docs = list(db["enhancements"].find({}).sort("name", 1))
    return [_clean(doc) for doc in docs]


@router.get("/for-recipe/{recipe_id}")
def get_enhancements_for_recipe(recipe_id: str):
    """Return enhancements that match the given recipe's ingredients and keywords."""
    db = get_db()
    recipe = db["recipes"].find_one({"recipeId": recipe_id})
    if not recipe:
        raise HTTPException(status_code=404, detail=f"Recipe {recipe_id} not found")

    all_enhancements = list(db["enhancements"].find({}))
    matched = [_clean(e) for e in all_enhancements if _matches_recipe(e, recipe)]
    return {"recipeId": recipe_id, "enhancements": matched}


@router.get("/{enhancement_id}")
def get_enhancement(enhancement_id: str):
    """Get a single enhancement by ID."""
    db = get_db()
    doc = db["enhancements"].find_one({"enhancementId": enhancement_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Enhancement {enhancement_id} not found")
    return _clean(doc)
