"""Find trips in the photo library and pick photos for memories.

Everything here works on rows already in SQLite (capture time, GPS,
reverse-geocoded names, favourites, face counts) — no image is opened
and no model runs, so a library of 100k photos is processed in well
under a second and the result is cached by the caller.

Trip detection
--------------
1. *Home* is the place with photos in the most distinct months (a long
   holiday adds a month or two; home shows up all year). It is decided
   per year when that year has enough evidence, so moving house works,
   and falls back to the whole-library home otherwise.
2. Photos with GPS more than ``AWAY_KM`` from home are "away". Runs of
   away photos form a trip; a photo taken at home, or a gap of more than
   ``MAX_GAP`` without away photos, ends it.
3. A trip keeps every photo taken between its first and last away photo
   (including ones without GPS), split into *stops* — consecutive photos
   in the same area — which drive the route playback.
"""
from __future__ import annotations

import bisect
import math
import zlib
from collections import Counter, defaultdict
from datetime import datetime

AWAY_KM = 60.0              # farther than this from home counts as travelling
MAX_GAP = 3 * 86400         # this long without an away photo ends a trip
MIN_TRIP_PHOTOS = 4         # GPS photos needed for a trip
STOP_KM = 3.0               # same named place within this distance = one stop
STOP_FAR_KM = 15.0          # this far always starts a new stop
MAX_STOPS = 40

COUNTRY_NAMES = {
    "CN": "中国", "HK": "中国香港", "MO": "中国澳门", "TW": "中国台湾", "JP": "日本", "KR": "韩国",
    "TH": "泰国", "SG": "新加坡", "MY": "马来西亚", "VN": "越南", "ID": "印度尼西亚", "PH": "菲律宾",
    "KH": "柬埔寨", "LA": "老挝", "MM": "缅甸", "IN": "印度", "NP": "尼泊尔", "LK": "斯里兰卡",
    "MV": "马尔代夫", "AE": "阿联酋", "TR": "土耳其", "EG": "埃及", "MA": "摩洛哥", "ZA": "南非",
    "KE": "肯尼亚", "TZ": "坦桑尼亚", "FR": "法国", "GB": "英国", "DE": "德国", "IT": "意大利",
    "ES": "西班牙", "PT": "葡萄牙", "NL": "荷兰", "BE": "比利时", "CH": "瑞士", "AT": "奥地利",
    "CZ": "捷克", "HU": "匈牙利", "PL": "波兰", "GR": "希腊", "HR": "克罗地亚", "IS": "冰岛",
    "NO": "挪威", "SE": "瑞典", "FI": "芬兰", "DK": "丹麦", "IE": "爱尔兰", "RU": "俄罗斯",
    "US": "美国", "CA": "加拿大", "MX": "墨西哥", "BR": "巴西", "AR": "阿根廷", "CL": "智利",
    "PE": "秘鲁", "AU": "澳大利亚", "NZ": "新西兰", "MN": "蒙古", "KZ": "哈萨克斯坦", "UZ": "乌兹别克斯坦",
    "GE": "格鲁吉亚", "IL": "以色列", "JO": "约旦", "QA": "卡塔尔", "SA": "沙特阿拉伯", "FJ": "斐济",
}

_PROVINCE_SUFFIXES = (" Sheng", " Shi", "省", "市", "自治区", "特别行政区")


def country_name(cc: str) -> str:
    return COUNTRY_NAMES.get((cc or "").upper(), cc or "")


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(a)))


def _has_gps(p) -> bool:
    lat, lon = p.get("lat"), p.get("lon")
    return lat is not None and lon is not None and not (abs(lat) < 1e-6 and abs(lon) < 1e-6)


def _place_key(p) -> str:
    """Coarse place identity: the city name, else a ~10 km grid cell."""
    if p.get("city"):
        return f"{p['city']}|{p.get('province', '')}|{p.get('country', '')}"
    return f"@{round(p['lat'], 1)},{round(p['lon'], 1)}"


def _short_province(name: str) -> str:
    for s in _PROVINCE_SUFFIXES:
        if name.endswith(s) and len(name) > len(s):
            return name[: -len(s)]
    return name


def _month(ts: float) -> tuple:
    d = datetime.fromtimestamp(ts)
    return d.year, d.month


# --------------------------------------------------------------------------
# Home
# --------------------------------------------------------------------------


