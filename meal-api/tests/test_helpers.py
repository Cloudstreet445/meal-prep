"""Unit tests for pure helper functions in routers/bundles.py."""

import pytest
from src.routers.bundles import _normalise_name, _guess_category, _derive_shopping_list


class TestNormaliseName:
    def test_lowercases(self):
        assert _normalise_name("Chicken") == "chicken"

    def test_strips_spaces(self):
        assert _normalise_name("olive oil") == "oliveoil"

    def test_strips_special_chars(self):
        assert _normalise_name("Garlic (minced)") == "garlicminced"

    def test_strips_hyphens(self):
        assert _normalise_name("self-raising flour") == "selfraisingflour"

    def test_preserves_numbers(self):
        assert _normalise_name("2% milk") == "2milk"

    def test_empty_string(self):
        assert _normalise_name("") == ""


class TestGuessCategory:
    def test_identifies_chicken(self):
        assert _guess_category("Chicken breast") == "protein"

    def test_identifies_beef(self):
        assert _guess_category("Beef mince 500g") == "protein"

    def test_identifies_pork(self):
        assert _guess_category("Pork shoulder") == "protein"

    def test_identifies_lamb(self):
        assert _guess_category("Lamb chops") == "protein"

    def test_identifies_milk(self):
        assert _guess_category("Full cream milk") == "dairy"

    def test_identifies_cheese(self):
        assert _guess_category("Tasty cheese block") == "dairy"

    def test_identifies_butter(self):
        assert _guess_category("Butter salted") == "dairy"

    def test_identifies_onion_as_vegetable(self):
        assert _guess_category("Brown onion") == "vegetable"

    def test_identifies_broccoli_as_vegetable(self):
        assert _guess_category("Broccoli head") == "vegetable"

    def test_identifies_garlic_as_vegetable(self):
        assert _guess_category("Garlic cloves") == "vegetable"

    def test_identifies_pasta_as_pantry(self):
        assert _guess_category("Pasta penne 500g") == "pantry"

    def test_identifies_rice_as_pantry(self):
        assert _guess_category("Jasmine rice 1kg") == "pantry"

    def test_identifies_soy_sauce_as_pantry(self):
        assert _guess_category("Soy sauce 250ml") == "pantry"

    def test_defaults_to_other(self):
        assert _guess_category("Random ingredient") == "other"

    def test_case_insensitive(self):
        assert _guess_category("CHICKEN BREAST") == "protein"


