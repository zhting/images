"""Security regression tests: path guard + privacy session tokens.

These lock in the fixes for:
- arbitrary file read via /files/content and /files/thumbnail
- locked-folder enforcement on file serving
- session-token flow replacing per-request passwords
"""
import os
import pytest
from PIL import Image


@pytest.fixture
def photo_root(tmp_path, sqlite_store):
    """A configured photo root containing one real photo, plus a secret
    file OUTSIDE the root that must never be servable."""
    root = tmp_path / "photos"
    root.mkdir()
    photo = root / "cat.jpg"
    Image.new("RGB", (32, 32), color=(120, 60, 30)).save(photo)

    secret = tmp_path / "secret.txt"
    secret.write_text("api-key=hunter2")

    sqlite_store.add_asset_path(str(root))
    return {"root": root, "photo": photo, "secret": secret}


class TestPathGuard:
    def test_serves_photo_inside_root(self, app_client, photo_root):
        resp = app_client.get("/files/content", params={"path": str(photo_root["photo"])})
        assert resp.status_code == 200

    def test_rejects_file_outside_root(self, app_client, photo_root):
        resp = app_client.get("/files/content", params={"path": str(photo_root["secret"])})
        assert resp.status_code == 403

    def test_rejects_traversal(self, app_client, photo_root):
        sneaky = str(photo_root["root"]) + "/../secret.txt"
        resp = app_client.get("/files/content", params={"path": sneaky})
        assert resp.status_code == 403
        # Prove the traversal target actually exists — the guard, not a
        # 404, is what blocked it.
        assert os.path.exists(os.path.realpath(sneaky))

    def test_rejects_system_file(self, app_client, photo_root):
        resp = app_client.get("/files/content", params={"path": "/etc/passwd"})
        assert resp.status_code == 403

    def test_thumbnail_guarded_too(self, app_client, photo_root):
        resp = app_client.get("/files/thumbnail", params={"path": str(photo_root["secret"])})
        assert resp.status_code == 403

    def test_no_roots_configured_denies_everything(self, app_client, tmp_path):
        f = tmp_path / "a.jpg"
        Image.new("RGB", (8, 8)).save(f)
        resp = app_client.get("/files/content", params={"path": str(f)})
        assert resp.status_code == 403

    def test_thumbnail_never_returns_original(self, app_client, photo_root, monkeypatch):
        """If thumbnail generation fails, we must get a placeholder —
        never the original file bytes."""
        from core.thumbnails import thumbnail_service
        monkeypatch.setattr(thumbnail_service, "get_thumbnail", lambda p, **kw: None)
        resp = app_client.get("/files/thumbnail", params={"path": str(photo_root["photo"])})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/svg")


class TestPrivacySessions:
    def _lock_photo_folder(self, app_client, photo_root, password="pw123"):
        app_client.post("/privacy/set_password", json={"password": password})
        app_client.post("/privacy/lock", json={"path": str(photo_root["root"])})

    def test_locked_content_denied_without_token(self, app_client, photo_root):
        self._lock_photo_folder(app_client, photo_root)
        resp = app_client.get("/files/content", params={"path": str(photo_root["photo"])})
        assert resp.status_code == 403

    def test_verify_returns_session_token(self, app_client, photo_root):
        self._lock_photo_folder(app_client, photo_root)
        resp = app_client.post("/privacy/verify", json={"password": "pw123"})
        assert resp.status_code == 200
        assert resp.json().get("session_token")

    def test_token_unlocks_via_header(self, app_client, photo_root):
        self._lock_photo_folder(app_client, photo_root)
        token = app_client.post(
            "/privacy/verify", json={"password": "pw123"}
        ).json()["session_token"]
        resp = app_client.get(
            "/files/content",
            params={"path": str(photo_root["photo"])},
            headers={"X-Privacy-Token": token},
        )
        assert resp.status_code == 200

    def test_token_unlocks_via_query_param(self, app_client, photo_root):
        """<img> tags cannot send headers; token query param must work."""
        self._lock_photo_folder(app_client, photo_root)
        token = app_client.post(
            "/privacy/verify", json={"password": "pw123"}
        ).json()["session_token"]
        resp = app_client.get(
            "/files/content",
            params={"path": str(photo_root["photo"]), "token": token},
        )
        assert resp.status_code == 200

    def test_bogus_token_rejected(self, app_client, photo_root):
        self._lock_photo_folder(app_client, photo_root)
        resp = app_client.get(
            "/files/content",
            params={"path": str(photo_root["photo"])},
            headers={"X-Privacy-Token": "not-a-real-token"},
        )
        assert resp.status_code == 403

    def test_password_change_invalidates_sessions(self, app_client, photo_root):
        self._lock_photo_folder(app_client, photo_root)
        token = app_client.post(
            "/privacy/verify", json={"password": "pw123"}
        ).json()["session_token"]
        app_client.post(
            "/privacy/set_password",
            json={"password": "newpw456", "old_password": "pw123"},
        )
        resp = app_client.get(
            "/files/content",
            params={"path": str(photo_root["photo"])},
            headers={"X-Privacy-Token": token},
        )
        assert resp.status_code == 403


class TestContentCaching:
    def test_etag_conditional_request(self, app_client, photo_root):
        first = app_client.get("/files/content", params={"path": str(photo_root["photo"])})
        assert first.status_code == 200
        etag = first.headers.get("etag")
        assert etag
        second = app_client.get(
            "/files/content",
            params={"path": str(photo_root["photo"])},
            headers={"If-None-Match": etag},
        )
        assert second.status_code == 304
