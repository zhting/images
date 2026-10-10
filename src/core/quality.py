"""Cheap image-quality measurements for the cleanup assistant.

Computed once per photo from the cached 1600px preview (no model, a few
milliseconds each) and stored in SQLite:

* sharpness  — variance of the Laplacian on a 1000px grey copy. Focused
  photos have strong local edges; motion blur and missed focus don't.
  Measured over the sharpest 4x4 tile, so a portrait with a soft
  background (bokeh) is judged by its subject rather than the blur
  around it.
* brightness — mean luminance 0..255 (pocket shots are nearly black;
  night shots are dark too but keep sharp detail, so both are checked).
* contrast   — luminance standard deviation (lens cap, blank wall).
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageOps

SIDE = 1000
GRID = 4

# Thresholds used by the cleanup suggestions (on the scale above).
BLURRY_BELOW = 30.0
DARK_BELOW = 22.0
DARK_MAX_SHARPNESS = 50.0   # dark *and* featureless; a starry sky or night street has detail
FLAT_BELOW = 8.0


def _laplacian(g: np.ndarray) -> np.ndarray:
    return (g[1:-1, :-2] + g[1:-1, 2:] + g[:-2, 1:-1] + g[2:, 1:-1] - 4.0 * g[1:-1, 1:-1])


def measure(img: Image.Image) -> dict:
    img = ImageOps.exif_transpose(img) if hasattr(img, "getexif") else img
    g = img.convert("L")
    if max(g.size) > SIDE:
        g.thumbnail((SIDE, SIDE), Image.Resampling.BILINEAR)
    a = np.asarray(g, dtype=np.float32)
    brightness = float(a.mean())
    contrast = float(a.std())
    if min(a.shape) < 16:
        return {"sharpness": 0.0, "brightness": brightness, "contrast": contrast}
    lap = _laplacian(a)
    h, w = lap.shape
    best = 0.0
    for i in range(GRID):
        for j in range(GRID):
            tile = lap[i * h // GRID:(i + 1) * h // GRID, j * w // GRID:(j + 1) * w // GRID]
            if tile.size:
                best = max(best, float(tile.var()))
    return {"sharpness": round(best, 2), "brightness": round(brightness, 2), "contrast": round(contrast, 2)}


def verdict(sharpness, brightness, contrast) -> str | None:
    """'dark' | 'flat' | 'blurry' | None (looks fine / not measured)."""
    if sharpness is None or sharpness < 0:
        return None
    if brightness is not None and brightness < DARK_BELOW and sharpness < DARK_MAX_SHARPNESS:
        return "dark"
    if contrast is not None and contrast < FLAT_BELOW:
        return "flat"
    if sharpness < BLURRY_BELOW:
        return "blurry"
    return None
