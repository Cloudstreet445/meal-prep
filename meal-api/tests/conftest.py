import os
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test-secret")

import mongomock
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.main import app
from src.auth_utils import create_jwt

# A fixed authenticated identity used by the default `client` fixture.
TEST_USER_ID = "test-user-1"
TEST_EMAIL = "test@example.com"
TEST_SESSION_ID = "test-session-1"
TEST_HOUSEHOLD_ID = "test-household-1"


@pytest.fixture
def meals_db():
    return mongomock.MongoClient()["paknsave-meals"]


@pytest.fixture
def pricing_db():
    return mongomock.MongoClient()["paknsave-pricing"]


@pytest.fixture
def client(meals_db, pricing_db):
    """Authenticated test client.

    Seeds a user + household + session and attaches a valid JWT cookie, so
    endpoints behind `require_user` work and bundle/plan queries resolve to
    TEST_HOUSEHOLD_ID. `src.database.get_db` is patched too because
    `require_user` reads the session through it (not the per-router get_db)."""
    meals_db["users"].insert_one({
        "userId": TEST_USER_ID,
        "email": TEST_EMAIL,
        "householdId": TEST_HOUSEHOLD_ID,
    })
    meals_db["sessions"].insert_one({
        "sessionId": TEST_SESSION_ID,
        "userId": TEST_USER_ID,
    })
    token = create_jwt(TEST_USER_ID, TEST_EMAIL, TEST_SESSION_ID)

    with patch("src.database.get_db", return_value=meals_db), \
         patch("src.routers.bundles.get_db", return_value=meals_db), \
         patch("src.routers.bundles.get_pricing_db", return_value=pricing_db), \
         patch("src.routers.shopping.get_db", return_value=meals_db), \
         patch("src.routers.shopping.get_pricing_db", return_value=pricing_db), \
         patch("src.routers.plans.get_db", return_value=meals_db), \
         patch("src.routers.plans.get_pricing_db", return_value=pricing_db), \
         patch("src.routers.recipes.get_db", return_value=meals_db), \
         patch("src.routers.settings.get_db", return_value=meals_db), \
         patch("src.routers.pantry.get_db", return_value=meals_db), \
         patch("src.routers.substitutions.get_pricing_db", return_value=pricing_db), \
         patch("src.routers.enhancements.get_db", return_value=meals_db):
        c = TestClient(app)
        c.cookies.set("access_token", token)
        yield c


@pytest.fixture
def anon_client(meals_db, pricing_db):
    """Unauthenticated client — for asserting auth is actually required."""
    with patch("src.database.get_db", return_value=meals_db), \
         patch("src.routers.bundles.get_db", return_value=meals_db), \
         patch("src.routers.bundles.get_pricing_db", return_value=pricing_db), \
         patch("src.routers.shopping.get_db", return_value=meals_db), \
         patch("src.routers.shopping.get_pricing_db", return_value=pricing_db), \
         patch("src.routers.plans.get_db", return_value=meals_db), \
         patch("src.routers.plans.get_pricing_db", return_value=pricing_db), \
         patch("src.routers.recipes.get_db", return_value=meals_db), \
         patch("src.routers.settings.get_db", return_value=meals_db), \
         patch("src.routers.pantry.get_db", return_value=meals_db), \
         patch("src.routers.substitutions.get_pricing_db", return_value=pricing_db), \
         patch("src.routers.enhancements.get_db", return_value=meals_db):
        yield TestClient(app)