def find_homes(gps_photos: list) -> dict:
    """{year: (lat, lon, country)} plus key None for the library-wide home."""
    months = defaultdict(set)              # key -> {(y, m)}
    months_by_year = defaultdict(lambda: defaultdict(set))
    coords = defaultdict(list)
    countries = {}
    for p in gps_photos:
        k = _place_key(p)
        ym = _month(p["t"])
        months[k].add(ym)
        months_by_year[ym[0]][k].add(ym)
        coords[k].append((p["lat"], p["lon"]))
        countries[k] = p.get("country", "")
    if not months:
        return {}

    def centre(k):
        lats = sorted(c[0] for c in coords[k])
        lons = sorted(c[1] for c in coords[k])
        return lats[len(lats) // 2], lons[len(lons) // 2], countries.get(k, "")

    def best(table):
        return max(table, key=lambda k: (len(table[k]), len(coords[k])))

    homes = {None: centre(best(months))}
    for year, table in months_by_year.items():
        k = best(table)
        homes[year] = centre(k) if len(table[k]) >= 3 else homes[None]
    return homes


# --------------------------------------------------------------------------
# Scoring (shared by trip covers and memories highlights)
# --------------------------------------------------------------------------


def photo_score(p, faces: dict | None = None) -> float:
    f = (faces or {}).get(p["file_path"], (0, 0))
    return (3.0 * bool(p.get("favorite")) + 1.5 * min(f[1], 3) + 0.4 * min(f[0], 5)
            + (0.3 if _has_gps(p) else 0) - (0.5 if p.get("tag") == "video" else 0))


def pick_spread(items: list, n: int, faces: dict | None = None) -> list:
    """Up to n good photos spread over the time range of ``items``.

    Best photo per day first (so a burst of 200 shots from one afternoon
    can't take over), then the day list is cut into n consecutive chunks
    and the best of each chunk is kept.
    """
    if not items or n <= 0:
        return []
    by_day = {}
    for p in items:
        day = datetime.fromtimestamp(p["t"]).date()
        if day not in by_day or photo_score(p, faces) > photo_score(by_day[day], faces):
            by_day[day] = p
    days = [by_day[d] for d in sorted(by_day)]
    if len(days) <= n:
        # Few days: fill up with the next-best photos overall, keep time order.
        chosen = {p["file_path"] for p in days}
        rest = sorted((p for p in items if p["file_path"] not in chosen),
                      key=lambda p: -photo_score(p, faces))
        picked = days + rest[: n - len(days)]
        return sorted(picked, key=lambda p: p["t"])
    out = []
    for i in range(n):
        chunk = days[i * len(days) // n:(i + 1) * len(days) // n]
        if chunk:
            out.append(max(chunk, key=lambda p: photo_score(p, faces)))
    return out


# --------------------------------------------------------------------------
# Trips
# --------------------------------------------------------------------------


def _segments(gps_photos: list, homes: dict) -> list:
    segs, cur = [], []
    for p in gps_photos:
        home = homes.get(datetime.fromtimestamp(p["t"]).year, homes[None])
        away = haversine_km(p["lat"], p["lon"], home[0], home[1]) > AWAY_KM
        if away and cur and p["t"] - cur[-1]["t"] > MAX_GAP:
            segs.append(cur)
            cur = []
        if away:
            cur.append(p)
        elif cur:
            segs.append(cur)
            cur = []
    if cur:
        segs.append(cur)
    return [s for s in segs if len(s) >= MIN_TRIP_PHOTOS]


def _build_stops(gps: list, near_km: float, far_km: float) -> list:
    stops = []
    for p in gps:
        s = stops[-1] if stops else None
        if s is not None:
            d = haversine_km(p["lat"], p["lon"], s["lat"], s["lon"])
            same = d <= far_km and (_place_key(p) == s["key"] or d <= near_km)
            if same:
                n = len(s["gps"])
                s["lat"] = (s["lat"] * n + p["lat"]) / (n + 1)
                s["lon"] = (s["lon"] * n + p["lon"]) / (n + 1)
                s["gps"].append(p)
                continue
        stops.append({"key": _place_key(p), "lat": p["lat"], "lon": p["lon"], "gps": [p]})
    return stops


def _stops_for(gps: list) -> list:
    near, far = STOP_KM, STOP_FAR_KM
    stops = _build_stops(gps, near, far)
    while len(stops) > MAX_STOPS:
        near, far = near * 2, far * 2
        stops = _build_stops(gps, near, far)
    return stops


def _stop_name(gps: list) -> str:
    names = Counter(p.get("city") or _short_province(p.get("province", "")) or country_name(p.get("country", ""))
                    for p in gps)
    names.pop("", None)
    return names.most_common(1)[0][0] if names else ""


def _trip_title(stops: list, home_country: str) -> tuple[str, list, list]:
    weight = Counter()
    countries = Counter()
    provinces = Counter()
    for s in stops:
        for p in s["gps"]:
            weight[s["name"]] += 1
            if p.get("country"):
                countries[p["country"]] += 1
            if p.get("province"):
                provinces[p["province"]] += 1
    weight.pop("", None)
    cities = [n for n, _ in weight.most_common()]
    visited = [c for c, _ in countries.most_common() if c]
    foreign = [c for c in visited if c != home_country]
    if len(visited) > 1 and foreign:
        # Several countries (possibly including places at home): name them.
        title = " · ".join(country_name(c) for c in visited[:3])
    elif foreign and len(cities) > 3:
        title = f"{country_name(foreign[0])}之旅"
    elif len(cities) > 3 and len(provinces) == 1:
        title = f"{_short_province(next(iter(provinces)))}之旅"
    elif cities:
        # The three places with the most photos, in the order visited.
        top = set(cities[:3])
        order = [s["name"] for s in stops if s["name"] in top]
        title = " · ".join(dict.fromkeys(order))
    else:
        title = "一次旅行"
    return title, cities, [country_name(c) for c, _ in countries.most_common()]


def _trip_id(first) -> str:
    return f"{int(first['t'])}-{zlib.crc32(first['file_path'].encode('utf-8')) & 0xffff:04x}"


def detect_trips(photos: list, faces: dict | None = None) -> list:
    """photos: dicts with file_path, t, lat, lon, city, province, country,
    favorite, tag — any order. Returns trips, newest first."""
    photos = sorted((p for p in photos if p.get("t")), key=lambda p: p["t"])
    gps_photos = [p for p in photos if _has_gps(p)]
    homes = find_homes(gps_photos)
    if not homes:
        return []

    times = [p["t"] for p in photos]
    trips = []
    for seg in _segments(gps_photos, homes):
        start, end = seg[0]["t"], seg[-1]["t"]
        lo, hi = bisect.bisect_left(times, start), bisect.bisect_right(times, end)
        members = photos[lo:hi]
        # A GPS photo inside the window that is *not* part of this segment
        # was taken at home (segments end there), so leave it out.
        seg_paths = {p["file_path"] for p in seg}
        members = [p for p in members if not _has_gps(p) or p["file_path"] in seg_paths]

        stops = _stops_for(seg)
        for s in stops:
            s["name"] = _stop_name(s["gps"])
            s["arrive"], s["leave"] = s["gps"][0]["t"], s["gps"][-1]["t"]
            s["photos"] = []
        # Every member goes to the stop whose time span it falls in (or the
        # last stop that started before it).
        si = 0
        for p in members:
            while si + 1 < len(stops) and p["t"] >= stops[si + 1]["arrive"]:
                si += 1
            stops[si]["photos"].append(p)

        home = homes.get(datetime.fromtimestamp(start).year, homes[None])
        title, cities, countries = _trip_title(stops, home[2])
        distance = sum(haversine_km(a["lat"], a["lon"], b["lat"], b["lon"]) for a, b in zip(stops, stops[1:], strict=False))
        d0, d1 = datetime.fromtimestamp(start).date(), datetime.fromtimestamp(end).date()
        cover = max(members, key=lambda p: (photo_score(p, faces), -abs(p["t"] - (start + end) / 2)))
        trips.append({
            "id": _trip_id(seg[0]),
            "title": title,
            "start": start, "end": end,
            "days": (d1 - d0).days + 1,
            "cities": cities, "countries": countries,
            "abroad": any(p.get("country") and p["country"] != home[2] for p in seg),
            "photo_count": len(members),
            "distance_km": round(distance),
            "cover": cover["file_path"],
            "home": {"lat": home[0], "lon": home[1]},
            "stops": stops,
            "members": members,
        })
    trips.reverse()
    return trips


def trip_summary(trip: dict) -> dict:
    return {k: trip[k] for k in ("id", "title", "start", "end", "days", "cities", "countries",
                                 "abroad", "photo_count", "distance_km", "cover")} | {
        "stop_count": len(trip["stops"]),
        "path": [[round(s["lat"], 4), round(s["lon"], 4)] for s in trip["stops"]],
    }


def photo_out(p, stop=None) -> dict:
    d = {"file_path": p["file_path"], "basename": p["file_path"].replace("\\", "/").rsplit("/", 1)[-1],
         "captured_time": p["t"], "tag": p.get("tag") or "photo", "favorite": bool(p.get("favorite")),
         "lat": p.get("lat"), "lon": p.get("lon")}
    if stop is not None:
        d["stop"] = stop
    return d


def trip_detail(trip: dict, faces: dict | None = None) -> dict:
    stops = []
    photos = []
    for i, s in enumerate(trip["stops"]):
        picks = pick_spread(s["photos"], 8, faces)
        stops.append({
            "index": i, "name": s["name"], "lat": s["lat"], "lon": s["lon"],
            "arrive": s["arrive"], "leave": s["leave"], "photo_count": len(s["photos"]),
            "highlights": [p["file_path"] for p in picks],
        })
        photos.extend(photo_out(p, i) for p in s["photos"])
    return trip_summary(trip) | {"home": trip["home"], "stops": stops, "photos": photos}
