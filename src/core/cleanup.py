"""Cleanup suggestions: what could go to the recycle bin, and how much
space that would free.

Categories, in priority order — a photo is suggested by the first
category that matches, so nothing is counted twice:

  duplicates    identical files (same content hash); one copy is kept
  bursts        shots seconds apart; the favourite / sharpest is kept
  accidental    nearly black or blank frames (pocket shots, lens cap)
  blurry        out of focus or shaken
  screenshots   screenshots older than a month
  large_videos  videos over 100 MB

Only metadata is read here (hashes, times, the quality numbers measured
by the background worker, file sizes); favourites are never suggested,
and anything the user marked "keep" for a category stays out of it.
"""
from __future__ import annotations

import os
import time

from core import quality

LABELS = {
    "duplicates": "重复照片", "bursts": "连拍", "accidental": "误拍",
    "blurry": "模糊照片", "screenshots": "旧截图", "large_videos": "大视频",
}
ORDER = list(LABELS)
PRESELECT = {"duplicates", "bursts", "accidental"}

BURST_GAP = 5.0             # seconds between shots in a burst
BURST_MAX = 40              # longer runs are time-lapses, not bursts
SCREENSHOT_AGE = 30 * 86400
LARGE_VIDEO = 100 * 1024 * 1024
ITEM_LIMIT = 300
GROUP_LIMIT = 120

_VISIBLE = "tag NOT IN ('trash','error')"


def _size(item) -> int:
    if item.get("size") is None:
        try:
            item["size"] = os.path.getsize(item["file_path"])
        except OSError:
            item["size"] = 0
    return item["size"] or 0


def _slim(item) -> dict:
    return {k: item.get(k) for k in ("file_path", "basename", "captured_time", "tag", "favorite",
                                     "size", "sharpness", "brightness")}


def _keeper(items, prefer_sharp=False):
    """Index of the one to keep: favourite, then sharpest (bursts) or the
    oldest copy with the shortest path (duplicates)."""
    def score(i):
        it = items[i]
        if prefer_sharp:
            return (bool(it["favorite"]), it.get("sharpness") or 0.0, -abs(i - (len(items) - 1) / 2))
        return (bool(it["favorite"]), -len(it["file_path"]), -it["captured_time"])
    return max(range(len(items)), key=score)


def _groups(kind, groups, kept, taken, prefer_sharp):
    out, count, size, n = [], 0, 0, 0
    for items in groups:
        k = _keeper(items, prefer_sharp)
        suggest = [it for i, it in enumerate(items)
                   if i != k and not it["favorite"] and it["file_path"] not in kept
                   and it["file_path"] not in taken]
        if not suggest:
            continue
        n += 1
        for it in suggest:
            taken.add(it["file_path"])
            count += 1
            size += _size(it)
        _size(items[k])
        if len(out) < GROUP_LIMIT:
            out.append({"keep": items[k]["file_path"],
                        "suggest": [it["file_path"] for it in suggest],
                        "items": [_slim(it) for it in items]})
    return {"kind": kind, "groups": out, "count": count, "bytes": size, "truncated": n > len(out)}


def _items(kind, rows, kept, taken):
    picked = [r for r in rows if not r["favorite"] and r["file_path"] not in kept
              and r["file_path"] not in taken]
    size = 0
    for r in picked:
        taken.add(r["file_path"])
        size += _size(r)
    return {"kind": kind, "items": [_slim(r) for r in picked[:ITEM_LIMIT]],
            "count": len(picked), "bytes": size, "truncated": len(picked) > ITEM_LIMIT}


def find_bursts(rows: list) -> list:
    """rows sorted by time -> runs of 2..BURST_MAX shots < BURST_GAP apart."""
    out, cur = [], []
    for r in rows:
        if cur and r["captured_time"] - cur[-1]["captured_time"] < BURST_GAP:
            cur.append(r)
            continue
        if 2 <= len(cur) <= BURST_MAX:
            out.append(cur)
        cur = [r]
    if 2 <= len(cur) <= BURST_MAX:
        out.append(cur)
    return out


