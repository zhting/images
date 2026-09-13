"""
Shared helper functions used across multiple route modules.
"""
import threading
from collections import OrderedDict

import numpy as np


def is_ascii(s: str) -> bool:
    """Return True if the string contains only ASCII characters."""
    return all(ord(c) < 128 for c in s)


def filter_locked_items(items: list, locked_folders: list, path_key: str = 'file_path') -> list:
    """Filter out items whose path falls within a locked folder."""
    if not locked_folders:
        return items

    filtered = []
    for item in items:
        path = item.get(path_key)
        if not path:
            continue
        norm_path = path.replace("\\", "/").rstrip("/")
        is_locked = any(
            norm_path == lp or norm_path.startswith(lp + "/")
            for lp in locked_folders
        )
        if not is_locked:
            filtered.append(item)
    return filtered


_TRANSLATE_CACHE_MAX = 128
_translate_cache: "OrderedDict[tuple, str]" = OrderedDict()
_translate_lock = threading.Lock()


def cached_translate(text: str, target_lang: str = "Simplified Chinese") -> str:
    """Translate text using the local offline translator (Qwen2.5).

    Only *successful* translations are cached. The translator returns its
    input unchanged when the Qwen model has not finished loading or when
    generation raises, and caching that would be permanent: a query typed
    during preheat would skip translation for the rest of the process and
    silently search the vision index with untranslated text. Re-translating
    the rare text that legitimately equals its own translation is the
    cheaper mistake.
    """
    key = (text, target_lang)
    with _translate_lock:
        hit = _translate_cache.get(key)
        if hit is not None:
            _translate_cache.move_to_end(key)
            return hit

    from core.translator import get_translator
    result = get_translator().translate(text, target_lang=target_lang)

    if result and result != text:
        with _translate_lock:
            _translate_cache[key] = result
            _translate_cache.move_to_end(key)
            while len(_translate_cache) > _TRANSLATE_CACHE_MAX:
                _translate_cache.popitem(last=False)
    return result


def clear_translate_cache():
    """Drop memoized translations (used by tests and config changes)."""
    with _translate_lock:
        _translate_cache.clear()


def cosine_similarity(v1, v2) -> float:
    """Compute cosine similarity between two vectors.

    numpy rather than Python loops: burst detection calls this once per
    adjacent pair on a timeline page, and each call walked three Python
    loops over a 1152-dim vector.
    """
    if v1 is None or v2 is None or len(v1) == 0 or len(v2) == 0:
        return 0.0
    a = np.asarray(v1, dtype=np.float64)
    b = np.asarray(v2, dtype=np.float64)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def compute_file_hash(path: str, sample_threshold: int = 32 * 1024 * 1024) -> str:
    """Content hash for duplicate detection.

    Files up to *sample_threshold* get a full MD5. Larger files (mostly
    videos) get a sampled hash — first 4MB + last 4MB + file size — so
    we never stream multi-GB files just to fingerprint them. The 'S'
    prefix keeps sampled hashes from ever colliding with full ones.
    """
    import hashlib
    import os as _os
    size = _os.path.getsize(path)
    h = hashlib.md5()
    with open(path, 'rb') as f:
        if size <= sample_threshold:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
            return h.hexdigest()
        sample = min(4 * 1024 * 1024, size // 2)
        h.update(f.read(sample))
        f.seek(size - sample)
        h.update(f.read(sample))
        h.update(str(size).encode())
        return 'S' + h.hexdigest()
