"""Unit tests for data models in models.py."""

import pytest
from models import MarketData, Ingredient, Meal, ShoppingItem, MealPlan


class TestMarketDataAnyData:
    def test_true_when_proteins_on_special(self):
        data = MarketData(
            proteins_on_special=[{"name": "Chicken", "price": 8.00}],
            proteins_cheap=[],
            beef_mince_special=[],
            veges_cheap=[],
            veges_special=[],
            pantry=[],
            dairy=[],
        )
        assert data.any_data() is True

    def test_true_when_proteins_cheap(self):
        data = MarketData(
            proteins_on_special=[],
            proteins_cheap=[{"name": "Pork", "price": 10.00}],
            beef_mince_special=[],
            veges_cheap=[],
            veges_special=[],
            pantry=[],
            dairy=[],
        )
        assert data.any_data() is True

    def test_true_when_veges_cheap(self):
        data = MarketData(
            proteins_on_special=[],
            proteins_cheap=[],
            beef_mince_special=[],
            veges_cheap=[{"name": "Broccoli", "price": 2.00}],
            veges_special=[],
            pantry=[],
            dairy=[],
        )
        assert data.any_data() is True

    def test_true_when_pantry(self):
        data = MarketData(
            proteins_on_special=[],
            proteins_cheap=[],
            beef_mince_special=[],
            veges_cheap=[],
            veges_special=[],
            pantry=[{"name": "Pasta", "price": 1.50}],
            dairy=[],
        )
        assert data.any_data() is True

    def test_false_when_all_empty(self):
        data = MarketData(
            proteins_on_special=[],
            proteins_cheap=[],
            beef_mince_special=[],
            veges_cheap=[],
            veges_special=[],
            pantry=[],
            dairy=[],
        )
        assert data.any_data() is False

    def test_veges_special_alone_is_not_enough(self):
        """veges_special is not checked in any_data()."""
        data = MarketData(
            proteins_on_special=[],
            proteins_cheap=[],
            beef_mince_special=[],
            veges_cheap=[],
            veges_special=[{"name": "Capsicum", "price": 3.00}],
            pantry=[],
            dairy=[],
        )
        assert data.any_data() is False

    def test_dairy_alone_is_not_enough(self):
        """dairy is not checked in any_data()."""
        data = MarketData(
            proteins_on_special=[],
            proteins_cheap=[],
            beef_mince_special=[],
            veges_cheap=[],
            veges_special=[],
            pantry=[],
            dairy=[{"name": "Milk", "price": 3.50}],
        )
        assert data.any_data() is False

    def test_beef_mince_alone_is_not_enough(self):
        """beef_mince_special is not checked in any_data()."""
        data = MarketData(
            proteins_on_special=[],
            proteins_cheap=[],
            beef_mince_special=[{"name": "Beef mince", "price": 9.00}],
            veges_cheap=[],
            veges_special=[],
            pantry=[],
            dairy=[],
        )
        assert data.any_data() is False


class TestMarketDataToDict:
    def _empty_data(self):
        return MarketData(
            proteins_on_special=[],
            proteins_cheap=[],
            beef_mince_special=[],
            veges_cheap=[],
            veges_special=[],
            pantry=[],
            dairy=[],
        )

    def test_has_all_seven_keys(self):
        d = self._empty_data().to_dict()
        assert set(d.keys()) == {
            "proteins_on_special",
            "proteins_cheap",
            "beef_mince_special",
            "veges_cheap",
            "veges_special",
            "pantry",
            "dairy",
        }

    def test_values_are_lists(self):
        d = self._empty_data().to_dict()
        for v in d.values():
            assert isinstance(v, list)

    def test_preserves_data(self):
        chicken = {"name": "Chicken", "price": 8.00}
        data = MarketData(
            proteins_on_special=[chicken],
            proteins_cheap=[],
            beef_mince_special=[],
            veges_cheap=[],
            veges_special=[],
            pantry=[],
            dairy=[],
        )
        d = data.to_dict()
        assert d["proteins_on_special"] == [chicken]


class TestDataclasses:
    def test_ingredient_defaults(self):
        ing = Ingredient(name="Garlic", amount="2 cloves", estimatedCost=0.50)
        assert ing.fromSpecial is False
        assert ing.sharedWith == []

    def test_meal_construction(self):
        meal = Meal(
            id="r1",
            name="Chicken Stir Fry",
            serves=4,
            leftovers=True,
            cookTime="30 mins",
            description="Quick weeknight meal",
            recipeUrl="",
            ingredients=[],
            method=[],
        )
        assert meal.name == "Chicken Stir Fry"
        assert meal.serves == 4

    def test_meal_plan_construction(self):
        plan = MealPlan(
            weekSummary="5 hearty meals",
            estimatedTotal=45.50,
            meals=[],
            shoppingList=[],
        )
        assert plan.estimatedTotal == 45.50
        assert plan.meals == []
