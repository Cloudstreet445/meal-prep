"""Endpoint tests for theme-driven pantry suggestions + bulk add + settings."""


class TestMealThemesSetting:
    def test_saves_and_normalises_themes(self, client):
        resp = client.put("/api/settings/", json={"mealThemes": ["asian", "klingon", "INDIAN"]})
        assert resp.status_code == 200
        # Unknown dropped, known kept (canonical order), case-normalised.
        assert resp.json()["mealThemes"] == ["asian", "indian"]

    def test_default_is_empty_list(self, client):
        resp = client.get("/api/settings/")
        assert resp.json()["mealThemes"] == []


class TestPantrySuggestions:
    def test_suggestions_from_query_override(self, client):
        resp = client.get("/api/pantry/suggestions", params={"themes": "thai"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["themes"] == ["thai"]
        names = {s["canonical"] for s in data["suggestions"]}
        assert "fish sauce" in names
        # Nothing in pantry yet → none pre-ticked.
        assert all(s["inPantry"] is False for s in data["suggestions"])

    def test_suggestions_fall_back_to_saved_themes(self, client):
        client.put("/api/settings/", json={"mealThemes": ["italian"]})
        resp = client.get("/api/pantry/suggestions")
        data = resp.json()
        assert data["themes"] == ["italian"]
        names = {s["canonical"] for s in data["suggestions"]}
        assert "olive oil" in names

    def test_owned_items_flagged_in_pantry(self, client):
        client.post("/api/pantry/", json={"name": "Olive Oil", "canonical": "olive oil"})
        resp = client.get("/api/pantry/suggestions", params={"themes": "italian"})
        olive = next(s for s in resp.json()["suggestions"] if s["canonical"] == "olive oil")
        assert olive["inPantry"] is True


class TestPantryBulkAdd:
    def test_bulk_adds_new_items(self, client):
        resp = client.post("/api/pantry/bulk", json={"items": [
            {"name": "Soy Sauce", "canonical": "soy sauce"},
            {"name": "Rice", "canonical": "rice"},
        ]})
        assert resp.status_code == 200
        assert resp.json()["added"] == 2
        pantry = client.get("/api/pantry/").json()
        canon = {p["canonical"] for p in pantry}
        assert {"soy sauce", "rice"} <= canon

    def test_bulk_skips_existing(self, client):
        client.post("/api/pantry/", json={"name": "Rice", "canonical": "rice"})
        resp = client.post("/api/pantry/bulk", json={"items": [
            {"name": "Rice", "canonical": "rice"},
            {"name": "Ginger", "canonical": "ginger"},
        ]})
        assert resp.json()["added"] == 1  # only ginger was new
