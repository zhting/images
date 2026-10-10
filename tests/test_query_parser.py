"""Natural-language search -> filters + semantic remainder."""
from datetime import datetime

import pytest

from core.query_parser import parse_query

NOW = datetime(2026, 10, 10, 15, 0)
PLACES = ["大理市", "杭州", "云南", "Dali", "Beijing"]
PEOPLE = {"妈妈": 3, "小明": 7}


def P(q):
    return parse_query(q, places=PLACES, people=PEOPLE, now=NOW)


def rng(p):
    return (datetime.fromtimestamp(p.date_from), datetime.fromtimestamp(p.date_to))


def test_full_sentence():
    p = P("去年夏天在大理和妈妈的合照")
    assert rng(p) == (datetime(2025, 6, 1), datetime(2025, 9, 1))
    assert p.places == ["大理市"]
    assert p.people == [3]
    assert p.text == "合照"
    assert [c["kind"] for c in p.chips] == ["time", "place", "person"]


@pytest.mark.parametrize("q, start, end, text", [
    ("2024年3月 杭州", datetime(2024, 3, 1), datetime(2024, 4, 1), ""),
    ("三月的樱花", datetime(2026, 3, 1), datetime(2026, 4, 1), "樱花"),
    ("十二月 雪", datetime(2025, 12, 1), datetime(2026, 1, 1), "雪"),      # future month -> last year
    ("去年冬天", datetime(2025, 12, 1), datetime(2026, 3, 1), ""),        # wraps the year
    ("2023年", datetime(2023, 1, 1), datetime(2024, 1, 1), ""),
    ("三年前 海边", datetime(2023, 1, 1), datetime(2024, 1, 1), "海边"),
    ("上个月", datetime(2026, 9, 1), datetime(2026, 10, 1), ""),
    ("最近7天", datetime(2026, 10, 4), datetime(2026, 10, 11), ""),
    ("昨天", datetime(2026, 10, 9), datetime(2026, 10, 10), ""),
])
def test_time_expressions(q, start, end, text):
    p = P(q)
    assert rng(p) == (start, end)
    assert p.text == text


def test_numbers_that_are_not_years():
    assert P("2048 游戏").date_from is None
    assert P("密码DeepPhoto2026").date_from is None


def test_quoted_and_prefixed_text_become_ocr_terms():
    p = P('包含 "发票" 的照片')
    assert p.ocr_terms == ["发票"]
    assert p.text == "包含"
    assert P("文字:WiFi密码").ocr_terms == ["WiFi密码"]
    assert P("「会议纪要」 截图").ocr_terms == ["会议纪要"]


def test_types_and_favorites():
    p = P("上个月的截图")
    assert p.types == ["screenshot"] and p.text == ""
    p = P("收藏的猫")
    assert p.favorite and p.text == "猫"
    assert P("小明的视频").types == ["video"]
    assert P("小明的视频").people == [7]


def test_words_containing_joiners_survive():
    assert P("和服").text == "和服"
    assert P("在线课程截图").text == "在线课程"


def test_only_known_places_and_people():
    p = P("北京 爸爸")          # neither is in the library
    assert p.places == [] and p.people == [] and p.text == "北京 爸爸"
    p = P("dali trip")
    assert p.places == ["Dali"] and p.text == "trip"
    p = P("云南大理")             # both a province and a city
    assert set(p.places) == {"云南", "大理市"}


def test_plain_semantic_query_has_no_filters():
    p = P("猫在沙发上睡觉")
    assert not p.has_filters
    assert p.text == "猫在沙发上睡觉"


def test_chip_tokens_remove_cleanly():
    q = "去年夏天在大理和妈妈的合照"
    for chip in P(q).chips:
        reduced = q.replace(chip["token"], "", 1)
        assert chip["kind"] not in [c["kind"] for c in P(reduced).chips]
