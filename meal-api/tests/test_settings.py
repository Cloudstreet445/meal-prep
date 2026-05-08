"""Endpoint tests for /api/settings."""


class TestGetSettings:
    def test_returns_defaults_when_no_settings(self, client):
        resp = client.get("/api/settings/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["budget"] == 60.0
        assert data["serves"] == 2
        assert data["exclusions"] == []

    def test_returns_saved_settings(self, client, meals_db):
        meals_db["settings"].insert_one({"key": "default", "budget": 80.0, "serves": 4, "exclusions": ["mushroom"]})
        resp = client.get("/api/settings/")
        data = resp.json()
        assert data["budget"] == 80.0
        assert data["serves"] == 4
        assert data["exclusions"] == ["mushroom"]


class TestUpdateSettings:
    def test_updates_budget(self, client):
        resp = client.put("/api/settings/", json={"budget": 80.0})
        assert resp.status_code == 200
        assert resp.json()["budget"] == 80.0

    def test_updates_serves(self, client):
        resp = client.put("/api/settings/", json={"serves": 4})
        assert resp.json()["serves"] == 4

    def test_updates_exclusions(self, client):
        resp = client.put("/api/settings/", json={"exclusions": ["mushroom", "seafood"]})
        assert resp.json()["exclusions"] == ["mushroom", "seafood"]

    def test_partial_update_preserves_other_fields(self, client):
        client.put("/api/settings/", json={"budget": 80.0})
        resp = client.put("/api/settings/", json={"serves": 4})
        data = resp.json()
        assert data["budget"] == 80.0
        assert data["serves"] == 4

    def test_empty_body_returns_current_settings(self, client):
        client.put("/api/settings/", json={"budget": 75.0})
        resp = client.put("/api/settings/", json={})
        assert resp.json()["budget"] == 75.0

    def test_returns_full_settings_after_update(self, client):
        resp = client.put("/api/settings/", json={"budget": 55.0})
        data = resp.json()
        assert "budget" in data
        assert "serves" in data
        assert "exclusions" in data
