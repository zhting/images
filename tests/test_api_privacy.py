"""API integration tests for privacy endpoints."""


class TestPrivacyAPI:
    def test_privacy_status_initial(self, app_client):
        resp = app_client.get("/privacy/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_password"] is False

    def test_set_password(self, app_client):
        resp = app_client.post("/privacy/set_password", json={"password": "mypass123"})
        assert resp.status_code == 200

        resp = app_client.get("/privacy/status")
        assert resp.json()["has_password"] is True

    def test_verify_password_correct(self, app_client):
        app_client.post("/privacy/set_password", json={"password": "secret"})
        resp = app_client.post("/privacy/verify", json={"password": "secret"})
        assert resp.status_code == 200
        assert resp.json()["verified"] is True

    def test_verify_password_wrong(self, app_client):
        app_client.post("/privacy/set_password", json={"password": "secret"})
        resp = app_client.post("/privacy/verify", json={"password": "wrong"})
        assert resp.status_code == 403

    def test_lock_folder_without_password(self, app_client):
        # No password set in this fresh fixture -> should fail
        resp = app_client.post("/privacy/lock", json={"path": "C:/Private"})
        assert resp.status_code == 400

    def test_lock_and_unlock_folder(self, app_client):
        app_client.post("/privacy/set_password", json={"password": "pass"})
        resp = app_client.post("/privacy/lock", json={"path": "C:/Private"})
        assert resp.status_code == 200

        status = app_client.get("/privacy/status").json()
        assert "C:/Private" in status["locked_folders"]

        resp = app_client.post("/privacy/unlock", json={"path": "C:/Private"})
        assert resp.status_code == 200

        status = app_client.get("/privacy/status").json()
        assert "C:/Private" not in status["locked_folders"]
