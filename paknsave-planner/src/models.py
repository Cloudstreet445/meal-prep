"""Data models for the meal planner."""

from dataclasses import dataclass, field
from typing import Optional



@dataclass
class MarketData:
    """Aggregated market data passed to Claude."""
    proteins_on_special: list
    proteins_cheap: list
    beef_mince_special: list
    veges_cheap: list
    veges_special: list
    pantry: list
    dairy: list

    def any_data(self) -> bool:
        """Returns True if at least one category has data."""
        return any([
            self.proteins_on_special,
            self.proteins_cheap,
            self.veges_cheap,
            self.pantry,
        ])

    def to_dict(self) -> dict:
        return {
            "proteins_on_special": self.proteins_on_special,
            "proteins_cheap":      self.proteins_cheap,
            "beef_mince_special":  self.beef_mince_special,
            "veges_cheap":         self.veges_cheap,
            "veges_special":       self.veges_special,
            "pantry":              self.pantry,
            "dairy":               self.dairy,
        }


@dataclass
class Ingredient:
    """An ingredient in a meal."""
    name: str
    amount: str
    estimatedCost: float
    fromSpecial: bool = False
    sharedWith: list = field(default_factory=list)


@dataclass
class Meal:
    """A single meal in the plan."""
    id: str
    name: str
    serves: int
    leftovers: bool
    cookTime: str
    description: str
    recipeUrl: str
    ingredients: list
    method: list


@dataclass
class ShoppingItem:
    """A line item on the shopping list."""
    name: str
    amount: str
    estimatedCost: float
    isSpecial: bool
    usedIn: list


@dataclass
class MealPlan:
    """The full weekly meal plan."""
    weekSummary: str
    estimatedTotal: float
    meals: list
    shoppingList: list
