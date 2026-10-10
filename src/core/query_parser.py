"""Turn a natural-language search ("去年夏天在大理和妈妈的合照") into
structured filters plus whatever is left for semantic (SigLIP) ranking.

Rule-based on purpose: it runs on every keystroke-submitted search, needs
no model, and is predictable — every filter it extracts comes back as a
chip the user can see and remove. Only names that actually exist in the
library (cities/provinces of indexed photos, people the user has named)
are recognised as places or people, so ordinary words are never
mistaken for filters.

parse_query(q, places=[...], people={name: person_id}, now=datetime)
returns a ParsedQuery; ``chips`` lists each recognised filter together
with the exact ``token`` it was read from, so a UI can remove a filter by
deleting that token from the query string.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# --------------------------------------------------------------------------
# Result
# --------------------------------------------------------------------------


@dataclass
class ParsedQuery:
    text: str = ""                       # remainder for semantic ranking
    date_from: float | None = None       # unix seconds, inclusive
    date_to: float | None = None         # unix seconds, exclusive
    places: list = field(default_factory=list)      # matched place names
    people: list = field(default_factory=list)      # person ids
    types: list = field(default_factory=list)       # photo|video|screenshot|document
    favorite: bool = False
    ocr_terms: list = field(default_factory=list)   # must appear in the photo's text
    chips: list = field(default_factory=list)       # [{kind, label, token}]

    @property
    def has_filters(self) -> bool:
        return bool(self.date_from is not None or self.date_to is not None or self.places
                    or self.people or self.types or self.favorite or self.ocr_terms)

    def to_dict(self) -> dict:
        return {
            "text": self.text, "date_from": self.date_from, "date_to": self.date_to,
            "places": self.places, "people": self.people, "types": self.types,
            "favorite": self.favorite, "ocr_terms": self.ocr_terms, "chips": self.chips,
        }


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
           "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12, "半": 0}

_SEASONS = {"春天": (3, 5), "春季": (3, 5), "夏天": (6, 8), "夏季": (6, 8),
            "秋天": (9, 11), "秋季": (9, 11), "冬天": (12, 2), "冬季": (12, 2),
            "暑假": (7, 8), "寒假": (1, 2)}

_TYPES = [
    ("视频", "video", "视频"), ("录像", "video", "视频"),
    ("截图", "screenshot", "截图"), ("截屏", "screenshot", "截图"),
    ("文档", "document", "文档"), ("扫描件", "document", "文档"),
]
_FAVORITE_WORDS = ("我的收藏", "收藏的", "收藏", "喜欢的", "最爱")

# Words that carry no meaning once filters are pulled out. Order matters:
# longer phrases first.
_FILLERS = ["的照片", "的图片", "的相片", "照片", "图片", "相片", "拍的", "拍摄的",
            "那张", "那些", "所有的", "所有", "我的", "一起", "时候", "时拍"]
_JOINERS = "在和跟与同及的于从去到"

# Quoted text means "the photo contains this text".
_QUOTES = re.compile(r'[“"「『\'‘]([^”"」』\'’]{1,40})[”"」』\'’]')
_TEXT_PREFIX = re.compile(r'(?:文字|包含文字|写着|含有文字|带字)[:：]?\s*([^\s，,。]{1,40})')


def _cn_int(s: str) -> int | None:
    if s.isdigit():
        return int(s)
    if s in _CN_NUM:
        return _CN_NUM[s]
    if len(s) == 2 and s[0] == "十" and s[1] in _CN_NUM:
        return 10 + _CN_NUM[s[1]]
    return None


def _ts(dt: datetime) -> float:
    return dt.timestamp()


def _month_range(year: int, m1: int, m2: int):
    """[first day of m1, first day after m2) — m2 may wrap into next year."""
    start = datetime(year, m1, 1)
    end_year = year + 1 if m2 < m1 else year
    last = calendar.monthrange(end_year, m2)[1]
    end = datetime(end_year, m2, last) + timedelta(days=1)
    return start, end


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------


def parse_query(q: str, places=(), people=None, now: datetime | None = None) -> ParsedQuery:
    now = now or datetime.now()
    people = people or {}
    out = ParsedQuery()
    rest = " " + (q or "").strip() + " "

    def take(token: str):
        nonlocal rest
        rest = rest.replace(token, " ", 1)

    # --- quoted / prefixed text -> OCR terms --------------------------------
    for m in list(_QUOTES.finditer(rest)):
        term = m.group(1).strip()
        if term:
            out.ocr_terms.append(term)
            out.chips.append({"kind": "text", "label": f"含文字「{term}」", "token": m.group(0)})
            take(m.group(0))
    for m in list(_TEXT_PREFIX.finditer(rest)):
        term = m.group(1).strip()
        if term:
            out.ocr_terms.append(term)
            out.chips.append({"kind": "text", "label": f"含文字「{term}」", "token": m.group(0)})
            take(m.group(0))

    # --- time ---------------------------------------------------------------
    year = None
    year_token = None
    rel_years = {"今年": 0, "去年": 1, "前年": 2, "大前年": 3}
    for word in sorted(rel_years, key=len, reverse=True):
        if word in rest:
            year, year_token = now.year - rel_years[word], word
            break
    if year is None:
        # A 4-digit year not glued to other digits/letters ("DeepPhoto2026"
        # or "2048 游戏" are not dates), within a plausible range.
        m = re.search(r'(?<![0-9A-Za-z])((?:19|20)\d{2})(?![0-9A-Za-z])(?:\s*年)?', rest)
        if m and 1990 <= int(m.group(1)) <= now.year + 1:
            year, year_token = int(m.group(1)), m.group(0)
    if year is None:
        m = re.search(r'([一二两三四五六七八九十\d]{1,2})\s*年前', rest)
        if m and _cn_int(m.group(1)):
            year, year_token = now.year - _cn_int(m.group(1)), m.group(0)

    start = end = None
    time_label = None
    time_tokens = [year_token] if year_token else []

    m = re.search(r'([一二三四五六七八九十]{1,2}|\d{1,2})\s*月份?', rest)
    month = _cn_int(m.group(1)) if m else None
    if month and 1 <= month <= 12:
        y = year if year is not None else (now.year if month <= now.month else now.year - 1)
        start, end = _month_range(y, month, month)
        time_label = f"{y}年{month}月"
        time_tokens.append(m.group(0))
    else:
        for word, (m1, m2) in _SEASONS.items():
            if word in rest:
                y = year if year is not None else (now.year if m1 <= now.month else now.year - 1)
                start, end = _month_range(y, m1, m2)
                time_label = f"{y}年{word}"
                time_tokens.append(word)
                break

    if start is None and year is not None:
        start, end = datetime(year, 1, 1), datetime(year + 1, 1, 1)
        time_label = f"{year}年"

    if start is None:
        rel = [
            (r'最近\s*([一二两三四五六七八九十\d]{1,3})\s*(天|周|个月|月)', None),
            (r'(上个月|上月)', 'last_month'), (r'(这个月|本月)', 'this_month'),
            (r'(上周|上个星期)', 'last_week'), (r'(这周|本周|这个星期)', 'this_week'),
            (r'(昨天)', 'yesterday'), (r'(今天)', 'today'),
        ]
        for pat, kind in rel:
            m = re.search(pat, rest)
            if not m:
                continue
            today = datetime(now.year, now.month, now.day)
            if kind is None:
                n = _cn_int(m.group(1)) or 0
                days = {"天": 1, "周": 7, "个月": 30, "月": 30}[m.group(2)] * n
                start, end = today - timedelta(days=days - 1), today + timedelta(days=1)
            elif kind == 'last_month':
                first = datetime(now.year, now.month, 1)
                prev_last = first - timedelta(days=1)
                start, end = datetime(prev_last.year, prev_last.month, 1), first
            elif kind == 'this_month':
                start, end = datetime(now.year, now.month, 1), today + timedelta(days=1)
            elif kind == 'last_week':
                monday = today - timedelta(days=today.weekday())
                start, end = monday - timedelta(days=7), monday
            elif kind == 'this_week':
                start, end = today - timedelta(days=today.weekday()), today + timedelta(days=1)
            elif kind == 'yesterday':
                start, end = today - timedelta(days=1), today
            elif kind == 'today':
                start, end = today, today + timedelta(days=1)
            time_label = m.group(0).strip()
            time_tokens = [m.group(0)]
            break

    if start is not None:
        out.date_from, out.date_to = _ts(start), _ts(end)
        token = "".join(t for t in time_tokens if t)
        out.chips.append({"kind": "time", "label": time_label, "token": token})
        for t in time_tokens:
            if t:
                take(t)

    # --- places (only names present in the library) --------------------------
    names = set()
    for p in places or ():
        if not p:
            continue
        names.add(p)
        for suffix in ("市", "省", "自治区", "特别行政区", "县", "区"):
            if p.endswith(suffix) and len(p) > len(suffix) + 1:
                names.add(p[: -len(suffix)])
    lowered = rest.lower()
    for name in sorted(names, key=len, reverse=True):
        idx = lowered.find(name.lower())
        if idx == -1 or len(name) < 2:
            continue
        token = rest[idx: idx + len(name)]
        canonical = next((p for p in places if p == name or p.startswith(name)), name)
        if canonical not in out.places:
            out.places.append(canonical)
            out.chips.append({"kind": "place", "label": canonical, "token": token})
        take(token)
        lowered = rest.lower()

    # --- people (only names the user gave) -----------------------------------
    for name in sorted(people, key=len, reverse=True):
        if name and name in rest:
            pid = people[name]
            if pid not in out.people:
                out.people.append(pid)
                out.chips.append({"kind": "person", "label": name, "token": name})
            take(name)

    # --- media type / favourites --------------------------------------------
    for word, t, label in _TYPES:
        if word in rest:
            if t not in out.types:
                out.types.append(t)
                out.chips.append({"kind": "type", "label": label, "token": word})
            take(word)
    for word in _FAVORITE_WORDS:
        if word in rest:
            out.favorite = True
            out.chips.append({"kind": "favorite", "label": "收藏", "token": word})
            take(word)
            break

    # --- what is left goes to semantic search ---------------------------------
    for f in _FILLERS:
        rest = rest.replace(f, " ")
    rest = re.sub(r'[，,。.!！?？、;；:：]+', " ", rest)
    # Joiners ("在", "和", "的" ...) are dropped only when a removed filter
    # left them standing alone, so words like "和服" or "在线" survive.
    words = []
    for w in rest.split():
        if all(ch in _JOINERS for ch in w):
            continue
        w = w.strip("的")
        if w:
            words.append(w)
    out.text = " ".join(words).strip()
    return out
