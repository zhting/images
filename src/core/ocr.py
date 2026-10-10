"""Local text recognition (OCR) for photos.

Uses RapidOCR (PaddleOCR PP-OCRv3 models converted to ONNX). The models
ship inside the pip package, so nothing is downloaded at runtime and no
image leaves the machine. Recognises Chinese and English.

If the package is not installed the feature reports itself unavailable
and everything else keeps working.
"""
import threading
import logging

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

MAX_SIDE = 1600        # same size as the cached preview thumbnail
MIN_SCORE = 0.5


def available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


class OcrEngine:
    def __init__(self):
        self._engine = None
        # Separate locks: recognize() holds _run_lock while _get() may need
        # to load the model under _load_lock. (One shared non-reentrant lock
        # deadlocked on the very first call.)
        self._load_lock = threading.Lock()
        self._run_lock = threading.Lock()

    def _get(self):
        if self._engine is None:
            with self._load_lock:
                if self._engine is None:
                    from rapidocr_onnxruntime import RapidOCR
                    self._engine = RapidOCR()
                    logger.info("[OCR] RapidOCR engine loaded")
        return self._engine

    def recognize(self, image: Image.Image) -> str:
        """Text lines in reading order (top-to-bottom, left-to-right),
        joined with newlines; '' when the photo has no readable text."""
        img = image.convert("RGB")
        if max(img.size) > MAX_SIDE:
            img = img.copy()
            img.thumbnail((MAX_SIDE, MAX_SIDE))
        arr = np.asarray(img)[:, :, ::-1].copy()   # RGB -> BGR (OpenCV order)
        engine = self._get()
        with self._run_lock:                       # one inference at a time
            result, _ = engine(arr)
        lines = []
        for box, text, score in result or []:
            try:
                if float(score) < MIN_SCORE or not str(text).strip():
                    continue
                top = min(p[1] for p in box)
                left = min(p[0] for p in box)
            except Exception:
                continue
            lines.append((round(top / 12), left, str(text).strip()))
        lines.sort()
        return "\n".join(t for _, _, t in lines)


engine = OcrEngine()
