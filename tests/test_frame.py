"""Photo frame / slideshow sources."""
from datetime import datetime

import numpy as np
import pytest


def t(y, m, d, h=12):
    return datetime(y, m, d, h).timestamp()


ROWS = [
    # path,               time,             tag,          city,      country, sharp,  bright
    ("/p/hz1.jpg",        t(2025, 1, 5),    "photo",      "Hangzhou", "CN",   200.0, 120.0),
    ("/p/hz2.jpg",        t(2025, 2, 5),    "photo",      "Hangzhou", "CN",   200.0, 120.0),
    ("/p/hz3.jpg",        t(2025, 3, 5),    "photo",      "Hangzhou", "CN",   200.0, 120.0),
    ("/p/tokyo.jpg",      t(2025, 4, 5),    "photo",      "Tokyo",    "JP",   200.0, 120.0),
    ("/p/blurry.jpg",     t(2025, 5, 5),    "photo",      "Hangzhou", "CN",   5.0,   120.0),
    ("/p/black.jpg",      t(2025, 6, 5),    "photo",      "",         "",     2.0,   3.0),
    ("/p/new.jpg",        t(2025, 7, 5),    "photo",      "",         "",     None,  None),   # not measured yet
    ("/p/old.jpg",        t(2024, 7, 5),    "photo",      "Hangzhou", "CN",   200.0, 120.0),
    ("/p/clip.mp4",       t(2025, 8, 5),    "video",      "Hangzhou", "CN",   -1.0,  None),
    ("/p/shot.png",       t(2025, 8, 6),    "screenshot", "",         "",     200.0, 200.0),
    ("/private/x.jpg",    t(2025, 8, 7),    "photo",      "",         "",     200.0, 120.0),
]


@pytest.fixture
def frame(app_client, sqlite_store):
    s = sqlite_store
    s.upsert_photos([{
        "file_path": p, "captured_time": ts, "tag": tag, "last_modified": 1,
        "location_info": {"city": c, "country_code": cc} if c else None,
    } for p, ts, tag, c, cc, *_ in ROWS])
    for p, *_, sharp, bright in ROWS:
        if sharp is not None:
            s.set_quality(p, sharp, bright, 40.0, 1000)
    s.set_favorite("/p/tokyo.jpg", True)
    s.set_favorite("/p/blurry.jpg", True)
    aid = s.create_album("旅行")
    s.add_to_album(aid, ["/p/tokyo.jpg", "/p/hz1.jpg", "/p/clip.mp4"])
    s.add_faces("/p/hz2.jpg", [{"bbox": [0, 0, 1, 1], "embedding": np.zeros(4, np.float32)}])
    with s._get_conn() as conn:
        conn.execute("UPDATE faces SET person_id = 4")
        conn.commit()
    s.set_person_name(4, "妈妈")
    s.add_locked_folder("/private")
    app_client.album_id = aid
    return app_client


def paths(res):
    return [i["file_path"] for i in res.json()["items"]]


def test_best_skips_poor_photos_videos_screenshots_and_locked(frame):
    r = frame.get("/frame/photos", params={"seed": 1})
    assert r.json()["label"] == "精选" and r.json()["order"] == "weighted"
    assert set(paths(r)) == {"/p/hz1.jpg", "/p/hz2.jpg", "/p/hz3.jpg", "/p/tokyo.jpg", "/p/new.jpg", "/p/old.jpg"}
    # same seed, same order; another seed shuffles
    assert paths(r) == paths(frame.get("/frame/photos", params={"seed": 1}))
    orders = {tuple(paths(frame.get("/frame/photos", params={"seed": s}))) for s in range(8)}
    assert len(orders) > 1


def test_places_name_the_country_only_abroad(frame):
    items = {i["file_path"]: i for i in frame.get("/frame/photos").json()["items"]}
    assert items["/p/hz1.jpg"]["place"] == "Hangzhou"
    assert items["/p/tokyo.jpg"]["place"] == "Tokyo · 日本"
    assert items["/p/new.jpg"]["place"] == ""


def test_explicit_sources(frame):
    fav = frame.get("/frame/photos", params={"source": "favorites"}).json()
    assert sorted(i["file_path"] for i in fav["items"]) == ["/p/blurry.jpg", "/p/tokyo.jpg"]   # user's own picks
    alb = frame.get("/frame/photos", params={"source": f"album:{frame.album_id}", "order": "time"}).json()
    assert alb["label"] == "旅行" and [i["file_path"] for i in alb["items"]] == ["/p/hz1.jpg", "/p/tokyo.jpg"]
    per = frame.get("/frame/photos", params={"source": "person:4"}).json()
    assert per["label"] == "妈妈" and [i["file_path"] for i in per["items"]] == ["/p/hz2.jpg"]
    yr = frame.get("/frame/photos", params={"source": "year:2025"}).json()
    assert yr["order"] == "time"
    assert [i["file_path"] for i in yr["items"]] == ["/p/hz1.jpg", "/p/hz2.jpg", "/p/hz3.jpg", "/p/tokyo.jpg", "/p/new.jpg"]


def test_bad_sources(frame):
    assert frame.get("/frame/photos", params={"source": "album:999"}).status_code == 404
    assert frame.get("/frame/photos", params={"source": "trip:nope"}).status_code == 404
    assert frame.get("/frame/photos", params={"source": "year:x"}).status_code == 400
    assert frame.get("/frame/photos", params={"source": "bogus"}).status_code == 400


def test_sources_listing(frame):
    import api.routes.memories as mem
    mem.reset_cache()
    s = frame.get("/frame/sources").json()
    assert s["albums"] == [{"id": frame.album_id, "name": "旅行", "count": 3}]
    assert s["people"] == [{"id": 4, "name": "妈妈"}]
    assert s["years"] == [2025, 2024]
    mem.reset_cache()
