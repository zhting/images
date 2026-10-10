"""Memories: automatically detected trips (with a route for map
playback), "this week in past years", and per-year highlights.

All of it is derived from metadata already in SQLite — capture time, GPS
and place names, favourites and face clusters — so nothing is re-indexed.
Trip detection runs in pure Python over the whole library and is cached
until the library fingerprint changes (``memory_signature``).
"""
import threading
from collections import Counter
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException

from api.state import get_store
from core.trips import detect_trips, photo_out, pick_spread, trip_detail, trip_summary, photo_score

import logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["memories"])

_lock = threading.Lock()
_cache = {"sig": None, "rows": [], "faces": {}, "trips": []}


def _load():
    """(rows, faces, trips) for the current library, recomputed only when
    something trip detection depends on has changed."""
    store = get_store()
    locked = store.get_locked_folders()
    sig = store.memory_signature(locked)
    with _lock:
        if _cache["sig"] != sig:
            rows = store.get_memory_rows(locked)
            faces = store.get_face_counts()
            trips = detect_trips(rows, faces)
            _cache.update(sig=sig, rows=rows, faces=faces, trips=trips)
        return _cache["rows"], _cache["faces"], _cache["trips"]


def reset_cache():
    with _lock:
        _cache.update(sig=None, rows=[], faces={}, trips=[])


def _ts(d: date) -> float:
    return datetime(d.year, d.month, d.day).timestamp()


@router.get("/trips")
def list_trips():
    _, _, trips = _load()
    return {"trips": [trip_summary(t) for t in trips]}


@router.get("/trips/{trip_id}")
def get_trip(trip_id: str):
    _, faces, trips = _load()
    for t in trips:
        if t["id"] == trip_id:
            return trip_detail(t, faces)
    raise HTTPException(status_code=404, detail="trip not found")


def _on_this_week(rows, faces, today: date, per_year: int = 12):
    out = []
    years = sorted({datetime.fromtimestamp(r["t"]).year for r in rows}, reverse=True)
    for y in years:
        if y >= today.year:
            continue
        try:
            centre = today.replace(year=y)
        except ValueError:                      # 29 Feb
            centre = today.replace(year=y, day=28)
        lo, hi = _ts(centre - timedelta(days=3)), _ts(centre + timedelta(days=4))
        window = [r for r in rows if lo <= r["t"] < hi]
        if not window:
            continue
        picks = pick_spread(window, per_year, faces)
        out.append({
            "year": y, "years_ago": today.year - y,
            "start": lo, "end": hi, "count": len(window),
            "cover": max(window, key=lambda p: photo_score(p, faces))["file_path"],
            "photos": [photo_out(p) for p in picks],
        })
    return out


def _place_name(r):
    return r["city"] or r["province"] or ""


def _years(rows, faces, trips):
    by_year = {}
    for r in rows:
        by_year.setdefault(datetime.fromtimestamp(r["t"]).year, []).append(r)
    trip_years = Counter(datetime.fromtimestamp(t["start"]).year for t in trips)
    out = []
    for y in sorted(by_year, reverse=True):
        items = by_year[y]
        places = Counter(_place_name(r) for r in items)
        places.pop("", None)
        out.append({
            "year": y, "count": len(items),
            "cover": max(items, key=lambda p: photo_score(p, faces))["file_path"],
            "places": [n for n, _ in places.most_common(3)],
            "trip_count": trip_years.get(y, 0),
        })
    return out


@router.get("/memories")
def get_memories(today: str = None):
    rows, faces, trips = _load()
    try:
        day = date.fromisoformat(today) if today else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="today must be YYYY-MM-DD")
    return {
        "on_this_week": _on_this_week(rows, faces, day),
        "trips": [trip_summary(t) for t in trips],
        "years": _years(rows, faces, trips),
    }


@router.get("/memories/year/{year}")
def get_year(year: int, limit: int = 36):
    rows, faces, trips = _load()
    lo, hi = _ts(date(year, 1, 1)), _ts(date(year + 1, 1, 1))
    items = [r for r in rows if lo <= r["t"] < hi]
    if not items:
        raise HTTPException(status_code=404, detail="no photos in that year")
    months = [0] * 12
    for r in items:
        months[datetime.fromtimestamp(r["t"]).month - 1] += 1
    places = Counter(_place_name(r) for r in items)
    places.pop("", None)
    store = get_store()
    people = store.get_named_people_between(lo, hi, store.get_locked_folders())
    return {
        "year": year, "count": len(items),
        "videos": sum(1 for r in items if r["tag"] == "video"),
        "favorites": sum(1 for r in items if r["favorite"]),
        "months": months,
        "places": [{"name": n, "count": c} for n, c in places.most_common(8)],
        "people": people,
        "trips": [trip_summary(t) for t in trips if lo <= t["start"] < hi],
        "highlights": [photo_out(p) for p in pick_spread(items, max(1, min(limit, 120)), faces)],
    }
