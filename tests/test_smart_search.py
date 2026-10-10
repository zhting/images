"""Text in photos (OCR storage + background worker) and /api/search/smart."""
from datetime import datetime

import numpy as np
import pytest
from PIL import Image


def ts(y, m, d):
    return datetime(y, m, d, 12).timestamp()


ROWS = [
    # path,                         time,              tag,          city,   province, fav
    ("/lib/dali/a.jpg",             ts(2025, 7, 3),    "photo",      "大理市", "云南",   0),
    ("/lib/dali/b.jpg",             ts(2025, 7, 4),    "photo",      "大理市", "云南",   1),
    ("/lib/hz/c.jpg",               ts(2025, 7, 5),    "photo",      "杭州",   "浙江",   0),
    ("/lib/hz/d.jpg",               ts(2024, 3, 1),    "photo",      "杭州",   "浙江",   0),
    ("/lib/shots/receipt.png",      ts(2025, 3, 2),    "screenshot", "",       "",       0),
    ("/lib/shots/menu.png",         ts(2025, 3, 3),    "screenshot", "",       "",       0),
    ("/lib/clip.mp4",               ts(2025, 7, 6),    "video",      "大理市", "云南",   0),
    ("/lib/gone.jpg",               ts(2025, 7, 7),    "trash",      "大理市", "云南",   0),
    ("/lib/private/e.jpg",          ts(2025, 7, 8),    "photo",      "大理市", "云南",   0),
]


@pytest.fixture
def library(sqlite_store):
    s = sqlite_store
    s.upsert_photos([{
        "file_path": p, "captured_time": t, "tag": tag, "last_modified": 1,
        "location_info": {"city": c, "province": pv} if c else None,
    } for p, t, tag, c, pv, _ in ROWS])
    for p, *_, fav in ROWS:
        if fav:
            s.set_favorite(p, True)
    # faces: 妈妈 (person 3) in a.jpg and c.jpg, 小明 (7) in a.jpg
    s.add_faces("/lib/dali/a.jpg", [{"bbox": [0, 0, 1, 1], "embedding": np.zeros(4, np.float32)}] * 2)
    s.add_faces("/lib/hz/c.jpg", [{"bbox": [0, 0, 1, 1], "embedding": np.zeros(4, np.float32)}])
    with s._get_conn() as conn:
        ids = [r[0] for r in conn.execute("SELECT id FROM faces ORDER BY id")]
        conn.execute("UPDATE faces SET person_id = 3 WHERE id IN (?, ?)", (ids[0], ids[2]))
        conn.execute("UPDATE faces SET person_id = 7 WHERE id = ?", (ids[1],))
        conn.commit()
    s.set_person_name(3, "妈妈")
    s.set_person_name(7, "小明")
    s.set_photo_text("/lib/shots/receipt.png", "增值税电子普通发票\n金额合计 ¥1,288.00\nWiFi 密码: DeepPhoto")
    s.set_photo_text("/lib/shots/menu.png", "菜单\n过桥米线 28元")
    s.set_photo_text("/lib/dali/a.jpg", "")          # processed, no text
    return s


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
def test_ocr_pending_order_and_counts(library):
    s = library
    pending = s.get_ocr_pending(limit=10)
    # never videos/trash; already-processed rows skipped; screenshots first
    assert "/lib/clip.mp4" not in pending and "/lib/gone.jpg" not in pending
    assert "/lib/dali/a.jpg" not in pending
    assert s.count_ocr_done() == 3
    assert s.count_ocr_pending() == len(pending) == 4      # 7 eligible - 3 processed


def test_reindex_forgets_text(library):
    s = library
    s.upsert_photos([{"file_path": "/lib/shots/menu.png", "captured_time": ts(2025, 3, 3),
                      "tag": "screenshot", "last_modified": 2}])
    assert s.get_photo_text("/lib/shots/menu.png") is None
    assert "/lib/shots/menu.png" in s.get_ocr_pending(limit=10)


def test_text_search_is_case_and_space_insensitive(library):
    s = library
    assert s.search_photo_text("wifi密码") == ["/lib/shots/receipt.png"]
    assert s.search_photo_text("WiFi 密码") == ["/lib/shots/receipt.png"]
    assert s.search_photo_text("1,288") == ["/lib/shots/receipt.png"]
    assert s.search_photo_text("100%") == []          # LIKE wildcards escaped
    assert s.search_photo_text("米线") == ["/lib/shots/menu.png"]


