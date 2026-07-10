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


class TestOrganizeAPIsStage2:
    """P1a stage 2: organize-domain routes served from the photos table."""

    @pytest.fixture(autouse=True)
    def seed(self, sqlite_store):
        import datetime
        today = datetime.datetime.now().replace(hour=12, minute=0, second=0)
        last_year_today = today.replace(year=today.year - 1)
        sqlite_store.upsert_photos(_rows() + [{
            "file_path": "/pics/anniversary.jpg",
            "captured_time": last_year_today.timestamp(),
            "last_modified": 1, "tag": "photo",
            "location_info": {"city": "Hangzhou", "province": "Zhejiang",
                              "latitude": 30.25, "longitude": 120.15},
            "auto_tags": ["lake"]}])
        self.store = sqlite_store

    def test_documents_paged(self, app_client):
        data = app_client.get("/files/organize/documents",
                              params={"page": 1, "page_size": 10}).json()
        assert data["total"] == 1
        assert data["items"][0]["file_path"].endswith("doc.png")

    def test_places_summary(self, app_client):
        places = app_client.get("/files/organize/places").json()
        hz = next(p for p in places if p["city"] == "Hangzhou")
        assert hz["count"] == 2
        assert hz["cover"]["file_path"]  # newest file as cover
        assert hz["latitude"] == pytest.approx(30.225, abs=0.01)

    def test_map_points(self, app_client):
        pts = app_client.get("/files/organize/places/all_map_data").json()
        assert len(pts) == 2
        assert all(p["latitude"] is not None for p in pts)

    def test_place_photos(self, app_client):
        photos = app_client.get("/files/organize/places/Hangzhou, Zhejiang").json()
        assert len(photos) == 2
        times = [p["captured_time"] for p in photos]
        assert times == sorted(times, reverse=True)

    def test_on_this_day_groups_by_year(self, app_client):
        groups = app_client.get("/files/organize/on_this_day").json()
        assert any(g["photos"] for g in groups)
        assert any(p["file_path"].endswith("anniversary.jpg")
                   for g in groups for p in g["photos"])

    def test_tags_counts(self, app_client):
        data = app_client.get("/files/organize/tags").json()
        by_name = {t["name"]: t["count"] for t in data["items"]}
        assert by_name.get("lake") == 2 and by_name.get("sunset") == 1

    def test_tag_photos_exact_match_no_substring_collision(self, app_client):
        # 'lake' must not match a hypothetical 'lakeside'
        self.store.upsert_photos([{
            "file_path": "/pics/x.jpg", "captured_time": 5, "last_modified": 1,
            "tag": "photo", "auto_tags": ["lakeside"]}])
        photos = app_client.get("/files/organize/tags/lake").json()
        assert len(photos) == 2
        assert all("x.jpg" not in p["file_path"] for p in photos)

    def test_locked_folder_excluded_from_places(self, app_client):
        self.store.upsert_photos([{
            "file_path": "/locked/l.jpg", "captured_time": 9, "last_modified": 1,
            "tag": "photo",
            "location_info": {"city": "Secret", "province": "P"}}])
        app_client.post("/privacy/set_password", json={"password": "pw"})
        app_client.post("/privacy/lock", json={"path": "/locked"})
        places = app_client.get("/files/organize/places").json()
        assert all(p["city"] != "Secret" for p in places)

    def test_browse_roots_count(self, app_client):
        self.store.add_asset_path("/pics")
        data = app_client.get("/files/browse_dir").json()
        root = next(d for d in data["directories"] if d["path"] == "/pics")
        # /pics holds a.jpg, c.jpg, anniversary.jpg (doc.png excluded;
        # b.jpg normalizes to C:/pics/... which is a different root)
        assert root["count"] == 3

    def test_browse_dir_listing_from_subtree(self, app_client):
        self.store.add_asset_path("/pics")
        data = app_client.get("/files/browse_dir", params={"path": "/pics"}).json()
        names = {d["name"] for d in data["directories"]}
        assert "2024" in names and "2023" in names
        assert all(f["tag"] != "document" for f in data["files"])


class TestStage3Cleanup:
    def test_sync_states_map(self, sqlite_store):
        sqlite_store.upsert_photos(_rows())
        states = sqlite_store.get_photo_sync_states()
        assert len(states) == 5
        assert states["/pics/2024/a.jpg"] == 1710000000
        # normalized key for the Windows-style path
        assert "C:/pics/2024/b.jpg" in states

    def test_search_route_consumes_flat_results(self, app_client, mock_db):
        """Routes must not expect the old [results] nesting."""
        mock_db.search = lambda embedding, top_k=10: [
            {"id": "/pics/hit.jpg", "distance": 0.2,
             "file_path": "/pics/hit.jpg", "tag": "photo"},
            {"id": "/pics/far.jpg", "distance": 0.95,
             "file_path": "/pics/far.jpg", "tag": "photo"},  # below score cut
        ]
        resp = app_client.post("/search/text", json={"query": "cat", "top_k": 5})
        assert resp.status_code == 200
        items = resp.json()["results"]
        paths = [i["file_path"] for i in items]
        assert "/pics/hit.jpg" in paths and "/pics/far.jpg" not in paths
