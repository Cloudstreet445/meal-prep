import os
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

import mongomock
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def meals_db():
    return mongomock.MongoClient()["paknsave-meals"]


@pytest.fixture
def pricing_db():
    return mongomock.MongoClient()["paknsave-pricing"]


@pytest.fixture
def client(meals_db, pricing_db):
    with patch("src.routers.bundles.get_db", return_value=meals_db), \
         patch("src.routers.bundles.get_pricing_db", return_value=pricing_db), \
         patch("src.routers.shopping.get_db", return_value=meals_db), \
         patch("src.routers.shopping.get_pricing_db", return_value=pricing_db), \
         patch("src.routers.recipes.get_db", return_value=meals_db):
        yield TestClient(app)
