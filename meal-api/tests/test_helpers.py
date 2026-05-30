"""Unit tests for pure helper functions in routers/bundles.py."""

import pytest
from src.routers.helpers import (
    _normalise_name, _guess_category, _derive_shopping_list,
    _parse_amount, _normalise_unit, _add_amounts,
    _infer_protein, _recipe_cost, _select_from_library,
    _enrich_ingredient, _ingredient_alternatives, _scale_amount,
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

    def test_cost_comes_from_live_price(self, pricing_db):
        pricing_db["products"].insert_one({
            "name": "Garlic Bulb",
            "storePrice": {"paknsave-lower-hutt": {"currentPrice": 1.29, "isSpecial": False}},
        })
        recipes = [
            {
                "recipeId": "r1",
                "name": "Pasta",
                "ingredients": [{"name": "Garlic", "amount": "2 cloves"}],
            },
            {
                "recipeId": "r2",
                "name": "Stir Fry",
                "ingredients": [{"name": "Garlic", "amount": "3 cloves"}],
            },
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        garlic = next(i for i in items if i["name"] == "Garlic")
        # Cost is the live currentPrice, not an accumulated sum of stored values
        assert garlic["estimatedCost"] == 1.29

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
        pricing_db["products"].insert_one({
            "name": "Pams Pasta 500g",
            "storePrice": {"paknsave-lower-hutt": {"currentPrice": 1.00, "isSpecial": False}},
        })
        pricing_db["products"].insert_one({
            "name": "Tomato Sauce Jar",
            "storePrice": {"paknsave-lower-hutt": {"currentPrice": 2.50, "isSpecial": False}},
        })
        recipes = [
            {
                "recipeId": "r1",
                "name": "Dinner",
                "ingredients": [
                    {"name": "Pasta", "amount": "200g"},
                    {"name": "Sauce", "amount": "1 jar"},
                ],
            }
        ]
        _, total = _derive_shopping_list(recipes, pricing_db)
        assert total == 3.50

    def test_total_rounded_to_two_decimal_places(self, pricing_db):
        pricing_db["products"].insert_one({
            "name": "Pams Pasta 500g",
            "storePrice": {"paknsave-lower-hutt": {"currentPrice": 1.333, "isSpecial": False}},
        })
        pricing_db["products"].insert_one({
            "name": "Tomato Sauce Jar",
            "storePrice": {"paknsave-lower-hutt": {"currentPrice": 2.666, "isSpecial": False}},
        })
        recipes = [
            {
                "recipeId": "r1",
                "name": "Dinner",
                "ingredients": [
                    {"name": "Pasta", "amount": "200g"},
                    {"name": "Sauce", "amount": "1 jar"},
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
            "storePrice": {"paknsave-lower-hutt": {"currentPrice": 7.99, "isSpecial": True}},
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
        # packPrice is the whole-pack store price; currentPrice is the
        # proportional share for the 400g actually needed (400/1000 × 7.99).
        assert chicken["packPrice"] == pytest.approx(7.99)
        assert chicken["currentPrice"] == pytest.approx(3.2)
        assert chicken["isSpecial"] is True

    def test_enriches_only_matching_store(self, pricing_db):
        pricing_db["products"].insert_one({
            "name": "Chicken Breast 1kg",
            "storePrice": {"paknsave-porirua": {"currentPrice": 8.49, "isSpecial": False}},
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

    def test_isspecial_comes_from_live_enrichment(self, pricing_db):
        pricing_db["products"].insert_one({
            "name": "Garlic Bulb",
            "storePrice": {"paknsave-lower-hutt": {"currentPrice": 0.99, "isSpecial": True}},
        })
        recipes = [
            {
                "recipeId": "r1",
                "name": "Pasta",
                "ingredients": [{"name": "Garlic", "amount": "2 cloves"}],
            },
            {
                "recipeId": "r2",
                "name": "Stir Fry",
                "ingredients": [{"name": "Garlic", "amount": "3 cloves"}],
            },
        ]
        items, _ = _derive_shopping_list(recipes, pricing_db)
        garlic = next(i for i in items if i["name"] == "Garlic")
        # isSpecial comes from the live product, not from a stored ingredient flag
        assert garlic["isSpecial"] is True


# ── TestShoppingExtras: cheapest default, overrides, serves, pantry, alternatives ──

class TestShoppingExtras:
    def _seed_two_brands(self, pricing_db, store="paknsave-lower-hutt"):
        pricing_db["products"].insert_one({
            "_id": "P-cheap", "name": "Pams Chicken Breast 1kg", "brand": "Pams",
            "sizeGrams": 1000.0,
            "storePrice": {store: {"currentPrice": 9.0, "isSpecial": False}},
        })
        pricing_db["products"].insert_one({
            "_id": "P-premium", "name": "Free Range Chicken Breast 1kg",
            "sizeGrams": 1000.0,
            "storePrice": {store: {"currentPrice": 15.0, "isSpecial": False}},
        })

    def _recipe(self):
        return [{
            "recipeId": "r1", "name": "Chicken Dinner", "serves": 4,
            "ingredients": [{"name": "Chicken breast", "amount": "1kg"}],
        }]

    def test_defaults_to_cheapest_brand(self, pricing_db):
        self._seed_two_brands(pricing_db)
        items, _ = _derive_shopping_list(self._recipe(), pricing_db)
        chicken = next(i for i in items if "chicken" in i["name"].lower())
        assert chicken["productId"] == "P-cheap"
        assert chicken["packPrice"] == pytest.approx(9.0)
        assert chicken["brand"] == "Pams"

    def test_override_picks_chosen_product(self, pricing_db):
        self._seed_two_brands(pricing_db)
        overrides = {_normalise_name("Chicken breast"): "P-premium"}
        items, total = _derive_shopping_list(self._recipe(), pricing_db, overrides=overrides)
        chicken = next(i for i in items if "chicken" in i["name"].lower())
        assert chicken["productId"] == "P-premium"
        assert chicken["packPrice"] == pytest.approx(15.0)
        assert chicken["isOverride"] is True
        assert total == pytest.approx(15.0)

    def test_alternatives_ranked_cheapest_first(self, pricing_db):
        self._seed_two_brands(pricing_db)
        alts = _ingredient_alternatives("Chicken breast", "1kg", pricing_db, "paknsave-lower-hutt")
        assert [a["productId"] for a in alts] == ["P-cheap", "P-premium"]
        assert alts[0]["brand"] == "Pams"

    def test_serves_scales_quantities_and_cost(self, pricing_db):
        self._seed_two_brands(pricing_db)
        # Recipe serves 4; household of 2 → buy half → 500g of a 1kg pack.
        items, _ = _derive_shopping_list(self._recipe(), pricing_db, serves=2)
        chicken = next(i for i in items if "chicken" in i["name"].lower())
        assert chicken["amount"] == "0.5 kg"  # 1kg halved
        assert chicken["currentPrice"] == pytest.approx(4.5)  # 500/1000 × $9

    def test_absurd_price_is_flagged_and_capped(self, pricing_db):
        pricing_db["products"].insert_one({
            "_id": "P-x", "name": "Truffle 1kg", "searchTokens": ["truffle"],
            "sizeGrams": 1000.0,
            "storePrice": {"paknsave-lower-hutt": {"currentPrice": 100.0, "isSpecial": False}},
        })
        item = {"name": "Truffle", "amount": "1kg"}
        enriched = _enrich_ingredient(item, pricing_db, "paknsave-lower-hutt")
        assert enriched["costWarning"] is True
        assert enriched["packPrice"] == 60.0     # _PACK_COST_CAP
        assert enriched["currentPrice"] == 20.0  # _INGREDIENT_COST_CAP

    def test_search_tokens_drive_matching(self, pricing_db):
        # Brand-led name where the ingredient word isn't first; searchTokens
        # (brand-stripped) still match, and the processed-word penalty steers
        # away from "Garlic Paste" toward plain garlic.
        pricing_db["products"].insert_many([
            {"_id": "P-clove", "name": "Pams Fresh Garlic 500g", "sizeGrams": 500.0,
             "searchTokens": ["garlic"],
             "storePrice": {"paknsave-lower-hutt": {"currentPrice": 4.0, "isSpecial": False}}},
            {"_id": "P-paste", "name": "Tegel Garlic Paste 200g", "sizeGrams": 200.0,
             "searchTokens": ["garlic", "paste"],
             "storePrice": {"paknsave-lower-hutt": {"currentPrice": 2.0, "isSpecial": False}}},
        ])
        alts = _ingredient_alternatives("Garlic", "100g", pricing_db, "paknsave-lower-hutt")
        # Plain garlic ranks above the cheaper paste despite costing more,
        # because "paste" is an unwanted processed token.
        assert alts[0]["productId"] == "P-clove"

    def test_pantry_items_flagged_and_excluded_from_total(self, pricing_db):
        self._seed_two_brands(pricing_db)
        pantry = {_normalise_name("chicken breast")}
        items, total = _derive_shopping_list(self._recipe(), pricing_db, pantry=pantry)
        chicken = next(i for i in items if "chicken" in i["name"].lower())
        assert chicken["inPantry"] is True
        assert total == 0.0  # the only item is in the pantry


# ── TestScaleAmount ────────────────────────────────────────────────────────────

class TestScaleAmount:
    def test_scales_grams(self):
        assert _scale_amount("400g", 1.5) == "600 g"

    def test_promotes_to_kg(self):
        assert _scale_amount("600g", 2) == "1.2 kg"

    def test_factor_one_unchanged(self):
        assert _scale_amount("400g", 1) == "400g"

    def test_unparseable_unchanged(self):
        assert _scale_amount("3 cloves", 2) == "6 clove"

    def test_empty_unchanged(self):
        assert _scale_amount("", 2) == ""


# ── Helpers for library selection tests ──────────────────────────────────────

def _make_recipe(recipe_id, name, ingredients, last_used="2025-01-01"):
    return {
        "recipeId": recipe_id,
        "name": name,
        "ingredients": [
            {"name": ing, "amount": "500g", "estimatedCost": cost}
            for ing, cost in ingredients
        ],
        "lastUsedWeek": last_used,
    }


class FakeDB:
    """Minimal stand-in for a pymongo Database for selection tests."""
    def __init__(self, recipes):
        self._recipes = recipes

    def __getitem__(self, coll):
        return self

    def find(self, query=None):
        if not query:
            return list(self._recipes)
        nin = (query or {}).get("recipeId", {}).get("$nin", [])
        return [r for r in self._recipes if r["recipeId"] not in nin]


# ── TestInferProtein ──────────────────────────────────────────────────────────

class TestInferProtein:
    def test_chicken_from_ingredient(self):
        r = _make_recipe("r1", "Soup", [("Chicken Drumsticks", 6.0)])
        assert _infer_protein(r) == "chicken"

    def test_pork_from_ingredient(self):
        r = _make_recipe("r1", "Stir Fry", [("Pork Mince", 5.0)])
        assert _infer_protein(r) == "pork"

    def test_sausage_maps_to_pork(self):
        r = _make_recipe("r1", "Bake", [("Hellers Pork Sausages", 7.0)])
        assert _infer_protein(r) == "pork"

    def test_beef_from_ingredient(self):
        r = _make_recipe("r1", "Bolognese", [("Beef Mince", 8.0)])
        assert _infer_protein(r) == "beef"

    def test_lamb_from_ingredient(self):
        r = _make_recipe("r1", "Stew", [("Lamb Shoulder", 10.0)])
        assert _infer_protein(r) == "lamb"

    def test_falls_back_to_other(self):
        r = _make_recipe("r1", "Salad", [("Lettuce", 2.0), ("Tomato", 1.5)])
        assert _infer_protein(r) == "other"

    def test_infers_from_recipe_name(self):
        r = _make_recipe("r1", "Chicken Curry", [("Onion", 1.0)])
        assert _infer_protein(r) == "chicken"

    def test_plant_protein_from_chickpeas(self):
        r = _make_recipe("r1", "Curry", [("Chickpeas", 2.0), ("Onion", 1.0)])
        assert _infer_protein(r) == "plant"

    def test_plant_protein_from_tofu(self):
        r = _make_recipe("r1", "Stir Fry", [("Firm Tofu", 4.0)])
        assert _infer_protein(r) == "plant"

    def test_fish_protein_from_salmon(self):
        r = _make_recipe("r1", "Bake", [("Salmon Fillet", 12.0)])
        assert _infer_protein(r) == "fish"

    def test_proteinless_meal_is_other(self):
        r = _make_recipe("r1", "Garden Salad", [("Lettuce", 2.0), ("Tomato", 1.5)])
        assert _infer_protein(r) == "other"

    def test_meat_wins_over_plant_in_mixed_dish(self):
        r = _make_recipe("r1", "Chilli", [("Beef Mince", 8.0), ("Beans", 1.0)])
        assert _infer_protein(r) == "beef"


# ── TestRecipeCost ─────────────────────────────────────────────────────────────

class TestRecipeCost:
    def test_sums_ingredient_costs(self):
        r = _make_recipe("r1", "Meal", [("Chicken", 6.0), ("Potato", 2.0), ("Garlic", 0.5)])
        assert _recipe_cost(r) == pytest.approx(8.5)

    def test_empty_ingredients(self):
        assert _recipe_cost({"ingredients": []}) == 0.0

    def test_missing_estimatedCost_treated_as_zero(self):
        r = {"ingredients": [{"name": "Onion", "amount": "1"}]}
        assert _recipe_cost(r) == 0.0

    def test_costTier_budget(self):
        assert _recipe_cost({"costTier": "budget", "ingredients": []}) == pytest.approx(10.0)

    def test_costTier_mid(self):
        assert _recipe_cost({"costTier": "mid", "ingredients": []}) == pytest.approx(17.0)

    def test_costTier_premium(self):
        assert _recipe_cost({"costTier": "premium", "ingredients": []}) == pytest.approx(28.0)

    def test_baselineCost_takes_precedence_over_tier(self):
        r = {"baselineCost": 12.5, "costTier": "budget", "ingredients": []}
        assert _recipe_cost(r) == pytest.approx(12.5)


# ── TestSelectFromLibrary ──────────────────────────────────────────────────────

def _make_library():
    return [
        _make_recipe("chicken-1", "Chicken Soup",       [("Chicken Drumsticks", 6.0), ("Carrot", 1.5)], "2025-01-01"),
        _make_recipe("chicken-2", "Chicken Curry",      [("Chicken Thighs", 7.0), ("Onion", 1.0)],      "2025-06-01"),
        _make_recipe("pork-1",    "Pork Bolognese",     [("Pork Mince", 5.0), ("Pasta", 2.0)],           "2025-01-01"),
        _make_recipe("pork-2",    "Pork Stir Fry",      [("Pork Mince", 5.0), ("Cabbage", 1.5)],         "2025-03-01"),
        _make_recipe("beef-1",    "Beef Bolognese",     [("Beef Mince", 8.0), ("Tomato", 1.0)],          "2025-01-01"),
        _make_recipe("lamb-1",    "Lamb Stew",          [("Lamb Shoulder", 10.0), ("Potato", 2.0)],      "2025-01-01"),
        _make_recipe("veg-1",     "Vege Noodles",       [("Noodles", 2.0), ("Cabbage", 1.5)],            "2025-01-01"),
    ]


class TestSelectFromLibrary:
    def test_returns_five_recipes(self):
        db = FakeDB(_make_library())
        result = _select_from_library(db, budget=60, exclusions=[], exclude_ids=set())
        assert result is not None
        assert len(result) == 5

    def test_total_within_budget(self):
        db = FakeDB(_make_library())
        result = _select_from_library(db, budget=60, exclusions=[], exclude_ids=set())
        assert result is not None
        total = sum(r["_cost"] for r in result)
        assert total <= 60

    def test_excludes_current_bundle(self):
        library = _make_library()
        db = FakeDB(library)
        result = _select_from_library(db, budget=60, exclusions=[], exclude_ids={"chicken-1"})
        assert result is not None
        ids = [r["recipeId"] for r in result]
        assert "chicken-1" not in ids

    def test_exclusion_ingredient_filtered(self):
        db = FakeDB(_make_library())
        result = _select_from_library(db, budget=60, exclusions=["lamb"], exclude_ids=set())
        assert result is not None
        for r in result:
            for ing in r["ingredients"]:
                assert "lamb" not in ing["name"].lower()

    def test_returns_none_when_too_few_candidates(self):
        tiny_library = _make_library()[:3]
        db = FakeDB(tiny_library)
        result = _select_from_library(db, budget=60, exclusions=[], exclude_ids=set(), n=5)
        assert result is None

    def test_prefers_least_recently_used(self):
        # chicken-1 last used 2025-01-01, chicken-2 last used 2025-06-01
        # Should prefer chicken-1
        db = FakeDB(_make_library())
        result = _select_from_library(db, budget=60, exclusions=[], exclude_ids=set())
        assert result is not None
        ids = [r["recipeId"] for r in result]
        assert "chicken-1" in ids

    def test_protein_variety(self):
        db = FakeDB(_make_library())
        result = _select_from_library(db, budget=60, exclusions=[], exclude_ids=set())
        assert result is not None
        proteins = {r["_protein"] for r in result}
        # Should have at least 3 different protein types
        assert len(proteins) >= 3

    def test_budget_too_tight_returns_none(self):
        db = FakeDB(_make_library())
        # $5 can't fit 5 meals
        result = _select_from_library(db, budget=5, exclusions=[], exclude_ids=set())
        assert result is None


class TestSelectFromLibraryExtras:
    def test_graceful_degrade_returns_partial_plan(self):
        db = FakeDB(_make_library())
        # $20 can't fit a full 5-meal week, but should still build >= 3.
        strict = _select_from_library(db, budget=20, exclusions=[], exclude_ids=set())
        assert strict is None  # default min_n == n == 5
        degraded = _select_from_library(db, budget=20, exclusions=[], exclude_ids=set(), min_n=3)
        assert degraded is not None
        assert 3 <= len(degraded) < 5
        assert sum(r["_cost"] for r in degraded) <= 20

    def test_diet_tags_filter(self):
        library = [
            _make_recipe("v1", "Tofu Curry",   [("Tofu", 5.0)]),
            _make_recipe("v2", "Lentil Dahl",  [("Lentils", 4.0)]),
            _make_recipe("v3", "Veggie Pasta", [("Pasta", 3.0)]),
            _make_recipe("m1", "Chicken Soup", [("Chicken", 6.0)]),
            _make_recipe("m2", "Beef Stew",    [("Beef Mince", 8.0)]),
        ]
        for r in library[:3]:
            r["dietTags"] = ["vegetarian"]
        db = FakeDB(library)
        result = _select_from_library(
            db, budget=60, exclusions=[], exclude_ids=set(),
            n=3, min_n=3, diet_tags=["vegetarian"],
        )
        assert result is not None
        assert all("vegetarian" in r.get("dietTags", []) for r in result)

    def test_prefers_protein_centred_meal(self):
        # With one slot, a meal with a protein at the centre should win over a
        # proteinless one — "other" is rotated last.
        library = [
            _make_recipe("salad", "Garden Salad", [("Lettuce", 2.0), ("Tomato", 1.5)]),
            _make_recipe("chick", "Chicken Soup", [("Chicken", 6.0)]),
        ]
        db = FakeDB(library)
        result = _select_from_library(db, budget=60, exclusions=[], exclude_ids=set(), n=1, min_n=1)
        assert result is not None
        assert result[0]["recipeId"] == "chick"

    def test_diet_tags_too_few_returns_none(self):
        library = _make_library()  # none tagged
        db = FakeDB(library)
        result = _select_from_library(
            db, budget=60, exclusions=[], exclude_ids=set(),
            diet_tags=["vegan"], min_n=3,
        )
        assert result is None


# ── TestSelectFromLibraryPriceAware ────────────────────────────────────────────

def _seed_product(pricing_db, name, price, *, is_special=False, store_id="paknsave-lower-hutt"):
    pricing_db["products"].insert_one({
        "name": name,
        "storePrice": {store_id: {"currentPrice": price, "isSpecial": is_special}},
    })


class TestSelectFromLibraryPriceAware:
    """When a pricing_db is supplied, selection uses live cost and specials."""

    def _five_protein_library(self):
        # One recipe per non-chicken protein, plus two chicken options that
        # contend for the single chicken slot. 500g of a 1kg pack = 1 pack.
        return [
            _make_recipe("chicken-cheap",  "Chicken Frames Soup", [("Chicken Frames", 0.0)]),
            _make_recipe("chicken-pricey", "Chicken Breast Bake",  [("Chicken Breast", 0.0)]),
            _make_recipe("pork-1",  "Pork Roast",  [("Pork Mince", 0.0)]),
            _make_recipe("beef-1",  "Beef Chilli", [("Beef Mince", 0.0)]),
            _make_recipe("lamb-1",  "Lamb Stew",   [("Lamb Shoulder", 0.0)]),
            _make_recipe("veg-1",   "Tofu Curry",  [("Tofu", 0.0)]),
        ]

    def _seed_prices(self, pricing_db, chicken_cheap=3.0, chicken_pricey=9.0):
        _seed_product(pricing_db, "Chicken Frames 1kg", chicken_cheap)
        _seed_product(pricing_db, "Chicken Breast 1kg", chicken_pricey)
        _seed_product(pricing_db, "Pork Mince 1kg",    7.0)
        _seed_product(pricing_db, "Beef Mince 1kg",    8.0)
        _seed_product(pricing_db, "Lamb Shoulder 1kg", 12.0)
        _seed_product(pricing_db, "Tofu 1kg",          3.5)

    def test_uses_live_cost_not_static_estimate(self, pricing_db):
        self._seed_prices(pricing_db)
        db = FakeDB(self._five_protein_library())
        result = _select_from_library(
            db, budget=60, exclusions=[], exclude_ids=set(),
            pricing_db=pricing_db, store_id="paknsave-lower-hutt",
        )
        assert result is not None
        costs = {r["recipeId"]: r["_cost"] for r in result}
        # _cost reflects the live pack price, not the 0.0 ingredient estimate
        assert costs["chicken-cheap"] == pytest.approx(3.0)
        assert costs["pork-1"] == pytest.approx(7.0)

    def test_prefers_cheaper_meal_for_contested_protein(self, pricing_db):
        self._seed_prices(pricing_db, chicken_cheap=3.0, chicken_pricey=9.0)
        db = FakeDB(self._five_protein_library())
        result = _select_from_library(
            db, budget=60, exclusions=[], exclude_ids=set(),
            pricing_db=pricing_db, store_id="paknsave-lower-hutt",
        )
        assert result is not None
        ids = {r["recipeId"] for r in result}
        assert "chicken-cheap" in ids
        assert "chicken-pricey" not in ids

    def test_special_boosts_otherwise_equal_meal(self, pricing_db):
        # Both chicken options cost the same; only one is on special.
        _seed_product(pricing_db, "Chicken Thigh 1kg", 7.0, is_special=True)
        _seed_product(pricing_db, "Chicken Drumstick 1kg", 7.0, is_special=False)
        _seed_product(pricing_db, "Pork Mince 1kg",    7.0)
        _seed_product(pricing_db, "Beef Mince 1kg",    8.0)
        _seed_product(pricing_db, "Lamb Shoulder 1kg", 12.0)
        _seed_product(pricing_db, "Tofu 1kg",          3.5)
        library = [
            _make_recipe("chicken-special", "Thigh Tray",     [("Chicken Thigh", 0.0)]),
            _make_recipe("chicken-normal",  "Drumstick Tray", [("Chicken Drumstick", 0.0)]),
            _make_recipe("pork-1", "Pork Roast",  [("Pork Mince", 0.0)]),
            _make_recipe("beef-1", "Beef Chilli", [("Beef Mince", 0.0)]),
            _make_recipe("lamb-1", "Lamb Stew",   [("Lamb Shoulder", 0.0)]),
            _make_recipe("veg-1",  "Tofu Curry",  [("Tofu", 0.0)]),
        ]
        db = FakeDB(library)
        result = _select_from_library(
            db, budget=60, exclusions=[], exclude_ids=set(),
            pricing_db=pricing_db, store_id="paknsave-lower-hutt",
        )
        assert result is not None
        ids = {r["recipeId"] for r in result}
        assert "chicken-special" in ids
        assert "chicken-normal" not in ids

    def test_total_within_budget_uses_live_prices(self, pricing_db):
        self._seed_prices(pricing_db)
        db = FakeDB(self._five_protein_library())
        result = _select_from_library(
            db, budget=60, exclusions=[], exclude_ids=set(),
            pricing_db=pricing_db, store_id="paknsave-lower-hutt",
        )
        assert result is not None
        assert sum(r["_cost"] for r in result) <= 60

    def test_uses_stored_sizeGrams_when_name_has_no_size(self, pricing_db):
        # Product name has no parseable size, but the scraper stored sizeGrams.
        # The proportional cost must use the stored 1000g, not treat it as 1 unit.
        pricing_db["products"].insert_one({
            "name": "Chicken Breast",
            "sizeGrams": 1000.0,
            "storePrice": {"paknsave-lower-hutt": {"currentPrice": 8.0, "isSpecial": False}},
        })
        item = {"name": "Chicken breast", "amount": "500g"}
        enriched = _enrich_ingredient(item, pricing_db, "paknsave-lower-hutt")
        assert enriched["packPrice"] == pytest.approx(8.0)        # 1 × 1kg pack
        assert enriched["currentPrice"] == pytest.approx(4.0)     # 500g / 1000g × $8

    def test_falls_back_to_estimate_when_no_price_match(self, pricing_db):
        # Empty pricing DB → live cost 0 → fall back to static ingredient cost.
        library = [
            _make_recipe("chicken-1", "Chicken Soup",   [("Chicken Drumsticks", 6.0)]),
            _make_recipe("pork-1",    "Pork Bolognese", [("Pork Mince", 5.0)]),
            _make_recipe("beef-1",    "Beef Bolognese", [("Beef Mince", 8.0)]),
            _make_recipe("lamb-1",    "Lamb Stew",      [("Lamb Shoulder", 10.0)]),
            _make_recipe("veg-1",     "Vege Noodles",   [("Noodles", 2.0)]),
        ]
        db = FakeDB(library)
        result = _select_from_library(
            db, budget=60, exclusions=[], exclude_ids=set(),
            pricing_db=pricing_db, store_id="paknsave-lower-hutt",
        )
        assert result is not None
        costs = {r["recipeId"]: r["_cost"] for r in result}
        assert costs["chicken-1"] == pytest.approx(6.0)  # from _recipe_cost fallback
