"""Unit tests for pure helper functions in routers/bundles.py."""

import pytest
from src.routers.helpers import (
    _normalise_name, _guess_category, _derive_shopping_list,
    _parse_amount, _normalise_unit, _add_amounts,
)


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


class TestParseAmount:
    def test_grams_no_space(self):
        assert _parse_amount("500g") == {"value": 500.0, "unit": "g"}

    def test_kg_with_space(self):
        assert _parse_amount("1.5 kg") == {"value": 1.5, "unit": "kg"}

    def test_plural_unit_normalised(self):
        assert _parse_amount("2 cloves") == {"value": 2.0, "unit": "clove"}

    def test_cups_normalised(self):
        assert _parse_amount("2 cups") == {"value": 2.0, "unit": "cup"}

    def test_ml(self):
        assert _parse_amount("400ml") == {"value": 400.0, "unit": "ml"}

    def test_litre_aliases(self):
        assert _parse_amount("1 litre") == {"value": 1.0, "unit": "l"}

    def test_empty_string_returns_none(self):
        assert _parse_amount("") is None

    def test_no_unit_returns_none(self):
        assert _parse_amount("500") is None

    def test_non_parseable_returns_none(self):
        assert _parse_amount("a handful") is None


class TestNormaliseUnit:
    def test_grams_below_threshold(self):
        assert _normalise_unit(800, "g") == (800, "g")

    def test_grams_at_threshold_converts_to_kg(self):
        assert _normalise_unit(1000, "g") == (1.0, "kg")

    def test_grams_above_threshold(self):
        assert _normalise_unit(1500, "g") == (1.5, "kg")

    def test_ml_below_threshold(self):
        assert _normalise_unit(600, "ml") == (600, "ml")

    def test_ml_at_threshold_converts_to_L(self):
        assert _normalise_unit(1000, "ml") == (1.0, "L")

    def test_other_units_unchanged(self):
        assert _normalise_unit(3, "cup") == (3, "cup")


class TestAddAmounts:
    def test_same_unit_sums(self):
        result = _add_amounts({"value": 300, "unit": "g"}, {"value": 200, "unit": "g"})
        assert result == {"value": 500, "unit": "g"}

    def test_g_plus_kg(self):
        result = _add_amounts({"value": 500, "unit": "g"}, {"value": 1, "unit": "kg"})
        assert result == {"value": 1500, "unit": "g"}

    def test_kg_plus_g(self):
        result = _add_amounts({"value": 1, "unit": "kg"}, {"value": 500, "unit": "g"})
        assert result == {"value": 1500, "unit": "g"}

    def test_ml_plus_l(self):
        result = _add_amounts({"value": 400, "unit": "ml"}, {"value": 1, "unit": "l"})
        assert result == {"value": 1400, "unit": "ml"}

    def test_incompatible_units_returns_none(self):
        assert _add_amounts({"value": 1, "unit": "cup"}, {"value": 500, "unit": "g"}) is None

    def test_same_count_unit_sums(self):
        result = _add_amounts({"value": 2, "unit": "clove"}, {"value": 3, "unit": "clove"})
        assert result == {"value": 5, "unit": "clove"}


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

    def test_aggregates_same_unit_quantities(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Pasta",
                "ingredients": [{"name": "Chicken breast", "amount": "400g", "estimatedCost": 4.00}],
            },
            {
                "recipeId": "r2",
                "name": "Stir Fry",
                "ingredients": [{"name": "Chicken breast", "amount": "600g", "estimatedCost": 5.00}],
            },
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        chicken = next(i for i in items if "chicken" in i["name"].lower())
        assert chicken["amount"] == "1 kg"

    def test_aggregates_cross_unit_mass(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Pasta",
                "ingredients": [{"name": "Potatoes", "amount": "1 kg", "estimatedCost": 3.00}],
            },
            {
                "recipeId": "r2",
                "name": "Soup",
                "ingredients": [{"name": "Potatoes", "amount": "500g", "estimatedCost": 2.00}],
            },
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        potatoes = next(i for i in items if "potatoes" in i["name"].lower())
        assert potatoes["amount"] == "1.5 kg"

    def test_aggregates_volume_and_normalises(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Recipe 1",
                "ingredients": [{"name": "Chicken stock", "amount": "600ml", "estimatedCost": 1.00}],
            },
            {
                "recipeId": "r2",
                "name": "Recipe 2",
                "ingredients": [{"name": "Chicken stock", "amount": "600ml", "estimatedCost": 1.00}],
            },
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        stock = next(i for i in items if "stock" in i["name"].lower())
        assert stock["amount"] == "1.2 L"

    def test_incompatible_units_produce_amount_parts(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Pasta",
                "ingredients": [{"name": "Garlic", "amount": "1 cup", "estimatedCost": 0.50}],
            },
            {
                "recipeId": "r2",
                "name": "Stir Fry",
                "ingredients": [{"name": "Garlic", "amount": "500g", "estimatedCost": 0.75}],
            },
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        garlic = next(i for i in items if i["name"] == "Garlic")
        assert "amount_parts" in garlic
        assert len(garlic["amount_parts"]) == 2
        parts_by_recipe = {p["recipe"]: p["amount"] for p in garlic["amount_parts"]}
        assert parts_by_recipe["Pasta"] == "1 cup"
        assert parts_by_recipe["Stir Fry"] == "500g"

    def test_missing_amount_does_not_crash(self, pricing_db):
        recipes = [
            {
                "recipeId": "r1",
                "name": "Pasta",
                "ingredients": [{"name": "Salt", "amount": "", "estimatedCost": 0.10}],
            },
            {
                "recipeId": "r2",
                "name": "Stir Fry",
                "ingredients": [{"name": "Salt", "amount": "", "estimatedCost": 0.10}],
            },
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        salt = next(i for i in items if i["name"] == "Salt")
        assert salt["amount"] == ""

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
