import os
from database.vector_db import VectorDB
from core.models import VisionModel
from database.sqlite_store import SQLiteStore
from core.location_processor import LocationProcessor
from core.tag_generator import TagGenerator
from core.face_processor import FaceProcessor
from core.video_processor import VideoProcessor
from PIL import Image, UnidentifiedImageError
import datetime
import json
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import logging
from api.helpers import compute_file_hash
from core.thumbnails import thumbnail_service

logger = logging.getLogger(__name__)
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv')


def _exif_timestamp(img: Image.Image):
    """Capture time from an already-open image's EXIF, or None."""
    try:
        exif = img.getexif()
        if exif:
            # 36867 = DateTimeOriginal, 306 = DateTime
            date_str = exif.get(36867) or exif.get(306)
            if date_str:
                # Format: YYYY:MM:DD HH:MM:SS
                dt = datetime.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                return int(dt.timestamp())
    except Exception:
        pass
    return None


def get_image_timestamp(file_path: str) -> int:
    """
    Extracts the earliest timestamp from EXIF data or falls back to file modification time.
    Returns unix timestamp (int).
    """
    try:
        # `with`: this used to leak one open file handle per call.
        with Image.open(file_path) as img:
            ts = _exif_timestamp(img)
            if ts is not None:
                return ts
    except Exception:
        pass

    # Fallback to mtime
    return int(os.path.getmtime(file_path))


def _safe_mtime(path: str, fs_files: dict) -> int:
    if path in fs_files:
        return fs_files[path]
    try:
        return int(os.path.getmtime(path))
    except OSError:
        return 0


@dataclass
class _Prepared:
    """Everything about one still image that does not need the vision
    model, produced on a worker thread. Holds the small model-input tensor
    rather than the decoded original, so a full prefetch window costs a
    few MB instead of hundreds."""
    path: str
    file_hash: str
    mtime: int
    captured: int
    coords: tuple = None
    pixels: object = None
    faces: list = field(default_factory=list)


@dataclass
class _Failed:
    path: str
    error: Exception


