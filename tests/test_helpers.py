"""Tests for shared helper functions."""
import pytest
import sys
import os

src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from api.helpers import is_ascii, filter_locked_items, cosine_similarity


class TestIsAscii:
    def test_ascii_string(self):
        assert is_ascii("hello world") is True

    def test_chinese_string(self):
        assert is_ascii("猫在沙发上睡觉") is False

    def test_mixed_string(self):
        assert is_ascii("hello 你好") is False

    def test_empty_string(self):
        assert is_ascii("") is True


class TestFilterLockedItems:
    def test_no_locked_folders(self):
        items = [{"file_path": "/a/b.jpg"}, {"file_path": "/c/d.jpg"}]
        result = filter_locked_items(items, [])
        assert len(result) == 2

    def test_filter_locked(self):
        items = [
            {"file_path": "C:/Photos/private/a.jpg"},
            {"file_path": "C:/Photos/public/b.jpg"},
        ]
        locked = ["C:/Photos/private"]
        result = filter_locked_items(items, locked)
        assert len(result) == 1
        assert result[0]["file_path"] == "C:/Photos/public/b.jpg"

    def test_filter_with_custom_key(self):
        items = [
            {"cover_file_path": "C:/locked/x.jpg"},
            {"cover_file_path": "C:/open/y.jpg"},
        ]
        locked = ["C:/locked"]
        result = filter_locked_items(items, locked, path_key="cover_file_path")
        assert len(result) == 1

    def test_nested_locked_path(self):
        items = [{"file_path": "C:/Photos/private/sub/deep/img.jpg"}]
        locked = ["C:/Photos/private"]
        result = filter_locked_items(items, locked)
        assert len(result) == 0


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]
        assert abs(cosine_similarity(v1, v2)) < 1e-6

    def test_opposite_vectors(self):
        v1 = [1.0, 0.0]
        v2 = [-1.0, 0.0]
        assert abs(cosine_similarity(v1, v2) - (-1.0)) < 1e-6

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0

    def test_none_vectors(self):
        assert cosine_similarity(None, [1.0]) == 0.0
