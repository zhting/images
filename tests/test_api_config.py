"""API integration tests for config endpoints."""
import pytest


class TestConfigAPI:
    def test_get_config(self, app_client):
        resp = app_client.get("/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "db_path" in data
        assert "model_name" in data

    def test_update_config(self, app_client):
        resp = app_client.post("/config", json={"key": "top_k", "value": "20"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_get_wishlist_empty(self, app_client):
        resp = app_client.get("/config/wishlist")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_set_and_get_wishlist(self, app_client):
        wishlist = [{"name": "Paris", "visited": False}]
        resp = app_client.post("/config/wishlist", json={"wishlist": wishlist})
        assert resp.status_code == 200

        resp = app_client.get("/config/wishlist")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["name"] == "Paris"

    def test_world_wishlist(self, app_client):
        resp = app_client.get("/config/world_wishlist")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