@pytest.mark.parametrize("kwargs, expected", [
    ({"places": ["大理市"]}, {"/lib/dali/a.jpg", "/lib/dali/b.jpg", "/lib/clip.mp4", "/lib/private/e.jpg"}),
    ({"places": ["云南"]}, {"/lib/dali/a.jpg", "/lib/dali/b.jpg", "/lib/clip.mp4", "/lib/private/e.jpg"}),
    ({"date_from": ts(2025, 1, 1), "date_to": ts(2026, 1, 1), "places": ["杭州"]}, {"/lib/hz/c.jpg"}),
    ({"people": [3]}, {"/lib/dali/a.jpg", "/lib/hz/c.jpg"}),
    ({"people": [3, 7]}, {"/lib/dali/a.jpg"}),                      # both people in the photo
    ({"favorite": True}, {"/lib/dali/b.jpg"}),
    ({"types": ["video"]}, {"/lib/clip.mp4"}),
    ({"ocr_terms": ["发票"]}, {"/lib/shots/receipt.png"}),          # screenshots included for text
])
def test_filter_photos(library, kwargs, expected):
    items, total = library.filter_photos(**kwargs)
    assert {i["file_path"] for i in items} == expected
    assert total == len(expected)


def test_filter_photos_includes_screenshots_but_never_trash(library):
    items, _ = library.filter_photos(date_from=ts(2025, 1, 1))
    paths = {i["file_path"] for i in items}
    assert "/lib/shots/receipt.png" in paths       # search is explicit: nothing hidden
    assert "/lib/gone.jpg" not in paths


def test_filter_photos_respects_locked_folders(library):
    items, _ = library.filter_photos(places=["大理市"], locked_prefixes=["/lib/private"])
    assert "/lib/private/e.jpg" not in {i["file_path"] for i in items}


def test_known_places_and_named_people(library):
    assert set(library.get_known_places()) == {"大理市", "云南", "杭州", "浙江"}
    assert library.get_named_people() == {"妈妈": 3, "小明": 7}


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------
class FakeEngine:
    def __init__(self):
        self.calls = []

    def recognize(self, img):
        self.calls.append(img.size)
        return "识别到的文字" if img.size[0] > 100 else ""


def make_worker(store, state="idle", **kw):
    from core.ocr_worker import OcrWorker
    return OcrWorker(lambda: store, lambda: state, engine=FakeEngine(), **kw)


def test_worker_processes_pending_and_records_unreadable(sqlite_store, tmp_path):
    good = tmp_path / "good.png"
    Image.new("RGB", (400, 300), "white").save(good)
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image")
    sqlite_store.upsert_photos([
        {"file_path": str(good), "captured_time": 2, "tag": "screenshot", "last_modified": 1},
        {"file_path": str(bad), "captured_time": 1, "tag": "photo", "last_modified": 1},
    ])
    w = make_worker(sqlite_store)
    assert w.run_batch() == 2
    assert sqlite_store.get_photo_text(str(good)) == "识别到的文字"
    assert sqlite_store.get_photo_text(str(bad)) == ""        # not retried forever
    assert sqlite_store.count_ocr_pending() == 0
    assert "bad.jpg" in w.last_error


def test_worker_prefers_cached_preview(sqlite_store, tmp_path):
    orig = tmp_path / "big.jpg"
    Image.new("RGB", (4000, 3000), "white").save(orig)
    prev = tmp_path / "prev.webp"
    Image.new("RGB", (1600, 1200), "white").save(prev)
    sqlite_store.upsert_photos([{"file_path": str(orig), "captured_time": 1, "tag": "photo", "last_modified": 1}])
    w = make_worker(sqlite_store, thumbnail_path=lambda p: str(prev))
    w.run_batch()
    assert w._engine.calls == [(1600, 1200)]


def test_worker_yields_to_indexing_and_respects_switch(sqlite_store, tmp_path):
    f = tmp_path / "x.png"
    Image.new("RGB", (300, 300)).save(f)
    sqlite_store.upsert_photos([{"file_path": str(f), "captured_time": 1, "tag": "photo", "last_modified": 1}])
    assert make_worker(sqlite_store, state="indexing").run_batch() == 0
    sqlite_store.set_config("ocr_enabled", "false")
    w = make_worker(sqlite_store)
    assert w.run_batch() == 0
    assert w.status()["state"] == "disabled"


# ---------------------------------------------------------------------------
# /api/search/smart
# ---------------------------------------------------------------------------
DIM = 8


def unit(i):
    v = np.zeros(DIM, np.float32)
    v[i] = 1.0
    return v


