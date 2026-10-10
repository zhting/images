"""Trip detection, memories and their API."""
from datetime import datetime

import numpy as np
import pytest

from core.trips import detect_trips, find_homes, haversine_km, pick_spread, trip_detail

HZ = ("Hangzhou", "Zhejiang", "CN", 30.25, 120.16)
SH = ("Shanghai", "Shanghai", "CN", 31.23, 121.47)
KM = ("Kunming", "Yunnan", "CN", 25.04, 102.71)
DL = ("Dali", "Yunnan", "CN", 25.61, 100.27)
LJ = ("Lijiang", "Yunnan", "CN", 26.87, 100.23)
TK = ("Tokyo", "Tokyo", "JP", 35.68, 139.69)
KY = ("Kyoto", "Kyoto", "JP", 35.01, 135.77)


def t(y, m, d, h=12):
    return datetime(y, m, d, h).timestamp()


def row(path, ts, place=None, fav=False, tag="photo", jitter=0.0):
    r = {"file_path": path, "t": ts, "lat": None, "lon": None, "city": "", "province": "",
         "country": "", "favorite": fav, "tag": tag}
    if place:
        city, prov, cc, lat, lon = place
        r.update(city=city, province=prov, country=cc, lat=lat + jitter, lon=lon + jitter)
    return r


