import os
import hashlib
import threading
from PIL import Image, ImageOps

import logging
logger = logging.getLogger(__name__)


class ThumbnailService:
    """Two-size WebP thumbnail cache.

    Sizes
    -----
    grid    360px  — timeline / search grids
    preview 1600px — gallery first frame (originals load only on demand)

    Generation happens primarily at *index time* via generate_from_image
    (the sync pipeline already holds a decoded PIL image, so both sizes
    cost one extra resize each — no second decode).  Request-time
    generation remains as a fallback for cache misses, capped by a
    semaphore so a fast scroll can't stampede the CPU with dozens of
    concurrent full-resolution decodes.
    """

    SIZES = {"grid": 360, "preview": 1600}
    _VIDEO_EXTS = ('.mp4', '.mov', '.avi', '.mkv')

    def __init__(self, cache_dir="./assets/.cache/thumbnails"):
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
        # At most 2 on-demand generations at once; index-time generation
        # is unaffected (it goes through generate_from_image directly).
        self._on_demand_gate = threading.Semaphore(2)

    # ------------------------------------------------------------------
    # Paths & validity
    # ------------------------------------------------------------------

    def get_thumbnail_path(self, file_path: str, size: str = "grid") -> str:
        hash_name = hashlib.md5(file_path.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, f"{hash_name}_{size}.webp")

    def _is_valid(self, thumb_path: str, src_path: str) -> bool:
        return (os.path.exists(thumb_path)
                and os.path.getmtime(thumb_path) >= os.path.getmtime(src_path))

    # ------------------------------------------------------------------
    # Index-time generation (image already decoded by the sync pipeline)
    # ------------------------------------------------------------------

    def generate_from_image(self, file_path: str, img: Image.Image):
        """Write all sizes from an in-memory image. Called by the sync
        pipeline right after it decoded the original for the model —
        one decode feeds the embedding, the score AND the thumbnails."""
        img = ImageOps.exif_transpose(img)
        if img.mode not in ('RGB',):
            img = img.convert('RGB')
        for size_name, px in self.SIZES.items():
            try:
                thumb = img.copy()
                thumb.thumbnail((px, px), Image.Resampling.LANCZOS)
                thumb.save(self.get_thumbnail_path(file_path, size_name),
                           "WEBP", quality=82, method=4)
            except Exception as e:
                logger.error(f"[Thumbnails] {size_name} failed for {file_path}: {e}")

    # ------------------------------------------------------------------
    # Request-time lookup (with on-demand fallback)
    # ------------------------------------------------------------------

    def get_thumbnail(self, file_path: str, size: str = "grid") -> str:
        """Return the cached thumbnail path for *size*, generating it on
        demand if missing or stale. Returns None on failure — callers
        must serve a placeholder, never the original file."""
        if size not in self.SIZES:
            size = "grid"
        if not os.path.exists(file_path):
            return None

        thumb_path = self.get_thumbnail_path(file_path, size)
        if self._is_valid(thumb_path, file_path):
            return thumb_path

        with self._on_demand_gate:
            # Another request may have produced it while we waited.
            if self._is_valid(thumb_path, file_path):
                return thumb_path
            try:
                img = self._decode(file_path)
                if img is None:
                    return None
                self.generate_from_image(file_path, img)
                return thumb_path if os.path.exists(thumb_path) else None
            except Exception as e:
                logger.error(f"Error generating thumbnail for {file_path}: {e}")
                return None

    def _decode(self, file_path: str):
        lower = file_path.lower()
        if lower.endswith(self._VIDEO_EXTS):
            import cv2
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return None
            cap.set(cv2.CAP_PROP_POS_FRAMES, 30)  # ~1s in at 30fps
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
            cap.release()
            if not ret:
                return None
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return Image.fromarray(frame)
        with Image.open(file_path) as img:
            img.load()
            return img


# Singleton instance
thumbnail_service = ThumbnailService()
