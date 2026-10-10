"""Photo frame / slideshow: an ordered list of still photos from one
source — a quality-filtered random selection of the whole library,
favourites, an album, a person, a trip, a year or a search."""
import random
from datetime import date, datetime

from fastapi import APIRouter, HTTPException

from api.state import get_store
from core import quality
from core.trips import country_name, photo_score

import logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["frame"])

LIMIT = 500


def _ts(d: date) -> float:
    return datetime(d.year, d.month, d.day).timestamp()


def _good(r) -> bool:
    return quality.verdict(r["sharpness"], r["brightness"], r["contrast"]) is None


def _weighted_shuffle(rows, weight, rng):
    # Efraimidis–Spirakis: key = u^(1/w); larger weight -> earlier on average.
    return sorted(rows, key=lambda r: rng.random() ** (1.0 / weight(r)), reverse=True)


def _place(r, home_country):
    place = r["city"] or r["province"]
    if r["country"] and r["country"] != home_country:
        return f"{place} · {country_name(r['country'])}" if place else country_name(r["country"])
    return place


def _rows_for(source: str, store, locked):
    """(label, rows, default order) for a source string like 'album:3'."""
    kind, _, arg = source.partition(":")
    if kind == "best":
        return "精选", [r for r in store.get_frame_rows("1=1", [], locked) if _good(r)], "weighted"
    if kind == "favorites":
        return "收藏", store.get_frame_rows("favorite = 1", [], locked), "shuffle"
    if kind == "album":
        albums = {str(a["id"]): a["name"] for a in store.get_albums(locked)}
        if arg not in albums:
            raise HTTPException(status_code=404, detail="album not found")
        return albums[arg], store.get_frame_rows(
            "file_path IN (SELECT file_path FROM album_items WHERE album_id = ?)", [int(arg)], locked), "shuffle"
    if kind == "person":
        names = {str(v): k for k, v in store.get_named_people().items()}
        try:
            pid = int(arg)
        except ValueError:
            raise HTTPException(status_code=400, detail="bad person id")
        return names.get(arg, "人物"), store.get_frame_rows(
            "file_path IN (SELECT file_path FROM faces WHERE person_id = ?)", [pid], locked), "shuffle"
    if kind == "year":
        try:
            y = int(arg)
        except ValueError:
            raise HTTPException(status_code=400, detail="bad year")
        rows = store.get_frame_rows("captured_time >= ? AND captured_time < ?",
                                    [_ts(date(y, 1, 1)), _ts(date(y + 1, 1, 1))], locked)
        return f"{y}年", [r for r in rows if _good(r)], "time"
    if kind == "trip":
        from api.routes.memories import _load
        trip = next((t for t in _load()[2] if t["id"] == arg), None)
        if trip is None:
            raise HTTPException(status_code=404, detail="trip not found")
        paths = {p["file_path"] for p in trip["members"] if p.get("tag") != "video"}
        rows = store.get_frame_rows("captured_time >= ? AND captured_time <= ?",
                                    [trip["start"], trip["end"]], locked)
        return trip["title"], [r for r in rows if r["file_path"] in paths], "time"
    if kind == "search":
        from api.routes.search import search_smart
        res = search_smart(q=arg, top_k=LIMIT)
        order = {r["file_path"]: i for i, r in enumerate(res.get("results", []))}
        if not order:
            return f"搜索：{arg}", [], "rank"
        ph = ",".join("?" * len(order))
        rows = store.get_frame_rows(f"file_path IN ({ph})", list(order), locked)
        rows.sort(key=lambda r: order[r["file_path"]])
        return f"搜索：{arg}", rows, "rank"
    raise HTTPException(status_code=400, detail="unknown source")


@router.get("/frame/photos")
def frame_photos(source: str = "best", order: str = "", seed: int = None, limit: int = LIMIT):
    store = get_store()
    locked = store.get_locked_folders()
    label, rows, default_order = _rows_for(source, store, locked)
    order = order or default_order
    rng = random.Random(seed)
    if order == "weighted":
        faces = store.get_face_counts()
        rows = _weighted_shuffle(rows, lambda r: 1.0 + max(0.0, photo_score(r, faces)), rng)
    elif order == "shuffle":
        rng.shuffle(rows)
    elif order == "time":
        rows.sort(key=lambda r: r["t"])
    home = store.get_main_country()
    total = len(rows)
    items = [{"file_path": r["file_path"], "captured_time": r["t"], "place": _place(r, home),
              "favorite": r["favorite"]} for r in rows[:max(1, min(limit, 2000))]]
    return {"source": source, "label": label, "order": order, "total": total, "items": items}


@router.get("/frame/sources")
def frame_sources():
    store = get_store()
    locked = store.get_locked_folders()
    from api.routes.memories import _load
    rows, _, trips = _load()
    years = sorted({datetime.fromtimestamp(r["t"]).year for r in rows}, reverse=True)
    return {
        "albums": [{"id": a["id"], "name": a["name"], "count": a["count"]}
                   for a in store.get_albums(locked) if a["count"]],
        "people": [{"id": pid, "name": name} for name, pid in sorted(store.get_named_people().items())],
        "trips": [{"id": t["id"], "title": t["title"], "start": t["start"]} for t in trips],
        "years": years,
    }
