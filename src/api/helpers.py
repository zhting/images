"""
Shared helper functions used across multiple route modules.
"""
from functools import lru_cache


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


@lru_cache(maxsize=128)
def cached_translate(text: str, target_lang: str = "Simplified Chinese") -> str:
    """Translate text using the local offline translator (Qwen2.5)."""
    from core.translator import get_translator
    return get_translator().translate(text, target_lang=target_lang)


def cosine_similarity(v1, v2) -> float:
    """Compute cosine similarity between two vectors."""
    if v1 is None or v2 is None or len(v1) == 0 or len(v2) == 0:
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = sum(a * a for a in v1) ** 0.5
    norm2 = sum(b * b for b in v2) ** 0.5
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)
