"""Tests for SQLiteStore — config, privacy, and asset path management."""


class TestSQLiteStoreConfig:
    """Configuration get/set operations."""

    def test_set_and_get_config(self, sqlite_store):
        sqlite_store.set_config("test_key", "test_value")
        assert sqlite_store.get_config("test_key") == "test_value"

    def test_get_config_default(self, sqlite_store):
        result = sqlite_store.get_config("nonexistent", "default_val")
        assert result == "default_val"

    def test_set_config_overwrite(self, sqlite_store):
        sqlite_store.set_config("key", "v1")
        sqlite_store.set_config("key", "v2")
        assert sqlite_store.get_config("key") == "v2"

    def test_asset_paths(self, sqlite_store):
        sqlite_store.set_config("asset_paths", '["C:/Photos","D:/Backup"]')
        paths = sqlite_store.get_asset_paths()
        assert isinstance(paths, list)
        assert len(paths) == 2


class TestSQLiteStorePrivacy:
    """Privacy password and folder locking."""

    def test_no_password_initially(self, sqlite_store):
        assert sqlite_store.is_privacy_password_set() is False

    def test_set_and_verify_password(self, sqlite_store):
        sqlite_store.set_privacy_password("secret123")
        assert sqlite_store.is_privacy_password_set() is True
        assert sqlite_store.verify_privacy_password("secret123") is True
        assert sqlite_store.verify_privacy_password("wrong") is False

    def test_locked_folders(self, sqlite_store):
        sqlite_store.set_privacy_password("pass")
        sqlite_store.add_locked_folder("C:/Photos/private")
        folders = sqlite_store.get_locked_folders()
        assert "C:/Photos/private" in folders

    def test_unlock_folder(self, sqlite_store):
        sqlite_store.set_privacy_password("pass")
        sqlite_store.add_locked_folder("C:/Photos/private")
        sqlite_store.remove_locked_folder("C:/Photos/private")
        folders = sqlite_store.get_locked_folders()
        assert "C:/Photos/private" not in folders

    def test_is_path_locked(self, sqlite_store):
        locked = ["C:/Photos/private"]
        assert sqlite_store.is_path_locked("C:/Photos/private/img.jpg", locked) is True
        assert sqlite_store.is_path_locked("C:/Photos/public/img.jpg", locked) is False


class TestWalCheckpoint:
    """WAL mode keeps recent commits in a sidecar file.

    Without a checkpoint the .db file on its own can be missing every
    table, so anything that copies it (the db-sync script, a backup) must
    happen after one — hence checkpoint() and close().
    """

    def _copy_probe(self, store, tmp_path, name):
        """Copy just the .db file, as a naive backup would, and read it."""
        import shutil
        import sqlite3
        dest = str(tmp_path / name)
        shutil.copyfile(store.db_path, dest)
        conn = sqlite3.connect(dest)
        try:
            return conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0]
        finally:
            conn.close()

    def test_runs_in_wal_mode(self, sqlite_store):
        with sqlite_store._get_conn() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"

    def test_checkpoint_makes_the_db_file_self_contained(self, sqlite_store, tmp_path):
        sqlite_store.upsert_photos([{"file_path": f"/p/{i}.jpg"} for i in range(200)])

        assert sqlite_store.checkpoint() is True
        assert self._copy_probe(sqlite_store, tmp_path, "after.db") == 200

    def test_checkpoint_is_idempotent(self, sqlite_store):
        sqlite_store.upsert_photos([{"file_path": "/p/a.jpg"}])
        assert sqlite_store.checkpoint() is True
        assert sqlite_store.checkpoint() is True

    def test_close_checkpoints_then_closes(self, sqlite_store, tmp_path):
        sqlite_store.upsert_photos([{"file_path": f"/p/{i}.jpg"} for i in range(50)])

        sqlite_store.close()

        assert self._copy_probe(sqlite_store, tmp_path, "closed.db") == 50

    def test_close_twice_does_not_raise(self, sqlite_store):
        sqlite_store.close()
        sqlite_store.close()
