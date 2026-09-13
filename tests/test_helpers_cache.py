"""Translation memoization and vector similarity.

The translate cache is the subtle one: the offline translator returns its
input unchanged when the Qwen model has not loaded yet or generation
raises, and memoizing that would permanently disable translation for the
query — every later search would hit the vision index with untranslated
text.
"""
import sys
import types

import numpy as np
import pytest

from api.helpers import cached_translate, clear_translate_cache, cosine_similarity


class FakeTranslator:
    """Stands in for the Qwen translator; counts real generations."""

    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = 0

    def translate(self, text, target_lang="Simplified Chinese"):
        self.calls += 1
        return self.behaviour(text)


@pytest.fixture
def translator(monkeypatch):
    """Install a fake core.translator and clear the cache around each test."""
    clear_translate_cache()
    holder = {}

    def install(behaviour):
        fake = FakeTranslator(behaviour)
        module = types.ModuleType("core.translator")
        module.get_translator = lambda: fake
        monkeypatch.setitem(sys.modules, "core.translator", module)
        holder["fake"] = fake
        return fake

    yield install
    clear_translate_cache()


def test_successful_translation_is_memoized(translator):
    fake = translator(lambda t: "sunset over the sea")

    first = cached_translate("海边的日落")
    second = cached_translate("海边的日落")

    assert first == second == "sunset over the sea"
    assert fake.calls == 1, "a successful translation must only be generated once"


def test_a_failed_translation_is_not_memoized(translator):
    """The translator echoes its input on failure — that must not stick."""
    fake = translator(lambda t: t)

    assert cached_translate("海边的日落") == "海边的日落"
    assert cached_translate("海边的日落") == "海边的日落"

    assert fake.calls == 2, "an echoed (failed) translation must be retried"


def test_recovers_once_the_model_finishes_loading(translator):
    """A query typed during preheat must translate correctly afterwards."""
    state = {"ready": False}
    fake = translator(lambda t: "sunset over the sea" if state["ready"] else t)

    assert cached_translate("海边的日落") == "海边的日落"   # model still loading
    state["ready"] = True
    assert cached_translate("海边的日落") == "sunset over the sea"
    assert fake.calls == 2


def test_empty_translation_is_not_memoized(translator):
    fake = translator(lambda t: "")

    cached_translate("海边的日落")
    cached_translate("海边的日落")

    assert fake.calls == 2


def test_target_language_is_part_of_the_key(translator):
    fake = translator(lambda t: f"translated:{t}")

    cached_translate("猫", target_lang="English")
    cached_translate("猫", target_lang="French")

    assert fake.calls == 2


def test_cache_is_bounded(translator):
    from api.helpers import _TRANSLATE_CACHE_MAX, _translate_cache

    translator(lambda t: f"translated:{t}")
    for i in range(_TRANSLATE_CACHE_MAX + 50):
        cached_translate(f"查询{i}")

    assert len(_translate_cache) <= _TRANSLATE_CACHE_MAX


class TestCosineSimilarity:
    def _reference(self, v1, v2):
        dot = sum(a * b for a, b in zip(v1, v2, strict=True))
        n1 = sum(a * a for a in v1) ** 0.5
        n2 = sum(b * b for b in v2) ** 0.5
        return 0.0 if n1 == 0 or n2 == 0 else dot / (n1 * n2)

    def test_matches_the_scalar_reference(self):
        rng = np.random.default_rng(7)
        for dim in (8, 512, 1152):
            a = rng.normal(size=dim)
            b = rng.normal(size=dim)
            assert cosine_similarity(a, b) == pytest.approx(self._reference(a, b))

    def test_identical_vectors_score_one(self):
        v = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_score_zero(self):
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite_vectors_score_minus_one(self):
        assert cosine_similarity([1, 1], [-1, -1]) == pytest.approx(-1.0)

    @pytest.mark.parametrize("a,b", [(None, [1]), ([1], None), ([], [1]), ([1], [])])
    def test_missing_vectors_score_zero(self, a, b):
        assert cosine_similarity(a, b) == 0.0

    def test_zero_vector_scores_zero_without_dividing_by_zero(self):
        assert cosine_similarity([0, 0], [1, 1]) == 0.0

    def test_accepts_float32_rows_as_chroma_returns_them(self):
        rng = np.random.default_rng(3)
        a = rng.normal(size=1152).astype("float32")
        b = rng.normal(size=1152).astype("float32")
        assert -1.0 <= cosine_similarity(a, b) <= 1.0