class TestDeriveShoppingList:
    def test_returns_all_ingredients(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Pasta",
                "ingredients": [
                    {"name": "Pasta", "amount": "300g", "estimatedCost": 1.50},
                    {"name": "Garlic", "amount": "2 cloves", "estimatedCost": 0.50},
                ],
            }
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        assert len(items) == 2

    def test_deduplicates_shared_ingredients(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Pasta",
                "ingredients": [{"name": "Garlic", "amount": "2 cloves", "estimatedCost": 0.50}],
            },
            {
                "recipeId": "r2",
                "name": "Stir Fry",
                "ingredients": [{"name": "Garlic", "amount": "3 cloves", "estimatedCost": 0.75}],
            },
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        garlic_items = [i for i in items if i["name"] == "Garlic"]
        assert len(garlic_items) == 1

    def test_sums_cost_for_shared_ingredients(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Pasta",
                "ingredients": [{"name": "Garlic", "amount": "2 cloves", "estimatedCost": 0.50}],
            },
            {
                "recipeId": "r2",
                "name": "Stir Fry",
                "ingredients": [{"name": "Garlic", "amount": "3 cloves", "estimatedCost": 0.75}],
            },
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        garlic = next(i for i in items if i["name"] == "Garlic")
        assert garlic["estimatedCost"] == 1.25

    def test_shared_with_populated_for_multi_recipe_ingredients(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Pasta",
                "ingredients": [{"name": "Garlic", "amount": "2 cloves", "estimatedCost": 0.50}],
            },
            {
                "recipeId": "r2",
                "name": "Stir Fry",
                "ingredients": [{"name": "Garlic", "amount": "3 cloves", "estimatedCost": 0.75}],
            },
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        garlic = next(i for i in items if i["name"] == "Garlic")
        assert set(garlic["sharedWith"]) == {"Pasta", "Stir Fry"}

    def test_shared_with_empty_for_single_recipe_ingredient(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Pasta",
                "ingredients": [{"name": "Spaghetti", "amount": "200g", "estimatedCost": 1.00}],
            }
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        spaghetti = next(i for i in items if i["name"] == "Spaghetti")
        assert spaghetti["sharedWith"] == []

    def test_sorted_by_category_order(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Dinner",
                "ingredients": [
                    {"name": "Pasta", "amount": "200g", "estimatedCost": 1.00},
                    {"name": "Chicken breast", "amount": "400g", "estimatedCost": 5.00},
                    {"name": "Milk", "amount": "1 cup", "estimatedCost": 1.50},
                    {"name": "Broccoli", "amount": "1 head", "estimatedCost": 2.00},
                ],
            }
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        category_order = {"protein": 0, "vegetable": 1, "pantry": 2, "dairy": 3, "other": 4}
        indices = [category_order.get(i["category"], 4) for i in items]
        assert indices == sorted(indices)

    def test_total_calculation(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Dinner",
                "ingredients": [
                    {"name": "Pasta", "amount": "200g", "estimatedCost": 1.00},
                    {"name": "Sauce", "amount": "1 jar", "estimatedCost": 2.50},
                ],
            }
        ]
        _, total = _derive_shopping_list(recipes, pricing_db)
        assert total == 3.50

    def test_total_rounded_to_two_decimal_places(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Dinner",
                "ingredients": [
                    {"name": "Pasta", "amount": "200g", "estimatedCost": 1.333},
                    {"name": "Sauce", "amount": "1 jar", "estimatedCost": 2.666},
                ],
            }
        ]
        _, total = _derive_shopping_list(recipes, pricing_db)
        assert total == round(1.333 + 2.666, 2)

    def test_empty_recipes(self, pricing_db):
        items, total = _derive_shopping_list([], pricing_db)
        assert items == []
        assert total == 0.0

    def test_enriches_price_from_store_specific_data(self, pricing_db):
        pricing_db["products"].insert_one({
            "name": "Chicken Breast 1kg",
            "storePrice": {
                "paknsave-lower-hutt": {"currentPrice": 7.99, "isSpecial": True},
            },
        })
        recipes = [
            {
                "recipeId": "r1",
                "name": "Chicken Dinner",
                "ingredients": [
                    {"name": "Chicken breast", "amount": "400g", "estimatedCost": 5.00},
                ],
            }
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        chicken = next(i for i in items if "chicken" in i["name"].lower())
        assert chicken["currentPrice"] == 7.99
        assert chicken["isSpecial"] is True

    def test_enriches_only_matching_store(self, pricing_db):
        pricing_db["products"].insert_one({
            "name": "Chicken Breast 1kg",
            "storePrice": {
                "paknsave-porirua": {"currentPrice": 8.49, "isSpecial": False},
            },
        })
        recipes = [
            {
                "recipeId": "r1",
                "name": "Chicken Dinner",
                "ingredients": [
                    {"name": "Chicken breast", "amount": "400g", "estimatedCost": 5.00},
                ],
            }
        ]
        # Request lower-hutt prices — product only exists for porirua, so no enrichment
        items, _ = _derive_shopping_list(recipes, pricing_db, store_id="paknsave-lower-hutt")
        chicken = next(i for i in items if "chicken" in i["name"].lower())
        assert chicken["currentPrice"] is None

    def test_from_special_flag_propagates(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Pasta",
                "ingredients": [
                    {"name": "Garlic", "amount": "2 cloves", "estimatedCost": 0.50, "fromSpecial": False},
                ],
            },
            {
                "recipeId": "r2",
                "name": "Stir Fry",
                "ingredients": [
                    {"name": "Garlic", "amount": "3 cloves", "estimatedCost": 0.75, "fromSpecial": True},
                ],
            },
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        garlic = next(i for i in items if i["name"] == "Garlic")
        assert garlic["fromSpecial"] is True
