"""Background quality pass for the cleanup assistant.

For every photo it records sharpness / brightness / contrast (see
``core.quality``) from the cached preview, and for every file its size on
disk. A photo takes a few milliseconds, so a 100k library is done in
minutes; like the OCR worker it runs on its own thread, newest photos
first, and steps aside while a scan or index is running.
"""
import os
import threading
import time
import logging

from PIL import Image

from core import quality

logger = logging.getLogger(__name__)

BATCH = 50
IDLE_SLEEP = 30.0
PAUSE_SLEEP = 5.0
BETWEEN_PHOTOS = 0.01
NOT_AN_IMAGE = -1.0     # videos / unreadable files: measured, nothing to judge


class QualityWorker:
    def __init__(self, get_store, get_progress_state, thumbnail_path=None):
        self._get_store = get_store
        self._get_progress_state = get_progress_state
        self._thumbnail_path = thumbnail_path
        self._thread = None
        self._wake = threading.Event()
        self._stop = threading.Event()
        self.state = "idle"          # idle | running | paused
        self.last_error = ""

    def busy_indexing(self) -> bool:
        try:
            return self._get_progress_state() in ("scanning", "indexing")
        except Exception:
            return False

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="quality-worker")
        self._thread.start()

    def wake(self):
        self._wake.set()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def status(self) -> dict:
        store = self._get_store()
        try:
            return {"state": self.state, "pending": store.count_quality_pending(),
                    "done": store.count_quality_done()}
        except Exception:
            return {"state": self.state, "pending": 0, "done": 0}

    def _load(self, path: str):
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
            im.draft("RGB", (quality.SIDE, quality.SIDE))   # fast JPEG downscale on decode
            im.load()
            return im.copy()

    def process_one(self, path: str, tag: str):
        store = self._get_store()
        try:
            size = os.path.getsize(path)
        except OSError:
            size = None
        m = {"sharpness": NOT_AN_IMAGE, "brightness": None, "contrast": None}
        if tag != "video" and size is not None:
            try:
                m = quality.measure(self._load(path))
            except Exception as e:
                self.last_error = f"{os.path.basename(path)}: {e}"
                logger.warning(f"[Quality] {self.last_error}")
        store.set_quality(path, m["sharpness"], m["brightness"], m["contrast"], size)

    def run_batch(self) -> int:
        rows = self._get_store().get_quality_pending(limit=BATCH)
        n = 0
        for path, tag in rows:
            if self._stop.is_set() or self.busy_indexing():
                break
            self.process_one(path, tag)
            n += 1
            time.sleep(BETWEEN_PHOTOS)
        return n

    def _loop(self):
        while not self._stop.is_set():
            if self.busy_indexing():
                self.state = "paused"
                self._wake.wait(PAUSE_SLEEP); self._wake.clear()
                continue
            try:
                self.state = "running"
                n = self.run_batch()
            except Exception as e:
                self.last_error = str(e)
                logger.exception("[Quality] batch failed")
                n = 0
            if n == 0:
                self.state = "idle"
                self._wake.wait(IDLE_SLEEP); self._wake.clear()


_worker = None


def get_worker() -> QualityWorker:
    global _worker
    if _worker is None:
        from api.state import get_store, state
        from core.thumbnails import thumbnail_service
        _worker = QualityWorker(
            get_store,
            lambda: getattr(getattr(state, "progress", None), "state", "idle"),
            thumbnail_path=lambda p: thumbnail_service.get_thumbnail(p, "preview"),
        )
    return _worker
