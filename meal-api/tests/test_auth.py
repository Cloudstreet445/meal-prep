"""Endpoint tests for /api/auth — password auth, sessions, reset, revocation."""

import pytest
from unittest.mock import patch
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from src.main import app
from src.limiter import limiter


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """slowapi's limiter keeps in-memory counters that otherwise bleed across
    tests (register is 5/min), so clear them before each test."""
    try:
        limiter._storage.reset()
    except Exception:
        pass
    yield


@pytest.fixture
def auth_db(meals_db):
    """Patch every get_db the auth flow touches at the same mongomock db."""
    with patch("src.database.get_db", return_value=meals_db), \
         patch("src.routers.auth.get_db", return_value=meals_db):
        yield meals_db


@pytest.fixture
def auth_client(auth_db):
    return TestClient(app), auth_db


def _register(client, email="alice@example.com", password="hunter2hunter2"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


class TestRegisterLogin:
    def test_register_then_login(self, auth_client):
        client, _ = auth_client
        r = _register(client)
        assert r.status_code == 200
        assert r.json()["email"] == "alice@example.com"

        r = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "hunter2hunter2"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_login_wrong_password(self, auth_client):
        client, _ = auth_client
        _register(client)
        r = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrongwrongwrong"})
        assert r.status_code == 401

    def test_login_unknown_email_is_401_not_500(self, auth_client):
        """Missing account runs the dummy-hash compare path and returns 401
        (the timing-equalisation fix must not crash on a None hash)."""
        client, _ = auth_client
        r = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever12345"})
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid email or password"

    def test_register_short_password_rejected(self, auth_client):
        client, _ = auth_client
        r = _register(client, password="short")
        assert r.status_code == 400

    def test_oversized_password_rejected_by_model(self, auth_client):
        client, _ = auth_client
        r = _register(client, password="x" * 2000)
        assert r.status_code == 422


class TestPasswordReset:
    def test_forgot_invalidates_prior_tokens(self, auth_client):
        client, db = auth_client
        _register(client)
        client.post("/api/auth/forgot-password", json={"email": "alice@example.com"})
        client.post("/api/auth/forgot-password", json={"email": "alice@example.com"})
        tokens = list(db["password_reset_tokens"].find({"email": "alice@example.com"}))
        unused = [t for t in tokens if not t["used"]]
        assert len(tokens) == 2
        assert len(unused) == 1  # only the most recent remains usable

    def test_reset_consumes_token_once(self, auth_client):
        client, db = auth_client
        _register(client)
        client.post("/api/auth/forgot-password", json={"email": "alice@example.com"})
        token = db["password_reset_tokens"].find_one({"used": False})["token"]

        r = client.post("/api/auth/reset-password", json={"token": token, "password": "newpassword123"})
        assert r.status_code == 200
        # Second use of the same token must fail (atomic single-use).
        r = client.post("/api/auth/reset-password", json={"token": token, "password": "another123456"})
        assert r.status_code == 400

    def test_reset_with_bad_token(self, auth_client):
        client, _ = auth_client
        r = client.post("/api/auth/reset-password", json={"token": "nope", "password": "newpassword123"})
        assert r.status_code == 400


class TestSessionRevocation:
    def test_get_current_user_rejects_revoked_session(self, auth_client):
        """After the session row is deleted, a still-valid JWT must no longer
        authenticate on get_current_user endpoints (e.g. /me)."""
        from src.auth_utils import create_jwt
        client, db = auth_client
        reg = _register(client).json()
        # Set the auth cookie explicitly — the real cookie is secure=True and so
        # isn't persisted by the test client over plain HTTP.
        token = create_jwt(reg["userId"], reg["email"], reg["sessionId"])
        client.cookies.set("access_token", token)

        # /me works while the session is live
        assert client.get("/api/auth/me").status_code == 200

        # Revoke the session server-side (as "log out all devices" does)
        db["sessions"].delete_many({"userId": reg["userId"]})

        assert client.get("/api/auth/me").status_code == 401


class TestMagicLinkRemoved:
    def test_send_magic_link_gone(self, auth_client):
        client, _ = auth_client
        assert client.post("/api/auth/send-magic-link", json={"email": "a@b.com"}).status_code == 404

    def test_verify_gone(self, auth_client):
        client, _ = auth_client
        assert client.get("/api/auth/verify?token=x").status_code == 404