@pytest.fixture
def smart(app_client, library, mock_db, mock_model, monkeypatch):
    # Query vector points along axis 0; per-photo similarity is set below.
    monkeypatch.setattr(mock_model, "encode_text", lambda text: unit(0).tolist(), raising=False)
    import api.routes.search as search_mod
    monkeypatch.setattr(search_mod, "cached_translate", lambda t, target_lang="English": "sunset by the sea")
    sims = {"/lib/dali/a.jpg": 0.30, "/lib/dali/b.jpg": 0.20, "/lib/hz/c.jpg": 0.25,
            "/lib/hz/d.jpg": 0.05, "/lib/clip.mp4": 0.10, "/lib/gone.jpg": 0.9,
            "/lib/private/e.jpg": 0.5, "/lib/shots/receipt.png": 0.02, "/lib/shots/menu.png": 0.01}

    def vec(sim):
        return (sim * unit(0) + np.sqrt(max(0, 1 - sim * sim)) * unit(1)).tolist()

    mock_db.get_embeddings = lambda paths: {p: [vec(sims[p])] for p in paths if p in sims}
    tags = {p: t for p, _, t, *_ in ROWS}
    mock_db.search = lambda emb, top_k=50: [
        {"file_path": p, "distance": 1 - s, "tag": tags[p]}
        for p, s in sorted(sims.items(), key=lambda kv: -kv[1])][:top_k]
    library.add_locked_folder("/lib/private")
    return app_client


def paths(resp):
    return [r["file_path"] for r in resp.json()["results"]]


def test_filters_plus_semantic_ranking(smart):
    r = smart.get("/search/smart", params={"q": "去年夏天在大理的日落"})
    body = r.json()
    assert r.status_code == 200
    assert [c["kind"] for c in body["parsed"]["chips"]] == ["time", "place"]
    # only 2025-summer Dali items (no trash, no locked), ranked by stored vectors
    assert paths(r) == ["/lib/dali/a.jpg", "/lib/dali/b.jpg", "/lib/clip.mp4"]
    assert body["results"][0]["match"] == ["semantic"]
    assert body["translated_query"] == "sunset by the sea"


def test_person_filter_only(smart):
    r = smart.get("/search/smart", params={"q": "妈妈"})
    assert set(paths(r)) == {"/lib/dali/a.jpg", "/lib/hz/c.jpg"}
    assert r.json()["parsed"]["people_names"] == ["妈妈"]
    assert all(x["score"] is None for x in r.json()["results"])     # time-ordered


def test_quoted_text_finds_screenshots_with_snippet(smart):
    r = smart.get("/search/smart", params={"q": '"发票"'})
    res = r.json()["results"]
    assert [x["file_path"] for x in res] == ["/lib/shots/receipt.png"]
    assert res[0]["match"] == ["filter", "text"]
    assert "发票" in res[0]["snippet"]


def test_plain_words_also_match_photo_text(smart):
    r = smart.get("/search/smart", params={"q": "过桥米线"})
    res = {x["file_path"]: x for x in r.json()["results"]}
    assert "text" in res["/lib/shots/menu.png"]["match"]
    assert "米线" in res["/lib/shots/menu.png"]["snippet"]
    # vector hits are still there, trash and locked are not
    assert "/lib/dali/a.jpg" in res
    assert "/lib/gone.jpg" not in res and "/lib/private/e.jpg" not in res


def test_empty_query_returns_nothing(smart):
    assert smart.get("/search/smart", params={"q": ""}).json()["results"] == []


def test_ocr_status_and_switch(smart):
    st = smart.get("/ocr/status").json()
    assert set(st) >= {"state", "pending", "done", "available"}
    st = smart.post("/ocr/config", json={"enabled": False}).json()
    assert st["state"] in ("disabled", "unavailable")


def test_file_info_includes_ocr_text(smart, tmp_path, library):
    f = tmp_path / "note.png"
    Image.new("RGB", (50, 50)).save(f)
    library.add_asset_path(str(tmp_path))
    library.upsert_photos([{"file_path": str(f), "captured_time": 1, "tag": "screenshot", "last_modified": 1}])
    library.set_photo_text(str(f), "会议纪要")
    info = smart.get("/files/info", params={"path": str(f)}).json()
    assert info.get("ocr_text") == "会议纪要"


def test_real_ocr_engine_reads_chinese(tmp_path):
    """Runs only where rapidocr_onnxruntime is installed (not in CI)."""
    pytest.importorskip("rapidocr_onnxruntime")
    import glob
    from PIL import ImageDraw, ImageFont
    fonts = glob.glob("/usr/share/fonts/**/*CJK*", recursive=True)
    if not fonts:
        pytest.skip("no CJK font to render the test image")
    img = Image.new("RGB", (900, 300), "white")
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(fonts[0], 48)
    d.text((40, 60), "增值税电子普通发票", fill="black", font=font)
    d.text((40, 170), "WiFi 密码: Deep2026", fill="black", font=font)
    from core.ocr import OcrEngine
    text = OcrEngine().recognize(img)
    assert "发票" in text
    assert "Deep2026" in text.replace(" ", "")
    assert text.index("发票") < text.index("Deep")      # reading order
