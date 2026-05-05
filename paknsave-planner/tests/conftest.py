import os
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGO_DB", "paknsave-pricing")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import mongomock
import pytest


@pytest.fixture
def mongo_client():
    return mongomock.MongoClient()


@pytest.fixture
def pricing_db(mongo_client):
    return mongo_client["paknsave-pricing"]


@pytest.fixture
def meals_db(mongo_client):
    return mongo_client["paknsave-meals"]


@pytest.fixture
def products_col(pricing_db):
    return pricing_db["products"]
