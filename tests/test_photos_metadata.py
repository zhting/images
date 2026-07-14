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


class TestTaskRunner:
    def _wait(self, task, timeout=5.0):
        import time
        deadline = time.time() + timeout
        while task.state.value in ("pending", "running") and time.time() < deadline:
            time.sleep(0.01)
        return task

    def test_task_completes_with_progress(self):
        from core.tasks import TaskRunner
        r = TaskRunner()
        seen = []

        def job(task):
            for i in range(5):
                task.report((i + 1) / 5, f"step {i+1}")
                seen.append(i)
        t = self._wait(r.submit("job", job))
        assert t.state.value == "done" and t.progress == 1.0 and len(seen) == 5

    def test_same_name_dedupe(self):
        import threading
        from core.tasks import TaskRunner
        r = TaskRunner()
        release = threading.Event()
        t1 = r.submit("slow", lambda task: release.wait(3))
        t2 = r.submit("slow", lambda task: None)
        assert t1.id == t2.id  # second submit returns the running task
        release.set()
        self._wait(t1)

    def test_cancellation_cooperative(self):
        import threading
        from core.tasks import TaskRunner
        r = TaskRunner()
        started = threading.Event()

        def job(task):
            started.set()
            while not task.cancelled:
                pass
        t = r.submit("cancellable", job)
        started.wait(2)
        assert r.cancel(t.id) is True
        self._wait(t)
        assert t.state.value == "cancelled"

    def test_failure_captured_not_raised(self):
        from core.tasks import TaskRunner
        r = TaskRunner()
        t = self._wait(r.submit("boom", lambda task: 1 / 0))
        assert t.state.value == "failed" and "ZeroDivisionError" in t.error

    def test_serial_execution(self):
        import threading
        from core.tasks import TaskRunner
        r = TaskRunner()
        order = []
        gate = threading.Event()
        t1 = r.submit("a", lambda task: (gate.wait(2), order.append("a")))
        t2 = r.submit("b", lambda task: order.append("b"))
        gate.set()
        self._wait(t1); self._wait(t2)
        assert order == ["a", "b"]  # strictly serial on one worker


class TestTasksAPI:
    def test_index_scan_returns_task_and_lists(self, app_client):
        resp = app_client.get("/index/scan")
        assert resp.status_code == 200
        tid = resp.json().get("task_id")
        assert tid
        tasks = app_client.get("/tasks").json()
        assert any(t["id"] == tid and t["name"] == "index_scan" for t in tasks)

    def test_cancel_unknown_task_404(self, app_client):
        assert app_client.post("/tasks/nope/cancel").status_code == 404


class TestDuplicates:
    def _seed(self, store):
        store.upsert_photos([
            {"file_path": "/p/a1.jpg", "captured_time": 10, "last_modified": 1,
             "tag": "photo", "file_hash": "aaa"},
            {"file_path": "/p/a2.jpg", "captured_time": 20, "last_modified": 1,
             "tag": "photo", "file_hash": "aaa"},
            {"file_path": "/p/b.jpg", "captured_time": 30, "last_modified": 1,
             "tag": "photo", "file_hash": "bbb"},
            {"file_path": "/p/legacy.jpg", "captured_time": 40, "last_modified": 1,
             "tag": "photo", "file_hash": "hash"},   # placeholder era
        ])

    def test_groups_and_ordering(self, sqlite_store):
        self._seed(sqlite_store)
        sqlite_store.set_photo_hash("/p/legacy.jpg", "ccc")
        groups = sqlite_store.get_duplicate_groups()
        assert len(groups) == 1 and groups[0]["count"] == 2
        # oldest first inside a group (default keep candidate)
        assert groups[0]["items"][0]["file_path"] == "/p/a1.jpg"

    def test_placeholder_hash_never_groups(self, sqlite_store):
        sqlite_store.upsert_photos([
            {"file_path": f"/p/x{i}.jpg", "captured_time": i, "last_modified": 1,
             "tag": "photo", "file_hash": "hash"} for i in range(3)])
        assert sqlite_store.get_duplicate_groups() == []
        assert sqlite_store.count_unhashed_photos() == 3

    def test_route_reports_backfill_then_groups(self, app_client, sqlite_store):
        self._seed(sqlite_store)
        r1 = app_client.get("/files/organize/duplicates").json()
        assert r1["ready"] is False and r1["pending"] == 1
        assert r1["task"]["name"] == "hash_backfill"
        # backfill task will fail on the fake path and store "" — emulate
        # completion by hashing manually, then the route serves groups
        sqlite_store.set_photo_hash("/p/legacy.jpg", "")
        import time
        deadline = time.time() + 3
        while sqlite_store.count_unhashed_photos() > 0 and time.time() < deadline:
            time.sleep(0.05)
        r2 = app_client.get("/files/organize/duplicates").json()
        assert r2["ready"] is True
        assert r2["total_groups"] == 1 and r2["reclaimable"] == 1

    def test_compute_file_hash_full_and_sampled(self, tmp_path):
        from api.helpers import compute_file_hash
        small = tmp_path / "s.bin"; small.write_bytes(b"x" * 1000)
        h1 = compute_file_hash(str(small))
        h2 = compute_file_hash(str(small))
        assert h1 == h2 and not h1.startswith("S")
        big = tmp_path / "b.bin"; big.write_bytes(b"y" * (2 * 1024 * 1024))
        hs = compute_file_hash(str(big), sample_threshold=1024 * 1024)
        assert hs.startswith("S")


class TestPersonMerge:
    def _add_face(self, store, path, pid):
        import numpy as np
        store.add_face(path, np.zeros(4, dtype=np.float32), "0,0,1,1")
        fid = store.get_all_faces()[-1]["id"]
        store.update_person_id(fid, pid)

    def test_merge_moves_faces_and_drops_source_name(self, sqlite_store):
        self._add_face(sqlite_store, "/p/a.jpg", 1)
        self._add_face(sqlite_store, "/p/b.jpg", 1)
        self._add_face(sqlite_store, "/p/c.jpg", 2)
        sqlite_store.set_person_name(1, "旧簇")
        sqlite_store.set_person_name(2, "妈妈")
        moved = sqlite_store.merge_persons(1, 2)
        assert moved == 2
        assert len(sqlite_store.get_faces_by_person(2)) == 3
        assert sqlite_store.get_faces_by_person(1) == []

    def test_merge_api_validates(self, app_client):
        r = app_client.post("/files/organize/people/merge",
                            json={"source_id": 5, "target_id": 5})
        assert r.status_code == 422
        r = app_client.post("/files/organize/people/merge",
                            json={"source_id": 99, "target_id": 100})
        assert r.status_code == 404