class SyncManager:
    def __init__(self, db: VectorDB, model: VisionModel, store: SQLiteStore):
        self.db = db
        self.model = model
        self.store = store
        
        # Initialize Smart Processors
        self.location_processor = LocationProcessor()
        self.tag_generator = TagGenerator(model)
        self.face_processor = FaceProcessor() # GPU if onnxruntime-gpu is present
        self.video_processor = VideoProcessor()

        # Face detection runs on the prep workers so it overlaps with the
        # vision model, but one at a time: onnxruntime already uses every
        # core per call, and N concurrent calls would just thrash.
        self._face_gate = threading.Semaphore(1)
        self._error_vec = None
        
        # Ensure faces table exists
        self.store.create_faces_table()

    # Supported file extensions
    SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.heic', '.heif', '.mp4', '.mov', '.avi', '.mkv')

    def _mark_file_as_error(self, path: str, file_mtime: int, error_msg: str):
        """
        Inserts a dummy record for unreadable/corrupt files with 'error' tag.
        This prevents the scanner from retrying them infinitely.
        """
        # Create a zero vector of the same dimension as the model output
        # E.g. 512 for SigLIP base. We can query the model if we wanted, or just assume 512.
        # Alternatively, model.encode(dummy_image)
        try:
            # Placeholder vector with the model's dimensionality: the
            # embedding of a tiny black image, computed once per process
            # instead of a full vision pass for every corrupt file.
            if self._error_vec is None:
                dummy_img = Image.new('RGB', (10, 10), color='black')
                self._error_vec = self.model.encode(dummy_img)
            vec = self._error_vec

            self.db.insert(
                vec, path, "hash", file_mtime,
                captured_time=_safe_mtime(path, {}),
                aesthetic_score=0.0,
                tag="error",
                location_info=None,
                auto_tags=["error: " + str(error_msg)]
            )
            logger.error(f"[SyncManager] Marked {os.path.basename(path)} as error to avoid retry loop.")
        except Exception as e:
            logger.error(f"[SyncManager] Failed to mark error placeholder for {path}: {e}")

        # Write to error log for manual review/deletion by the user
        try:
            import datetime
            log_path = os.path.join(os.getcwd(), "error_media.log")
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] REASON: {error_msg} | FILE: {path}\n")
        except Exception as log_e:
            logger.error(f"[SyncManager] Failed to write to error log: {log_e}")

    def _scandir_recursive(self, path, dir_cache, status_callback=None):
        """
        Recursively scan directory using os.scandir (faster than os.walk).
        Uses directory mtime caching to skip unchanged directories.
        Returns list of (file_path, mtime) tuples.
        """
        results = []
        try:
            dir_mtime = int(os.path.getmtime(path))
            cached_mtime = dir_cache.get(path)
            
            # If directory hasn't changed and we have cache, we still need to scan
            # because subdirectory changes don't update parent mtime.
            # However, we can skip status callback for unchanged dirs.
            should_report = cached_mtime is None or dir_mtime > cached_mtime
            
            if status_callback and should_report:
                status_callback(f"正在扫描: {path} ...")
            
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            # Recurse into subdirectory
                            results.extend(self._scandir_recursive(entry.path, dir_cache, status_callback))
                        elif entry.is_file() and entry.name.lower().endswith(self.SUPPORTED_EXTENSIONS):
                            stat_info = entry.stat()
                            results.append((entry.path, int(stat_info.st_mtime)))
                    except (PermissionError, OSError):
                        continue
                        
        except (PermissionError, OSError):
            pass
        return results

    def _scan_single_root(self, root_path, dir_cache, status_callback=None):
        """Scan a single root path. Used for parallel execution."""
        if not os.path.exists(root_path):
            return []
        return self._scandir_recursive(root_path, dir_cache, status_callback)

    def scan_files(self, force_simulation: bool = False, status_callback=None):
        """
        Scans filesystem and DB to calculate diffs.
        Optimized with: os.scandir, parallel scanning, directory mtime cache.
        Returns dict with 'to_add', 'to_update', 'to_delete' lists.
        """
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        start_time = time.time()
        logger.info("[SyncManager] Starting optimized file scan...")
        
        asset_paths = self.store.get_asset_paths()
        if not asset_paths:
            return {"to_add": [], "to_update": [], "to_delete": []}

        # 1. Get DB State
        # P1a stage 3: read indexed state from SQLite (kept in lockstep by
        # the dual-write mirror); fall back to paging Chroma pre-migration.
        if self.store.has_photos():
            db_files = self.store.get_photo_sync_states()
        else:
            db_files = self.db.get_all_files()
        
        # 2. Load directory mtime cache (for future optimization)
        dir_cache = self.store.get_config("dir_mtime_cache", {})
        if isinstance(dir_cache, str):
            try:
                dir_cache = json.loads(dir_cache)
            except Exception:
                dir_cache = {}
        
        # 3. Parallel scan all asset roots
        fs_files = {}
        
        # Use ThreadPoolExecutor for parallel scanning
        # Thread-safe status callback wrapper
        import threading
        callback_lock = threading.Lock()
        
        def safe_callback(msg):
            if status_callback:
                with callback_lock:
                    status_callback(msg)
        
        with ThreadPoolExecutor(max_workers=min(len(asset_paths), 4)) as executor:
            futures = {
                executor.submit(self._scan_single_root, p, dir_cache, safe_callback): p 
                for p in asset_paths
            }
            
            for future in as_completed(futures):
                try:
                    results = future.result()
                    for file_path, mtime in results:
                        fs_files[file_path] = mtime
                except Exception as e:
                    logger.error(f"[SyncManager] Scan error: {e}")

        scan_time = time.time() - start_time
        logger.info(f"[SyncManager] Scanned {len(fs_files)} files in {scan_time:.2f}s")

        # 4. Calculate Diff (Normalized)
        to_add = []
        to_update = []
        to_delete = []

        # Prepare normalized maps for comparison
        # DB: norm_path -> (original_path, mtime)
        norm_db_files = {}
        for p, t in db_files.items():
            norm_db_files[os.path.normcase(os.path.abspath(p))] = (p, t)

        # FS: norm_path -> (original_path, mtime)
        norm_fs_files = {}
        for p, t in fs_files.items():
            norm_fs_files[os.path.normcase(os.path.abspath(p))] = (p, t)

        # Compare using normalized paths
        for norm_p, (fs_path, fs_mtime) in norm_fs_files.items():
            if force_simulation:
                to_add.append(fs_path)
                continue
                
            if norm_p not in norm_db_files:
                to_add.append(fs_path)
            else:
                db_path, db_mtime = norm_db_files[norm_p]
                # Update if mtime changed
                if fs_mtime > db_mtime:
                    to_update.append(fs_path)
        
        # Check for deletions
        # We only delete if it belonged to our asset roots but is no longer in FS
        norm_asset_roots = [os.path.normcase(os.path.abspath(p)) for p in asset_paths]
        
        for norm_p, (db_path, _db_mtime) in norm_db_files.items():
            belongs = False
            for norm_root in norm_asset_roots:
                if norm_p.startswith(norm_root):
                    belongs = True
                    break
            
            if belongs and norm_p not in norm_fs_files:
                to_delete.append(db_path)
        
        return {
            "to_add": to_add,
            "to_update": to_update,
            "to_delete": to_delete,
            "fs_files": fs_files # Carry over to avoid re-stat
        }

    # Tags that strongly imply a real photo rather than a scanned page; used
    # to walk back an over-eager 'document' classification.
    _NON_DOC_TAGS = {
        'scissors', 'toy', 'food', 'fruit', 'vegetable', 'cat', 'dog', 'animal',
        'child', 'boy', 'girl', 'person', 'woman', 'man', 'baby', 'face', 'human body', 'hand',
        'car', 'vehicle', 'tree', 'flower', 'sky', 'cloud', 'nature', 'party', 'wedding', 'eating'
    }

    # ------------------------------------------------------------------
    # Indexing pipeline
    #
    #   prep workers (threads)                 main thread
    #   ─────────────────────                  ───────────
    #   hash · decode · EXIF/GPS · capture  ─▶  batch of N  ─▶ SigLIP (one pass)
    #   time · thumbnails · model resize ·      ─▶ tags · location names ·
    #   face detection                           faces/DB writes (one upsert)
    #
    # Previously every step ran back to back on one thread, one photo at a
    # time, so the CPU sat idle during file I/O and the GPU sat idle during
    # JPEG/HEIC decoding. Results are identical: the same functions run on
    # the same pixels, only where and when changes.
    # ------------------------------------------------------------------

    def _pipeline_sizes(self):
        """(commit batch, prep workers). Inference batch: see _infer_batch."""
        on_gpu = getattr(self.model, "device", "cpu") == "cuda"
        batch = int(os.environ.get("DEEPPHOTO_INDEX_BATCH", 16 if on_gpu else 4))
        workers = int(os.environ.get(
            "DEEPPHOTO_INDEX_WORKERS", min(4, max(1, (os.cpu_count() or 2) - 1))))
        return max(1, batch), max(1, workers)

    def _infer_batch(self) -> int:
        """Images per forward pass. On CUDA batching is the main win; on CPU
        SO400M is already compute-bound at batch 1 and measured ~5% *slower*
        per image at batch 4, so CPU infers one at a time while DB commits
        stay batched."""
        on_gpu = getattr(self.model, "device", "cpu") == "cuda"
        return max(1, int(os.environ.get("DEEPPHOTO_INFER_BATCH", 16 if on_gpu else 1)))

    def _model_input(self, img: Image.Image):
        preprocess = getattr(self.model, "preprocess", None)
        return preprocess(img) if callable(preprocess) else img

    def _detect_faces(self, img: Image.Image):
        with self._face_gate:
            return self.face_processor.detect_faces(img)

    def _prepare_image(self, path, fs_files) -> _Prepared:
        """Worker-thread half of indexing one still image."""
        # Open original for location (exif). `with` matters: the indexer
        # walks tens of thousands of files, and a leaked handle per photo
        # exhausts the fd table (and blocks deletes on Windows).
        with Image.open(path) as img_original:
            img_original.load()
            return self._prepare_loaded(path, img_original, fs_files)

    def _prepare_loaded(self, path, img_original, fs_files) -> _Prepared:
        try:
            file_hash_val = compute_file_hash(path)
        except Exception:
            file_hash_val = ""

        # GPS must come from the original to preserve EXIF; turning it into
        # a place name happens on the main thread (see location_from_coords).
        coords = self.location_processor.get_lat_lon(img_original)
        captured = _exif_timestamp(img_original)

        # Pre-generate thumbnails from the image we already decoded — the
        # request path then becomes plain static file serving.
        try:
            thumbnail_service.generate_from_image(path, img_original)
        except Exception as e:
            logger.error(f"[SyncManager] thumbnail pre-generation failed for {path}: {e}")

        # Convert for model (stripping exif is fine for the model)
        img = img_original.convert('RGB')
        pixels = self._model_input(img)
        faces = self._detect_faces(img)

        mtime = _safe_mtime(path, fs_files)
        if captured is None:
            captured = mtime if path in fs_files else int(os.path.getmtime(path))
        return _Prepared(path=path, file_hash=file_hash_val, mtime=mtime,
                         captured=captured, coords=coords, pixels=pixels, faces=faces)

    def _analyze_many(self, pixels: list) -> list:
        """One forward pass for the batch; per-item fallback if that fails.
        Each result is an analysis dict or the Exception for that item."""
        if not pixels:
            return []
        batched = callable(getattr(self.model, "analyze_batch", None)) and \
            callable(getattr(self.model, "preprocess", None))
        if batched:
            step = self._infer_batch()
            try:
                out = []
                for i in range(0, len(pixels), step):
                    out.extend(self.model.analyze_batch(pixels[i:i + step]))
                return out
            except Exception as e:
                logger.error(f"[SyncManager] batch inference failed ({e}); retrying one by one")
        results = []
        for px in pixels:
            try:
                results.append(self.model.analyze_batch([px])[0] if batched
                               else self.model.analyze(px))
            except Exception as e:
                results.append(e)
        return results

    def _resolve_location(self, path, coords):
        loc = self.location_processor.location_from_coords(*coords) if coords else None
        if loc:
            logger.debug(f"DEBUG: Found location for {os.path.basename(path)}: {loc}")
        else:
            # Strategy 1: Path Inference
            loc = self.location_processor.infer_from_path(path)
            if loc:
                logger.debug(f"DEBUG: Inferred location from path for {os.path.basename(path)}: {loc}")
            else:
                logger.debug(f"DEBUG: NO location found for {os.path.basename(path)}")
        return loc

    def _build_record(self, prep: _Prepared, analysis: dict) -> dict:
        vec = analysis["embedding"]
        score = analysis["aesthetic_score"]
        base_tag = analysis["tag"]

        # Semantic tags, reusing the embedding computed above.
        auto_tags = self.tag_generator.generate_tags(None, image_features=vec)

        # Face rows — clear old faces first to avoid duplicates.
        self.store.delete_faces(prep.path)
        if prep.faces:
            self.store.add_faces(prep.path, prep.faces)
            # Heuristic: if we found faces it is very likely a photo, not a document.
            if base_tag == 'document':
                logger.debug(f"DEBUG: Overriding 'document' tag to 'photo' due to face detection for {os.path.basename(prep.path)}")
                base_tag = 'photo'

        # Backup heuristic: semantic tags that imply a photo (if face detection failed).
        if base_tag == 'document':
            found_non_doc = [t for t in auto_tags if t in self._NON_DOC_TAGS]
            if found_non_doc:
                logger.debug(f"DEBUG: Overriding 'document' tag to 'photo' due to semantic tags {found_non_doc} for {os.path.basename(prep.path)}")
                base_tag = 'photo'

        return {
            "vector": vec, "file_path": prep.path, "file_hash": prep.file_hash,
            "last_modified": prep.mtime, "captured_time": prep.captured,
            "aesthetic_score": score, "tag": base_tag,
            "location_info": self._resolve_location(prep.path, prep.coords),
            "auto_tags": auto_tags,
        }

    @staticmethod
    def _error_reason(exc: Exception) -> str:
        if isinstance(exc, UnidentifiedImageError):
            return "corrupt or unsupported image"
        if isinstance(exc, OSError):
            return f"truncated/unreadable: {exc}"
        return f"unexpected error: {exc}"

    def _fail(self, path, exc, fs_files):
        if isinstance(exc, UnidentifiedImageError):
            logger.warning(f"[Warning] Skipping corrupt or unsupported image: {os.path.basename(path)}")
        elif isinstance(exc, OSError):
            logger.warning(f"[Warning] Skipping truncated or unreadable file {os.path.basename(path)}: {exc}")
        else:
            logger.error(f"[Warning] Error indexing {os.path.basename(path)}: {exc}. Skipping file.")
        self._mark_file_as_error(path, _safe_mtime(path, fs_files), self._error_reason(exc))

    def _commit_batch(self, batch: list, fs_files: dict, report=None):
        """Main-thread half: inference, tagging, location names, DB writes.
        Items are committed and reported in their original order."""
        if not batch:
            return
        ok = [b for b in batch if isinstance(b, _Prepared)]
        analyses = dict(zip((id(p) for p in ok),
                            self._analyze_many([p.pixels for p in ok]), strict=True))

        records, done = [], []
        for item in batch:
            if isinstance(item, _Failed):
                self._fail(item.path, item.error, fs_files)
                done.append(item.path)
                continue
            result = analyses[id(item)]
            try:
                if isinstance(result, Exception):
                    raise result
                records.append(self._build_record(item, result))
            except Exception as e:
                self._fail(item.path, e, fs_files)
            done.append(item.path)

        try:
            self.db.insert_many(records)
        except Exception as e:
            logger.error(f"[SyncManager] batch write failed ({e}); writing one by one")
            for r in records:
                try:
                    self.db.insert_many([r])
                except Exception as e2:
                    self._fail(r["file_path"], e2, fs_files)

        if report:
            for path in done:
                report(path, False)

    def _index_image(self, path, img_original, fs_files):
        """Index one still image synchronously (same steps as the pipeline)."""
        self._commit_batch([self._prepare_loaded(path, img_original, fs_files)], fs_files)

    def _index_video(self, path, fs_files, stop_check=None) -> bool:
        """Index one video's scenes. Returns False if a stop was requested."""
        logger.info(f"[SyncManager] Processing video: {os.path.basename(path)}")

        # 1. Clear existing segments (essential for re-indexing)
        self.db.delete_by_path(path)
        self.store.delete_faces(path) # Although videos don't have faces yet, good practice

        # 2. Extract Scenes
        frames_with_time = self.video_processor.process_video(path)
        try:
            file_hash_val = compute_file_hash(path)
        except Exception:
            file_hash_val = ""

        file_mtime = _safe_mtime(path, fs_files)

        if not frames_with_time:
            logger.error(f"[SyncManager] No frames extracted from {path}. Marking as error.")
            self._mark_file_as_error(path, file_mtime, "failed to extract frames (likely codec issue)")
            return True

        if stop_check and stop_check():
            return False

        # 3. All scenes in one forward pass; the tagger reuses each embedding.
        analyses = self._analyze_many([self._model_input(img) for img, _t in frames_with_time])
        captured = int(os.path.getmtime(path))
        records = []
        for idx, analysis in enumerate(analyses):
            if isinstance(analysis, Exception):
                raise analysis
            vec = analysis["embedding"]
            records.append({
                "vector": vec, "file_path": path, "file_hash": file_hash_val,
                "last_modified": file_mtime, "captured_time": captured,
                "aesthetic_score": analysis["aesthetic_score"], "tag": "video",
                "location_info": None,
                "auto_tags": self.tag_generator.generate_tags(None, image_features=vec),
                "custom_id": f"{path}#{idx}",
            })
        self.db.insert_many(records)

        try:
            thumbnail_service.get_thumbnail(path)
        except Exception as e:
            logger.error(f"[SyncManager] Warning: pre-generate thumbnail failed for {path}: {e}")

        logger.info(f"[SyncManager] Indexed {len(frames_with_time)} scenes for {os.path.basename(path)}")
        return True

    def sync_changes(self, diff, progress_callback=None, stop_check=None):
        """
        Executes the sync based on diff.
        progress_callback(current, total, message)
        stop_check(): returns True if should stop
        """
        to_add = diff['to_add']
        to_update = diff['to_update']
        to_delete = diff['to_delete']
        fs_files = diff.get('fs_files', {})

        total_ops = len(to_add) + len(to_update) + len(to_delete)
        processed = 0
        
        # Deletions
        for path in to_delete:
            if stop_check and stop_check():
                 logger.info("[SyncManager] Stop requested.")
                 return

            try:
                self.db.delete_by_path(path)
                self.store.delete_faces(path) # Clear faces from SQLite
            except Exception as e:
                logger.error(f"Error deleting {path}: {e}")
            
            processed += 1
            if progress_callback: progress_callback(processed, total_ops, f"Deleting {os.path.basename(path)}", is_video=False)

        # Additions & Updates
        def report(path, is_video):
            nonlocal processed
            processed += 1
            if progress_callback:
                progress_callback(processed, total_ops, f"Indexing {os.path.basename(path)}", is_video=is_video)

        if not self._run_pipeline(to_add + to_update, fs_files, report, stop_check):
            logger.info("[SyncManager] Stop requested.")
            return

        if processed > 0:
            import datetime
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.store.set_config("last_indexed_time", now_str)

    def _run_pipeline(self, paths, fs_files, report, stop_check=None) -> bool:
        """Index *paths* in order. Returns False if stopped early."""
        if not paths:
            return True
        batch_size, workers = self._pipeline_sizes()
        window = max(batch_size * 2, workers * 2)
        logger.info(f"[SyncManager] Indexing {len(paths)} files "
                    f"(batch={batch_size}, prep workers={workers})")

        pending = deque()
        source = iter(paths)
        pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="index-prep")

        def submit_next():
            path = next(source, None)
            if path is None:
                return False
            if path.lower().endswith(VIDEO_EXTENSIONS):
                pending.append((path, None))  # videos run on the main thread
            else:
                pending.append((path, pool.submit(self._prepare_image, path, fs_files)))
            return True

        batch = []
        try:
            while len(pending) < window and submit_next():
                pass
            while pending:
                if stop_check and stop_check():
                    # Work already inferred-for is cheap to keep; finish it.
                    self._commit_batch(batch, fs_files, report)
                    return False
                path, fut = pending.popleft()
                submit_next()

                if fut is None:
                    self._commit_batch(batch, fs_files, report)
                    batch = []
                    try:
                        if not self._index_video(path, fs_files, stop_check):
                            return False
                    except Exception as e:
                        self._fail(path, e, fs_files)
                    report(path, True)
                    continue

                try:
                    batch.append(fut.result())
                except Exception as e:
                    batch.append(_Failed(path, e))
                if len(batch) >= batch_size:
                    self._commit_batch(batch, fs_files, report)
                    batch = []

            self._commit_batch(batch, fs_files, report)
            return True
        finally:
            for _p, fut in pending:
                if fut is not None:
                    fut.cancel()
            pool.shutdown(wait=True)

    def run_startup_sync(self, dry_run: bool = False, force: bool = False):
        # Legacy/Simple wrapper
        if force and not dry_run:
            self.db.reset_collection()
            
        diff = self.scan_files()
        
        if dry_run:
             return {
                "added": len(diff['to_add']),
                "updated": len(diff['to_update']),
                "deleted": len(diff['to_delete'])
            }
            
        self.sync_changes(diff)
        
        # Post-Processing: Refine Locations (Sandwich/VLM/OCR)
        if not dry_run:
            self.refine_missing_locations()
            
        return {"status": "completed"}

    def refine_missing_locations(self):
        """
        Refine step:
        1. Sandwich Logic (Interpolation)
        2. VLM / OCR (Optional/Future)
        """
        logger.info("[SyncManager] Starting location refinement (Sandwich Logic)...")
        try:
            # 1. Fetch all files to build timeline
            # We need standard dicts with captured_time, file_path, location_info
            all_files = self.db.get_all_files_with_time()
            if not all_files: return
            
            # Sort by time
            # Ensure float type for sort
            def get_ts(f):
                ct = f.get('captured_time', 0)
                if hasattr(ct, 'item'): ct = ct.item()
                return float(ct)

            all_files.sort(key=get_ts)
            
            updates = [] # List of (path, location_info)
            
            # 2. Iterate
            for i in range(len(all_files)):
                curr = all_files[i]
                curr_loc = curr.get('location_info')
                
                # Check if location is missing or empty
                # Some implementations might store {'latitude': None}
                has_loc = False
                if curr_loc and isinstance(curr_loc, dict):
                    if curr_loc.get('latitude') is not None and curr_loc.get('longitude') is not None:
                        has_loc = True
                
                if has_loc: continue
                
                # Missing Location -> Try Sandwich
                # Find Prev Valid
                prev_valid = None
                for j in range(i-1, -1, -1):
                    p = all_files[j]
                    ploc = p.get('location_info')
                    if ploc and ploc.get('latitude') is not None:
                        prev_valid = p
                        break
                
                # Find Next Valid
                next_valid = None
                for j in range(i+1, len(all_files)):
                    n = all_files[j]
                    nloc = n.get('location_info')
                    if nloc and nloc.get('latitude') is not None:
                        next_valid = n
                        break
                
                # Interpolate
                if prev_valid and next_valid:
                    t1 = get_ts(prev_valid)
                    t2 = get_ts(next_valid)
                    target_t = get_ts(curr)
                    
                    # Threshold: e.g. 30 mins (1800s)
                    # User said "10:00 and 10:10", so gap is small.
                    if (t2 - t1) < 3600: # 1 hour max gap
                        loc1 = (prev_valid['location_info']['latitude'], prev_valid['location_info']['longitude'])
                        loc2 = (next_valid['location_info']['latitude'], next_valid['location_info']['longitude'])
                        
                        new_LatLon = self.location_processor.interpolate(t1, loc1, t2, loc2, target_t)
                        if new_LatLon:
                            logger.info(f"[Refine] Interpolated location for {os.path.basename(curr['file_path'])}")
                            
                            # Construct new location object
                            # We might accept city from prev or next?
                            # Let's take 'city' from nearest neighbor roughly
                            nearest = prev_valid if (target_t - t1) < (t2 - target_t) else next_valid
                            base_info = nearest.get('location_info', {})
                            
                            new_info = {
                                "latitude": new_LatLon[0],
                                "longitude": new_LatLon[1],
                                "city": base_info.get('city', ""),
                                "province": base_info.get('province', ""),
                                "country_code": base_info.get('country_code', ""),
                                "source": "interpolated"
                            }
                            updates.append((curr['file_path'], new_info))
                            continue

                # Strategy 3 & 4: VLM / OCR (Placeholder)
                # This could be slow, so maybe limit count or run in background worker
                pass

            # 3. Apply Updates
            if updates:
                logger.info(f"[Refine] Updating {len(updates)} files with interpolated locations...")
                for path, info in updates:
                    self.db.update_location(path, info)
                    
        except Exception as e:
            logger.error(f"[Refine] Error: {e}")
