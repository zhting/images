"""P1a data-layer refactor tests: photos table, migration, timeline API."""
import pytest


def _rows(n=0, **overrides):
    """Helper building photo metadata rows in VectorDB's output shape."""
    base = [
        {"file_path": "/pics/2024/a.jpg", "captured_time": 1710000000,
         "last_modified": 1710000000, "tag": "photo", "aesthetic_score": 0.5,
         "location_info": {"city": "Hangzhou", "province": "Zhejiang",
                           "country_code": "CN", "latitude": 30.2, "longitude": 120.1},
         "auto_tags": ["lake", "sunset"]},
        {"file_path": "C:\\pics\\2024\\b.jpg", "captured_time": 1712000000,
         "last_modified": 1712000000, "tag": "photo", "aesthetic_score": 0.9,
         "location_info": {}, "auto_tags": []},
        {"file_path": "/pics/2023/c.jpg", "captured_time": 1680000000,
         "last_modified": 1680000000, "tag": "photo", "aesthetic_score": 0.1,
         "location_info": {}, "auto_tags": []},
        {"file_path": "/pics/doc.png", "captured_time": 1711000000,
         "last_modified": 1711000000, "tag": "document", "aesthetic_score": 0.0,
         "location_info": {}, "auto_tags": []},
        {"file_path": "/locked/secret.jpg", "captured_time": 1713000000,
         "last_modified": 1713000000, "tag": "photo", "aesthetic_score": 0.3,
         "location_info": {}, "auto_tags": []},
    ]
    return base[:n] if n else base


class TestPhotosTable:
    def test_upsert_is_idempotent(self, sqlite_store):
        assert sqlite_store.upsert_photos(_rows()) == 5
        sqlite_store.upsert_photos(_rows())
        assert sqlite_store.count_photos() == 5

    def test_path_normalization(self, sqlite_store):
        sqlite_store.upsert_photos(_rows())
        details = sqlite_store.get_photos_by_paths(["C:\\pics\\2024\\b.jpg"])
        assert "C:/pics/2024/b.jpg" in details

    def test_upsert_preserves_location_on_partial_update(self, sqlite_store):
        sqlite_store.upsert_photos(_rows())
        # Re-index without location info (e.g. sync rewrite)
        sqlite_store.upsert_photos([{
            "file_path": "/pics/2024/a.jpg", "captured_time": 1710000000,
            "last_modified": 1710000001, "tag": "photo"}])
        d = sqlite_store.get_photos_by_paths(["/pics/2024/a.jpg"])["/pics/2024/a.jpg"]
        assert d["location_info"]["city"] == "Hangzhou"

    def test_timeline_page_order_and_hidden_tags(self, sqlite_store):
        sqlite_store.upsert_photos(_rows())
        items, total = sqlite_store.get_timeline_page(10, 0)
        paths = [i["file_path"] for i in items]
        assert total == 4  # document excluded
        assert paths == sorted(paths, key=lambda p: -[r for r in _rows()
                               if sqlite_store.norm_path(r["file_path"]) == p][0]["captured_time"])
        assert all("/doc.png" not in p for p in paths)

    def test_timeline_pagination(self, sqlite_store):
        sqlite_store.upsert_photos(_rows())
        page1, total = sqlite_store.get_timeline_page(2, 0)
        page2, _ = sqlite_store.get_timeline_page(2, 2)
        assert total == 4 and len(page1) == 2 and len(page2) == 2
        assert {i["file_path"] for i in page1}.isdisjoint(
            {i["file_path"] for i in page2})

    def test_locked_prefix_excluded_from_page_and_total(self, sqlite_store):
        sqlite_store.upsert_photos(_rows())
        items, total = sqlite_store.get_timeline_page(10, 0, locked_prefixes=["/locked"])
        assert total == 3
        assert all(not i["file_path"].startswith("/locked/") for i in items)

    def test_dates_buckets_with_cumulative_index(self, sqlite_store):
        sqlite_store.upsert_photos(_rows())
        dates = sqlite_store.get_timeline_dates()
        assert sum(d["count"] for d in dates) == 4
        # cumulative index consistency
        acc = 0
        for d in dates:
            assert d["index"] == acc
            acc += d["count"]

    def test_trash_restore_roundtrip(self, sqlite_store):
        sqlite_store.upsert_photos(_rows())
        sqlite_store.trash_photo("/pics/2024/a.jpg")
        assert sqlite_store.get_timeline_page(10, 0)[1] == 3
        sqlite_store.restore_photo("/pics/2024/a.jpg")
        d = sqlite_store.get_photos_by_paths(["/pics/2024/a.jpg"])["/pics/2024/a.jpg"]
        assert d["tag"] == "photo"
        assert sqlite_store.get_timeline_page(10, 0)[1] == 4

    def test_update_location_partial(self, sqlite_store):
        sqlite_store.upsert_photos(_rows())
        sqlite_store.update_photo_location("/pics/2023/c.jpg", {"city": "Suzhou"})
        d = sqlite_store.get_photos_by_paths(["/pics/2023/c.jpg"])["/pics/2023/c.jpg"]
        assert d["location_info"]["city"] == "Suzhou"


class TestMigration:
    class FakeVectorDB:
        def __init__(self, files):
            self._files = files

        def get_all_files_with_time(self, include_embeddings=False):
            return self._files

        def count(self):
            return len(self._files)

    def test_migrate_copies_all_rows(self, sqlite_store):
        from core.migrate import migrate_photos_metadata
        n = migrate_photos_metadata(self.FakeVectorDB(_rows()), sqlite_store)
        assert n == 5 and sqlite_store.count_photos() == 5

    def test_maybe_migrate_runs_once(self, sqlite_store):
        from core.migrate import maybe_migrate
        db = self.FakeVectorDB(_rows())
        assert maybe_migrate(db, sqlite_store) is True
        assert maybe_migrate(db, sqlite_store) is False  # photos populated
        assert sqlite_store.count_photos() == 5

    def test_maybe_migrate_skips_empty_collection(self, sqlite_store):
        from core.migrate import maybe_migrate
        assert maybe_migrate(self.FakeVectorDB([]), sqlite_store) is False


class TestTimelineAPI:
    def test_timeline_reads_from_photos_table(self, app_client, sqlite_store):
        sqlite_store.upsert_photos(_rows())
        resp = app_client.get("/timeline", params={"page": 1, "size": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) <= 3
        assert all(i["tag"] != "document" for i in data["items"])

    def test_timeline_dates_from_photos_table(self, app_client, sqlite_store):
        sqlite_store.upsert_photos(_rows())
        resp = app_client.get("/timeline/dates")
        assert resp.status_code == 200
        dates = resp.json()
        assert sum(d["count"] for d in dates) == 4

    def test_timeline_respects_locked_folders(self, app_client, sqlite_store):
        sqlite_store.upsert_photos(_rows())
        app_client.post("/privacy/set_password", json={"password": "pw"})
        app_client.post("/privacy/lock", json={"path": "/locked"})
        data = app_client.get("/timeline", params={"page": 1, "size": 10}).json()
        assert data["total"] == 3
        assert all(not i["file_path"].startswith("/locked/") for i in data["items"])
