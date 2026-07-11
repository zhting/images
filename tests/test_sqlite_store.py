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
