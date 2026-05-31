"""Tests for analytics.track and the metrics aggregations."""

from datetime import datetime, timedelta

import mongomock
import pytest

from src import analytics, metrics
from src.analytics import track, USER_REGISTERED, PLAN_GENERATED, PLAN_GENERATION_FAILED


@pytest.fixture
def db():
    return mongomock.MongoClient()["paknsave-meals"]


class TestTrack:
    def test_records_known_event(self, db):
        track(db, USER_REGISTERED, user_id="u1", household_id="h1")
        doc = db["events"].find_one({"event": USER_REGISTERED})
        assert doc["userId"] == "u1"
        assert doc["householdId"] == "h1"
        assert "ts" in doc and doc["props"] == {}

    def test_stores_props(self, db):
        track(db, PLAN_GENERATED, user_id="u1", props={"recipeCount": 5, "degraded": False})
        doc = db["events"].find_one({"event": PLAN_GENERATED})
        assert doc["props"]["recipeCount"] == 5

    def test_unknown_event_dropped(self, db):
        track(db, "definitely_not_an_event", user_id="u1")
        assert db["events"].count_documents({}) == 0

    def test_never_raises_on_failure(self):
        class Boom:
            def __getitem__(self, _):
                raise RuntimeError("db down")
        # Must swallow the error — analytics can't break a user request.
        track(Boom(), USER_REGISTERED, user_id="u1")


class TestMetrics:
    def test_query_derived_counts(self, db):
        now = datetime.utcnow()
        db["users"].insert_many([
            {"userId": "u1", "createdAt": now},
            {"userId": "u2", "createdAt": now - timedelta(days=40)},  # outside 30d
        ])
        db["sessions"].insert_one({"userId": "u1", "lastSeenAt": now})
        db["bundles"].insert_one({"bundleId": "b1", "createdAt": now})

        assert metrics.signups(db, 30) == 1
        assert metrics.active_users(db, 7) == 1
        assert metrics.plans_generated(db, 7) == 1
        assert metrics.total_users(db) == 2

    def test_activation_rate(self, db):
        now = datetime.utcnow()
        # u1 registers and generates a plan next day → activated
        track(db, USER_REGISTERED, user_id="u1")
        db["events"].insert_one({"event": PLAN_GENERATED, "userId": "u1",
                                 "ts": now + timedelta(days=1), "props": {}})
        # u2 registers, never generates → not activated
        track(db, USER_REGISTERED, user_id="u2")

        result = metrics.activation_rate(db, days=30, window_days=7)
        assert result["cohort"] == 2
        assert result["activated"] == 1
        assert result["rate"] == 0.5

    def test_activation_rate_empty_cohort(self, db):
        result = metrics.activation_rate(db)
        assert result["cohort"] == 0
        assert result["rate"] is None

    def test_plan_generation_health(self, db):
        track(db, PLAN_GENERATED, user_id="u1", props={"degraded": False})
        track(db, PLAN_GENERATED, user_id="u2", props={"degraded": True})
        track(db, PLAN_GENERATION_FAILED, user_id="u3", props={"budget": 10})

        h = metrics.plan_generation_health(db, 7)
        assert h["succeeded"] == 1
        assert h["degraded"] == 1
        assert h["failed"] == 1
        assert h["attempts"] == 3
        assert h["failureRate"] == round(1 / 3, 3)

    def test_summary_shape(self, db):
        s = metrics.summary(db)
        assert set(s) == {"generatedAt", "totals", "signups30d", "activeUsers7d",
                          "plansGenerated7d", "activation", "planHealth7d"}