def library():
    rows = []
    # Home: a couple of photos every month of 2025.
    for m in range(1, 13):
        for d in (3, 17):
            rows.append(row(f"/home/{m:02d}-{d}.jpg", t(2025, m, d), HZ))
    # Yunnan, 10-15 July: Kunming -> Dali -> Lijiang, two photos without GPS.
    rows += [row(f"/yn/km{i}.jpg", t(2025, 7, 10, 10 + i), KM, jitter=i * 0.002) for i in range(3)]
    rows += [row(f"/yn/dl{i}.jpg", t(2025, 7, 11 + i // 2, 9 + i), DL, jitter=i * 0.002) for i in range(4)]
    rows += [row("/yn/nogps1.jpg", t(2025, 7, 12, 20)), row("/yn/nogps2.jpg", t(2025, 7, 12, 21), fav=True)]
    rows += [row(f"/yn/lj{i}.jpg", t(2025, 7, 14 + i // 2, 10 + i), LJ) for i in range(3)]
    # Day out in Shanghai (165 km) with too few photos to count.
    rows += [row(f"/sh/{i}.jpg", t(2025, 5, 20, 10 + i), SH) for i in range(2)]
    # Tokyo 1-3 Oct, Kyoto 8-9 Oct: no home photo in between, but the
    # 5-day silence (> MAX_GAP) splits them into two trips.
    rows += [row(f"/jp/tk{i}.jpg", t(2025, 10, 1 + i // 2, 10 + i), TK) for i in range(5)]
    rows += [row(f"/jp/ky{i}.jpg", t(2025, 10, 8 + i // 3, 10 + i), KY) for i in range(4)]
    return rows


def test_home_is_where_most_months_are():
    gps = [r for r in library() if r["lat"] is not None]
    home = find_homes(gps)
    assert haversine_km(home[None][0], home[None][1], HZ[3], HZ[4]) < 1
    assert home[None][2] == "CN"
    assert home[2025] == home[None]


def test_detects_trips_newest_first():
    trips = detect_trips(library())
    assert [tr["title"] for tr in trips] == ["Kyoto", "Tokyo", "Kunming · Dali · Lijiang"]
    kyoto, tokyo, yunnan = trips
    assert tokyo["abroad"] and not yunnan["abroad"]
    assert tokyo["countries"] == ["日本"]
    assert yunnan["days"] == 6
    assert yunnan["photo_count"] == 12                  # includes the two without GPS
    assert [s["name"] for s in yunnan["stops"]] == ["Kunming", "Dali", "Lijiang"]
    assert 330 < yunnan["distance_km"] < 450
    assert yunnan["cover"] == "/yn/nogps2.jpg"          # the favourite


def test_photos_without_gps_join_the_stop_they_were_taken_at():
    yunnan = detect_trips(library())[-1]
    dali = yunnan["stops"][1]
    assert {"/yn/nogps1.jpg", "/yn/nogps2.jpg"} <= {p["file_path"] for p in dali["photos"]}
    detail = trip_detail(yunnan)
    assert [s["photo_count"] for s in detail["stops"]] == [3, 6, 3]
    assert len(detail["photos"]) == 12
    assert {p["stop"] for p in detail["photos"]} == {0, 1, 2}
    assert detail["path"][0] == [round(KM[3] + 0.002, 4), round(KM[4] + 0.002, 4)]


def test_returning_home_ends_a_trip():
    rows = library()
    rows.append(row("/home/mid.jpg", t(2025, 7, 13, 8), HZ))       # flew home for a night
    titles = [tr["title"] for tr in detect_trips(rows)]
    assert "Kunming · Dali · Lijiang" not in titles
    assert "Lijiang" not in titles                                 # only 3 photos after: too few
    assert "Kunming · Dali" in titles


def test_many_places_in_one_province_get_a_province_title():
    rows = [row(f"/home/{m}.jpg", t(2024, m, 5), HZ) for m in range(1, 13)]
    towns = [("A", 25.0), ("B", 25.5), ("C", 26.0), ("D", 26.5)]
    for i, (name, lat) in enumerate(towns):
        rows += [row(f"/{name}{k}.jpg", t(2024, 8, 1 + i, 9 + k), (name, "Yunnan Sheng", "CN", lat, 100.2))
                 for k in range(2)]
    assert detect_trips(rows)[0]["title"] == "Yunnan之旅"


def test_no_gps_no_trips():
    assert detect_trips([row(f"/{i}.jpg", t(2025, 1, 1 + i)) for i in range(20)]) == []


def test_pick_spread_one_per_day_and_prefers_favorites():
    items = [row(f"/d{d}-{k}.jpg", t(2025, 3, d, 8 + k), fav=(d == 2 and k == 3))
             for d in range(1, 11) for k in range(5)]
    picks = pick_spread(items, 5)
    assert len(picks) == 5
    assert len({datetime.fromtimestamp(p["t"]).date() for p in picks}) == 5
    assert "/d2-3.jpg" in [p["file_path"] for p in picks]
    assert picks == sorted(picks, key=lambda p: p["t"])
    # fewer days than requested: fill with more photos from those days
    assert len(pick_spread(items[:10], 6)) == 6


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@pytest.fixture
def mem_client(app_client, sqlite_store):
    import api.routes.memories as mem
    mem.reset_cache()
    rows = library()
    rows.append(row("/private/x.jpg", t(2025, 7, 12, 22), DL))
    rows.append(row("/shots/s.png", t(2025, 7, 12, 22), DL, tag="screenshot"))
    sqlite_store.upsert_photos([{
        "file_path": r["file_path"], "captured_time": r["t"], "tag": r["tag"], "last_modified": 1,
        "location_info": {"latitude": r["lat"], "longitude": r["lon"], "city": r["city"],
                          "province": r["province"], "country_code": r["country"]} if r["lat"] else None,
    } for r in rows])
    sqlite_store.set_favorite("/yn/nogps2.jpg", True)
    sqlite_store.add_faces("/jp/tk2.jpg", [{"bbox": [0, 0, 1, 1], "embedding": np.zeros(4, np.float32)}])
    with sqlite_store._get_conn() as conn:
        conn.execute("UPDATE faces SET person_id = 5")
        conn.commit()
    sqlite_store.set_person_name(5, "艾琳")
    sqlite_store.add_locked_folder("/private")
    yield app_client
    mem.reset_cache()


def test_trips_api(mem_client):
    trips = mem_client.get("/trips").json()["trips"]
    assert [tr["title"] for tr in trips] == ["Kyoto", "Tokyo", "Kunming · Dali · Lijiang"]
    assert trips[1]["cover"] == "/jp/tk2.jpg"                # named person beats the rest
    yn = mem_client.get(f"/trips/{trips[2]['id']}").json()
    paths = {p["file_path"] for p in yn["photos"]}
    assert "/private/x.jpg" not in paths and "/shots/s.png" not in paths
    assert len(yn["stops"]) == 3 and yn["stops"][1]["highlights"]
    assert mem_client.get("/trips/nope").status_code == 404


def test_trip_cache_follows_library_changes(mem_client, sqlite_store):
    first = mem_client.get("/trips").json()["trips"]
    sqlite_store.upsert_photos([{"file_path": f"/sy/{i}.jpg", "captured_time": t(2025, 3, 5, 9 + i),
                                 "tag": "photo", "last_modified": 1,
                                 "location_info": {"latitude": 18.25, "longitude": 109.5, "city": "Sanya",
                                                   "province": "Hainan", "country_code": "CN"}}
                                for i in range(4)])
    second = mem_client.get("/trips").json()["trips"]
    assert len(second) == len(first) + 1 and second[-1]["title"] == "Sanya"


def test_memories_api(mem_client):
    data = mem_client.get("/memories", params={"today": "2026-07-12"}).json()
    week = data["on_this_week"]
    assert [w["year"] for w in week] == [2025] and week[0]["years_ago"] == 1
    assert week[0]["count"] == 12               # 9-15 July: the whole Yunnan trip
    assert len(data["trips"]) == 3
    assert data["years"][0]["year"] == 2025 and data["years"][0]["trip_count"] == 3
    assert data["years"][0]["places"][0] == "Hangzhou"
    assert mem_client.get("/memories", params={"today": "bad"}).status_code == 400


def test_year_api(mem_client):
    y = mem_client.get("/memories/year/2025").json()
    assert y["count"] == 47 and y["favorites"] == 1
    assert sum(y["months"]) == 47 and y["months"][6] == 14
    assert y["people"] == [{"person_id": 5, "name": "艾琳", "count": 1}]
    assert len(y["trips"]) == 3
    assert 12 <= len(y["highlights"]) <= 36
    assert mem_client.get("/memories/year/1999").status_code == 404


def test_trip_through_several_countries_is_named_by_country():
    rows = [row(f"/home/{m}.jpg", t(2025, m, 5), HZ) for m in range(1, 13)]
    rows += [row(f"/dl{i}.jpg", t(2025, 8, 10, 9 + i), DL) for i in range(3)]
    rows += [row(f"/tk{i}.jpg", t(2025, 8, 11, 9 + i), TK) for i in range(2)]
    assert detect_trips(rows)[0]["title"] == "中国 · 日本"
