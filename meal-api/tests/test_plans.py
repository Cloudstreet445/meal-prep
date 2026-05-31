"""Integration tests for /api/plan generation, including analytics wiring."""

from tests.conftest import TEST_USER_ID, TEST_HOUSEHOLD_ID

RECIPE = {
    "name": "Test Meal",
    "serves": 4,
    "cookTime": "20 mins",
    "costTier": "budget",
    "ingredients": [{"name": "Chicken breast", "amount": "400g"}],
    "method": ["Cook it"],
}


def _seed_recipes(db, n):
    db["recipes"].insert_many([
        {**RECIPE, "recipeId": f"r{i}", "name": f"Meal {i}",
         "primaryProtein": ["chicken", "beef", "pork", "fish", "plant"][i % 5]}
        for i in range(n)
    ])


class TestGeneratePlan:
    def test_success_emits_plan_generated_event(self, client, meals_db):
        _seed_recipes(meals_db, 8)
        resp = client.post("/api/plan/generate")
        assert resp.status_code == 200

        ev = meals_db["events"].find_one({"event": "plan_generated"})
        assert ev is not None
        assert ev["userId"] == TEST_USER_ID
        assert ev["householdId"] == TEST_HOUSEHOLD_ID
        assert "degraded" in ev["props"]

    def test_failure_emits_plan_generation_failed_event(self, client, meals_db):
        # No recipes seeded → can't build a plan → 422 + failure event.
        resp = client.post("/api/plan/generate")
        assert resp.status_code == 422

        ev = meals_db["events"].find_one({"event": "plan_generation_failed"})
        assert ev is not None
        assert ev["householdId"] == TEST_HOUSEHOLD_ID
        assert "budget" in ev["props"]
