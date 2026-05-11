"""Seed the enhancements collection with default meal add-ons.

Run from the meal-api directory:
    python scripts/seed_enhancements.py

Requires MONGO_URI in .env or environment.
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from src.database import get_db

ENHANCEMENTS = [
    {
        "enhancementId": "fresh-coriander-lime",
        "name": "Fresh Coriander & Lime",
        "description": "Brightens Thai and Asian curries with fresh citrus and herby lift",
        "estimatedCost": 2.50,
        "ingredients": [
            {"name": "Fresh Coriander", "amount": "1 bunch"},
            {"name": "Lime", "amount": "1"},
        ],
        "compatibleIngredients": ["coconut milk", "fish sauce", "soy sauce", "ginger", "lemongrass", "chilli"],
        "compatibleRecipeKeywords": ["thai", "curry", "asian", "stir fry", "laksa"],
        "tags": ["fresh", "garnish"],
    },
    {
        "enhancementId": "garlic-bread",
        "name": "Garlic Bread",
        "description": "Classic side that goes with pasta, soups and casseroles",
        "estimatedCost": 3.00,
        "ingredients": [
            {"name": "Baguette or ciabatta", "amount": "1 small loaf"},
            {"name": "Butter", "amount": "50g"},
            {"name": "Garlic", "amount": "2 cloves"},
        ],
        "compatibleIngredients": ["pasta", "tomato", "bolognese", "mince", "lentil"],
        "compatibleRecipeKeywords": ["pasta", "bolognese", "bake", "casserole", "soup", "italian"],
        "tags": ["side", "bread"],
    },
    {
        "enhancementId": "toasted-cashews",
        "name": "Toasted Cashews",
        "description": "Adds crunch and richness to stir fries and curries",
        "estimatedCost": 3.50,
        "ingredients": [
            {"name": "Cashew Nuts", "amount": "75g"},
        ],
        "compatibleIngredients": ["soy sauce", "oyster sauce", "sesame oil", "hoisin"],
        "compatibleRecipeKeywords": ["stir fry", "thai", "asian", "kung pao", "noodle"],
        "tags": ["crunch", "garnish"],
    },
    {
        "enhancementId": "parmesan-garnish",
        "name": "Parmesan Garnish",
        "description": "Freshly grated parmesan adds a savoury umami finish to pasta",
        "estimatedCost": 2.00,
        "ingredients": [
            {"name": "Parmesan Cheese", "amount": "50g"},
        ],
        "compatibleIngredients": ["pasta", "cream", "tomato sauce"],
        "compatibleRecipeKeywords": ["pasta", "risotto", "italian", "carbonara", "bolognese"],
        "tags": ["cheese", "garnish"],
    },
    {
        "enhancementId": "sour-cream-chives",
        "name": "Sour Cream & Chives",
        "description": "A cooling, creamy topper for spicy or rich dishes",
        "estimatedCost": 2.00,
        "ingredients": [
            {"name": "Sour Cream", "amount": "100ml"},
            {"name": "Fresh Chives", "amount": "small bunch"},
        ],
        "compatibleIngredients": ["potato", "chilli", "enchilada", "taco", "mince"],
        "compatibleRecipeKeywords": ["mexican", "nachos", "chilli", "loaded", "potato", "beef"],
        "tags": ["dairy", "cool"],
    },
    {
        "enhancementId": "crispy-fried-shallots",
        "name": "Crispy Fried Shallots",
        "description": "Instant crunch and sweet onion depth for soups and noodle dishes",
        "estimatedCost": 2.50,
        "ingredients": [
            {"name": "Fried Shallots", "amount": "2 tbsp"},
        ],
        "compatibleIngredients": ["noodle", "broth", "soy sauce", "fish sauce", "rice"],
        "compatibleRecipeKeywords": ["pho", "ramen", "noodle", "soup", "fried rice", "asian"],
        "tags": ["crunch", "garnish"],
    },
    {
        "enhancementId": "yoghurt-mint-raita",
        "name": "Yoghurt & Mint Raita",
        "description": "A cooling yoghurt sauce that balances heat in Indian-style dishes",
        "estimatedCost": 2.00,
        "ingredients": [
            {"name": "Greek Yoghurt", "amount": "150ml"},
            {"name": "Fresh Mint", "amount": "small handful"},
            {"name": "Cucumber", "amount": "¼"},
        ],
        "compatibleIngredients": ["curry paste", "garam masala", "cumin", "turmeric", "naan"],
        "compatibleRecipeKeywords": ["curry", "indian", "dahl", "spiced", "lamb"],
        "tags": ["dairy", "cool", "indian"],
    },
    {
        "enhancementId": "sesame-spring-onion",
        "name": "Sesame Seeds & Spring Onion",
        "description": "Light, nutty garnish that finishes any Asian dish beautifully",
        "estimatedCost": 1.50,
        "ingredients": [
            {"name": "Sesame Seeds", "amount": "1 tbsp"},
            {"name": "Spring Onion", "amount": "2 stalks"},
        ],
        "compatibleIngredients": ["soy sauce", "sesame oil", "miso", "teriyaki", "oyster sauce"],
        "compatibleRecipeKeywords": ["stir fry", "teriyaki", "japanese", "korean", "fried rice", "asian"],
        "tags": ["garnish", "nutty"],
    },
    {
        "enhancementId": "steamed-bok-choy",
        "name": "Steamed Bok Choy",
        "description": "A quick, healthy green side that pairs with most Asian mains",
        "estimatedCost": 2.50,
        "ingredients": [
            {"name": "Bok Choy", "amount": "2 heads"},
            {"name": "Soy Sauce", "amount": "1 tbsp"},
        ],
        "compatibleIngredients": ["chicken", "pork", "oyster sauce", "soy sauce", "hoisin"],
        "compatibleRecipeKeywords": ["asian", "stir fry", "chinese", "noodle", "teriyaki"],
        "tags": ["vegetable", "side"],
    },
    {
        "enhancementId": "rocket-parmesan-salad",
        "name": "Rocket & Parmesan Side Salad",
        "description": "A peppery salad to balance rich pasta or meat dishes",
        "estimatedCost": 3.00,
        "ingredients": [
            {"name": "Rocket", "amount": "60g"},
            {"name": "Parmesan", "amount": "30g"},
            {"name": "Lemon", "amount": "½"},
            {"name": "Olive Oil", "amount": "1 tbsp"},
        ],
        "compatibleIngredients": ["pasta", "chicken", "beef", "steak", "lamb"],
        "compatibleRecipeKeywords": ["italian", "pasta", "steak", "lamb", "roast", "grilled"],
        "tags": ["salad", "side"],
    },
]


def seed():
    db = get_db()
    col = db["enhancements"]
    col.create_index("enhancementId", unique=True)

    inserted = 0
    skipped = 0
    for e in ENHANCEMENTS:
        existing = col.find_one({"enhancementId": e["enhancementId"]})
        if existing:
            skipped += 1
        else:
            col.insert_one(e)
            inserted += 1

    print(f"Seeded {inserted} enhancements ({skipped} already existed).")


if __name__ == "__main__":
    seed()