def build(store, locked=None, now: float | None = None, texts=None) -> dict:
    now = now or time.time()
    taken: set = set()
    cats = {}

    # duplicates ------------------------------------------------------------
    invalid = tuple(getattr(store, "_INVALID_HASHES", ()))
    ph = ",".join("?" * len(invalid)) or "''"
    dup_rows = store.get_cleanup_rows(
        f"""{_VISIBLE} AND file_hash IN (
                SELECT file_hash FROM photos WHERE file_hash IS NOT NULL AND file_hash NOT IN ({ph})
                  AND {_VISIBLE} GROUP BY file_hash HAVING COUNT(*) > 1)""",
        list(invalid), locked, order="file_hash, captured_time")
    by_hash = {}
    for r in dup_rows:
        by_hash.setdefault(r["file_hash"], []).append(r)
    groups = sorted((g for g in by_hash.values() if len(g) > 1), key=len, reverse=True)
    cats["duplicates"] = _groups("duplicates", groups, store.get_cleanup_kept("duplicates"), taken, False)

    # bursts ----------------------------------------------------------------
    photos = store.get_cleanup_rows("tag = 'photo' AND captured_time > 0", [], locked,
                                    order="captured_time ASC")
    # Copies already suggested as duplicates are left out *before* grouping:
    # otherwise a burst could keep the spare copy and suggest the original,
    # and both copies would end up in the bin.
    bursts = find_bursts([p for p in photos if p["file_path"] not in taken])
    bursts.reverse()                                     # newest first
    cats["bursts"] = _groups("bursts", bursts, store.get_cleanup_kept("bursts"), taken, True)

    # quality ---------------------------------------------------------------
    dark = "(brightness < ? AND sharpness < ?)"
    dark_p = [quality.DARK_BELOW, quality.DARK_MAX_SHARPNESS]
    rows = store.get_cleanup_rows(
        f"tag = 'photo' AND sharpness >= 0 AND ({dark} OR contrast < ?)", dark_p + [quality.FLAT_BELOW],
        locked, order="brightness ASC")
    cats["accidental"] = _items("accidental", rows, store.get_cleanup_kept("accidental"), taken)
    rows = store.get_cleanup_rows(
        f"tag = 'photo' AND sharpness >= 0 AND sharpness < ? AND NOT {dark} AND contrast >= ?",
        [quality.BLURRY_BELOW] + dark_p + [quality.FLAT_BELOW], locked, order="sharpness ASC")
    cats["blurry"] = _items("blurry", rows, store.get_cleanup_kept("blurry"), taken)

    # screenshots / videos ----------------------------------------------------
    rows = store.get_cleanup_rows("tag = 'screenshot' AND captured_time < ?", [now - SCREENSHOT_AGE],
                                  locked, order="captured_time ASC")
    cats["screenshots"] = _items("screenshots", rows, store.get_cleanup_kept("screenshots"), taken)
    if texts is not None:
        snippets = texts([it["file_path"] for it in cats["screenshots"]["items"]])
        for it in cats["screenshots"]["items"]:
            t = " ".join((snippets.get(it["file_path"]) or "").split())
            it["text"] = t[:60]
    # Videos: size from the quality pass, or stat() for ones not measured yet.
    rows = store.get_cleanup_rows("tag = 'video'", [], locked)
    rows = sorted((r for r in rows if _size(r) >= LARGE_VIDEO), key=lambda r: -r["size"])
    cats["large_videos"] = _items("large_videos", rows, store.get_cleanup_kept("large_videos"), taken)

    out = []
    for kind in ORDER:
        c = cats[kind]
        c["label"] = LABELS[kind]
        c["preselect"] = kind in PRESELECT
        out.append(c)
    return {"categories": out,
            "total_count": sum(c["count"] for c in out),
            "total_bytes": sum(c["bytes"] for c in out)}
