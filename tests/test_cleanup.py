"""Cleanup assistant: quality measurement, background worker, suggestions."""
import os
from datetime import datetime

import numpy as np
import pytest
from PIL import Image, ImageFilter

from core import quality
from core.cleanup import build, find_bursts
from core.quality_worker import QualityWorker, NOT_AN_IMAGE

NOW = datetime(2026, 10, 10, 12).timestamp()


def texture(seed=0, size=(1200, 900)):
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 255, (size[1] // 8, size[0] // 8, 3), dtype=np.uint8)
    return Image.fromarray(a).resize(size, Image.Resampling.NEAREST)


def test_measure_tells_sharp_from_blurry_dark_and_flat():
    sharp = quality.measure(texture())
    blurry = quality.measure(texture().filter(ImageFilter.GaussianBlur(8)))
    dark = quality.measure(Image.fromarray((np.asarray(texture()) * 0.05).astype(np.uint8)))
    flat = quality.measure(Image.new("RGB", (800, 600), (120, 130, 140)))
    assert sharp["sharpness"] > 10 * quality.BLURRY_BELOW
    assert blurry["sharpness"] < quality.BLURRY_BELOW
    assert quality.verdict(**sharp) is None
    assert quality.verdict(**blurry) == "blurry"
    assert quality.verdict(**dark) == "dark"
    assert quality.verdict(**flat) == "flat"
    assert quality.verdict(NOT_AN_IMAGE, None, None) is None
    assert quality.verdict(300.0, 12.0, 30.0) is None                   # dark but full of detail


def test_bokeh_portrait_is_not_blurry():
    """Sharp subject in one corner, everything else blurred."""
    img = texture().filter(ImageFilter.GaussianBlur(10))
    img.paste(texture(1, (300, 220)), (0, 0))
    assert quality.verdict(**quality.measure(img)) is None


@pytest.fixture
def files(tmp_path):
    texture().save(tmp_path / "sharp.jpg", quality=90)
    texture().filter(ImageFilter.GaussianBlur(8)).save(tmp_path / "soft.jpg", quality=90)
    (tmp_path / "clip.mp4").write_bytes(b"\0" * 2048)
    return tmp_path


def test_worker_measures_photos_and_sizes_videos(sqlite_store, files):
    s = sqlite_store
    s.upsert_photos([
        {"file_path": str(files / "sharp.jpg"), "captured_time": NOW - 10, "tag": "photo", "last_modified": 1},
        {"file_path": str(files / "soft.jpg"), "captured_time": NOW - 20, "tag": "photo", "last_modified": 1},
        {"file_path": str(files / "clip.mp4"), "captured_time": NOW - 30, "tag": "video", "last_modified": 1},
        {"file_path": str(files / "gone.jpg"), "captured_time": NOW - 40, "tag": "photo", "last_modified": 1},
        {"file_path": "/x/trashed.jpg", "captured_time": NOW, "tag": "trash", "last_modified": 1},
    ])
    w = QualityWorker(lambda: s, lambda: "idle")
    assert s.count_quality_pending() == 4
    assert w.run_batch() == 4
    assert s.count_quality_pending() == 0 and s.count_quality_done() == 4
    rows = {r["basename"]: r for r in s.get_cleanup_rows("1=1")}
    assert rows["sharp.jpg"]["sharpness"] > quality.BLURRY_BELOW > rows["soft.jpg"]["sharpness"]
    assert rows["sharp.jpg"]["size"] == os.path.getsize(files / "sharp.jpg")
    assert rows["clip.mp4"]["sharpness"] == NOT_AN_IMAGE and rows["clip.mp4"]["size"] == 2048
    assert rows["gone.jpg"]["sharpness"] == NOT_AN_IMAGE         # missing file: not retried forever
    # Re-indexing a changed file forgets its measurement; unchanged keeps it.
    s.upsert_photos([
        {"file_path": str(files / "sharp.jpg"), "captured_time": NOW - 10, "tag": "photo", "last_modified": 2},
        {"file_path": str(files / "soft.jpg"), "captured_time": NOW - 20, "tag": "photo", "last_modified": 1},
    ])
    assert [p for p, _ in s.get_quality_pending()] == [str(files / "sharp.jpg")]


def test_worker_pauses_while_indexing(sqlite_store, files):
    sqlite_store.upsert_photos([{"file_path": str(files / "sharp.jpg"), "captured_time": 1,
                                 "tag": "photo", "last_modified": 1}])
    assert QualityWorker(lambda: sqlite_store, lambda: "indexing").run_batch() == 0


def test_find_bursts():
    rows = [{"captured_time": t} for t in (0, 2, 4, 30, 100, 101, 500)]
    assert [[r["captured_time"] for r in b] for b in find_bursts(rows)] == [[0, 2, 4], [100, 101]]


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------
def P(path, t, tag="photo", sharp=200.0, bright=120.0, contrast=50.0, size=1_000_000, h=None, fav=False):
    return dict(file_path=path, t=t, tag=tag, sharp=sharp, bright=bright, contrast=contrast,
                size=size, h=h or path, fav=fav)


LIB = [
    # duplicates: copy in a longer path, favourite original. The backup
    # copy is taken the same second as dup2.jpg — that must not become a
    # "burst" that suggests deleting dup2.jpg, the copy being kept.
    P("/a/dup.jpg", NOW - 9000, h="H1", fav=True), P("/a/backup/dup.jpg", NOW - 9000 + 1000, h="H1"),
    P("/a/dup2.jpg", NOW - 8000, h="H2"), P("/a/old/copy/dup2.jpg", NOW - 7000, h="H2"),
    # burst of three; the middle one is sharpest; the first is also blurry
    P("/b/1.jpg", NOW - 5000, sharp=10.0), P("/b/2.jpg", NOW - 4998, sharp=400.0), P("/b/3.jpg", NOW - 4996, sharp=150.0),
    # quality
    P("/q/black.jpg", NOW - 4000, bright=5.0, sharp=3.0), P("/q/wall.jpg", NOW - 3900, contrast=3.0),
    P("/q/stars.jpg", NOW - 3950, bright=12.0, sharp=300.0),          # night sky: dark but detailed
    P("/q/soft.jpg", NOW - 3800, sharp=12.0), P("/q/soft_fav.jpg", NOW - 3700, sharp=8.0, fav=True),
    P("/q/fine.jpg", NOW - 3600),
    # screenshots: old and recent
    P("/s/old.png", NOW - 90 * 86400, tag="screenshot"), P("/s/new.png", NOW - 86400, tag="screenshot"),
    # videos
    P("/v/big.mp4", NOW - 3000, tag="video", sharp=NOT_AN_IMAGE, size=600 * 1024 * 1024),
    P("/v/small.mp4", NOW - 2900, tag="video", sharp=NOT_AN_IMAGE, size=20 * 1024 * 1024),
    # locked folder
    P("/private/soft.jpg", NOW - 2000, sharp=5.0),
]


@pytest.fixture
def lib(sqlite_store):
    s = sqlite_store
    s.upsert_photos([{"file_path": r["file_path"], "captured_time": r["t"], "tag": r["tag"],
                      "last_modified": 1, "file_hash": r["h"]} for r in LIB])
    for r in LIB:
        s.set_quality(r["file_path"], r["sharp"], r["bright"], r["contrast"], r["size"])
        if r["fav"]:
            s.set_favorite(r["file_path"], True)
    s.set_photo_text("/s/old.png", "订单号 123456\n  已签收")
    s.add_locked_folder("/private")
    return s


def cats(result):
    return {c["kind"]: c for c in result["categories"]}


def suggested(c):
    if "groups" in c:
        return sorted(p for g in c["groups"] for p in g["suggest"])
    return [it["file_path"] for it in c["items"]]


def test_suggestions_by_category(lib):
    r = build(lib, lib.get_locked_folders(), now=NOW, texts=lib.get_texts)
    c = cats(r)
    assert [x["kind"] for x in r["categories"]] == ["duplicates", "bursts", "accidental", "blurry",
                                                    "screenshots", "large_videos"]
    d = c["duplicates"]
    assert {g["keep"] for g in d["groups"]} == {"/a/dup.jpg", "/a/dup2.jpg"}   # favourite / shorter path
    assert suggested(d) == ["/a/backup/dup.jpg", "/a/old/copy/dup2.jpg"]
    b = c["bursts"]
    assert b["groups"][0]["keep"] == "/b/2.jpg" and suggested(b) == ["/b/1.jpg", "/b/3.jpg"]
    assert suggested(c["accidental"]) == ["/q/black.jpg", "/q/wall.jpg"]
    # /b/1.jpg is blurry too but already suggested as part of the burst;
    # favourites and locked folders are never suggested.
    assert suggested(c["blurry"]) == ["/q/soft.jpg"]
    assert suggested(c["screenshots"]) == ["/s/old.png"]
    assert c["screenshots"]["items"][0]["text"] == "订单号 123456 已签收"
    assert suggested(c["large_videos"]) == ["/v/big.mp4"]
    assert c["large_videos"]["bytes"] == 600 * 1024 * 1024
    assert r["total_count"] == 2 + 2 + 2 + 1 + 1 + 1
    assert r["total_bytes"] == 8 * 1_000_000 + 600 * 1024 * 1024
    assert c["duplicates"]["preselect"] and not c["blurry"]["preselect"]


def test_kept_items_drop_out(lib):
    lib.keep_for_cleanup(["/q/soft.jpg"], "blurry")
    lib.keep_for_cleanup(["/b/1.jpg", "/b/3.jpg"], "bursts")
    c = cats(build(lib, lib.get_locked_folders(), now=NOW))
    assert suggested(c["blurry"]) == ["/b/1.jpg"]      # no longer claimed by the burst
    assert c["bursts"]["groups"] == [] and c["bursts"]["count"] == 0


@pytest.fixture
def client(app_client, lib):
    return app_client


def test_cleanup_api(client):
    r = client.get("/cleanup").json()
    assert r["hash_pending"] == 0
    assert set(r["quality"]) >= {"pending", "done"}
    assert cats(r)["blurry"]["count"] == 1
    assert client.post("/cleanup/keep", json={"kind": "blurry", "file_paths": ["/q/soft.jpg"]}).json() == {"kept": 1}
    assert cats(client.get("/cleanup").json())["blurry"]["count"] == 0
    assert client.post("/cleanup/keep", json={"kind": "nope", "file_paths": []}).status_code == 400
