"""Background OCR of the library, one photo at a time, at low priority.

Runs on its own daemon thread rather than the shared TaskRunner queue:
OCR of a large library takes hours, and the runner executes one job at a
time, so a backfill there would hold up the next indexing run. This
worker instead yields — it pauses while a scan or index is running and
when OCR is switched off in Settings (config key ``ocr_enabled``).

Order: screenshots and documents first (that is where most text is),
then everything else newest first. Already-processed photos are skipped;
re-indexed photos lose their text row and are read again.
"""
import os
import threading
import time
import logging

from PIL import Image

from core import ocr

logger = logging.getLogger(__name__)

BATCH = 25
IDLE_SLEEP = 30.0      # nothing to do
PAUSE_SLEEP = 5.0      # indexing running / disabled
BETWEEN_PHOTOS = 0.05  # keep the machine responsive


class OcrWorker:
    def __init__(self, get_store, get_progress_state, engine=None, thumbnail_path=None):
        self._get_store = get_store
        self._get_progress_state = get_progress_state
        self._engine = engine or ocr.engine
        self._thumbnail_path = thumbnail_path
        self._thread = None
        self._wake = threading.Event()
        self._stop = threading.Event()
        self.state = "idle"        # idle | running | paused | disabled | unavailable
        self.current = ""
        self.done_this_session = 0
        self.last_error = ""

    # ------------------------------------------------------------------
    def enabled(self) -> bool:
        try:
            return str(self._get_store().get_config("ocr_enabled", "true")).lower() not in ("false", "0", "off")
        except Exception:
            return False

    def busy_indexing(self) -> bool:
        try:
            return self._get_progress_state() in ("scanning", "indexing")
        except Exception:
            return False

    def start(self):
        if not ocr.available():
            self.state = "unavailable"
            logger.info("[OCR] rapidocr_onnxruntime not installed; text search disabled")
            return
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ocr-worker")
        self._thread.start()

    def wake(self):
        self._wake.set()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def status(self) -> dict:
        store = self._get_store()
        try:
            pending = store.count_ocr_pending()
            done = store.count_ocr_done()
        except Exception:
            pending = done = 0
        state = self.state
        if state != "unavailable" and not self.enabled():
            state = "disabled"
        return {"state": state, "pending": pending, "done": done,
                "current": os.path.basename(self.current) if self.current else "",
                "available": state != "unavailable"}

    # ------------------------------------------------------------------
    def _load(self, path: str):
        """Prefer the cached 1600px preview: much cheaper than decoding a
        12-48 MP original (or a HEIC), and it is already upright."""
        if self._thumbnail_path:
            try:
                thumb = self._thumbnail_path(path)
                if thumb and os.path.exists(thumb):
                    with Image.open(thumb) as im:
                        im.load()
                        return im.copy()
            except Exception:
                pass
        with Image.open(path) as im:
            im.load()
            return im.copy()

    def process_one(self, path: str):
        store = self._get_store()
        self.current = path
        try:
            if not os.path.exists(path):
                text = ""
            else:
                text = self._engine.recognize(self._load(path))
        except Exception as e:
            # Unreadable file: record it as processed (no text) so the
            # worker does not retry it forever.
            self.last_error = f"{os.path.basename(path)}: {e}"
            logger.warning(f"[OCR] {self.last_error}")
            text = ""
        store.set_photo_text(path, text)
        self.done_this_session += 1
        self.current = ""

    def run_batch(self) -> int:
        """Process up to BATCH photos; returns how many were processed."""
        paths = self._get_store().get_ocr_pending(limit=BATCH)
        n = 0
        for p in paths:
            if self._stop.is_set() or not self.enabled() or self.busy_indexing():
                break
            self.process_one(p)
            n += 1
            time.sleep(BETWEEN_PHOTOS)
        return n

    def _loop(self):
        while not self._stop.is_set():
            if not self.enabled():
                self.state = "disabled"
                self._wake.wait(PAUSE_SLEEP); self._wake.clear()
                continue
            if self.busy_indexing():
                self.state = "paused"
                self._wake.wait(PAUSE_SLEEP); self._wake.clear()
                continue
            try:
                self.state = "running"
                n = self.run_batch()
            except Exception as e:
                self.last_error = str(e)
                logger.exception("[OCR] batch failed")
                n = 0
            if n == 0:
                self.state = "idle"
                self._wake.wait(IDLE_SLEEP); self._wake.clear()


_worker = None


def get_worker() -> OcrWorker:
    global _worker
    if _worker is None:
        from api.state import get_store, state
        from core.thumbnails import thumbnail_service
        _worker = OcrWorker(
            get_store,
            lambda: getattr(getattr(state, "progress", None), "state", "idle"),
            thumbnail_path=lambda p: thumbnail_service.get_thumbnail(p, "preview"),
        )
    return _worker
