import os
import hashlib
from typing import List, Dict, Any
from database.vector_db import VectorDB
from core.models import VisionModel
from database.sqlite_store import SQLiteStore
from core.location_processor import LocationProcessor
from core.tag_generator import TagGenerator
from core.face_processor import FaceProcessor
from core.video_processor import VideoProcessor
from PIL import Image, ExifTags, UnidentifiedImageError
import datetime
import json
import numpy as np
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

def get_image_timestamp(file_path: str) -> int:
    """
    Extracts the earliest timestamp from EXIF data or falls back to file modification time.
    Returns unix timestamp (int).
    """
    try:
        img = Image.open(file_path)
        exif = img.getexif()
        if exif:
            # 36867 = DateTimeOriginal, 306 = DateTime
            # Iterate to find date
            date_str = exif.get(36867) or exif.get(306)
            if date_str:
                # Format: YYYY:MM:DD HH:MM:SS
                dt = datetime.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                return int(dt.timestamp())
    except Exception:
        pass
        
    # Fallback to mtime
    return int(os.path.getmtime(file_path))

class SyncManager:
    def __init__(self, db: VectorDB, model: VisionModel, store: SQLiteStore):
        self.db = db
        self.model = model
        self.store = store
        
        # Initialize Smart Processors
        self.location_processor = LocationProcessor()
        self.tag_generator = TagGenerator(model)
        self.face_processor = FaceProcessor() # CPU by default
        self.video_processor = VideoProcessor()
        
        # Ensure faces table exists
        self.store.create_faces_table()

    # Supported file extensions
    SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.heic', '.heif', '.mp4', '.mov', '.avi', '.mkv')

    def _mark_file_as_error(self, path: str, file_mtime: int, error_msg: str):
        """
        Inserts a dummy record for unreadable/corrupt files with 'error' tag.
        This prevents the scanner from retrying them infinitely.
        """
        import numpy as np
        # Create a zero vector of the same dimension as the model output
        # E.g. 512 for SigLIP base. We can query the model if we wanted, or just assume 512.
        # Alternatively, model.encode(dummy_image)
        try:
            # Generate a 512-dim zero vector (adjust based on your actual model dim if different)
            # Clip/SigLIP usually uses 512, 768, or larger. Let's use 512. If db expects something else,
            # this might throw. Safest way is to just generate a small black image and encode it.
            dummy_img = Image.new('RGB', (10, 10), color='black')
            vec = self.model.encode(dummy_img)
            
            self.db.insert(
                vec, path, "hash", file_mtime,
                captured_time=int(os.path.getmtime(path)),
                aesthetic_score=0.0,
                tag="error",
                location_info=None,
                auto_tags=["error: " + str(error_msg)]
            )
            print(f"[SyncManager] Marked {os.path.basename(path)} as error to avoid retry loop.")
        except Exception as e:
            print(f"[SyncManager] Failed to mark error placeholder for {path}: {e}")

        # Write to error log for manual review/deletion by the user
        try:
            import datetime
            log_path = os.path.join(os.getcwd(), "error_media.log")
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] REASON: {error_msg} | FILE: {path}\n")
        except Exception as log_e:
            print(f"[SyncManager] Failed to write to error log: {log_e}")

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
        print("[SyncManager] Starting optimized file scan...")
        
        asset_paths = self.store.get_asset_paths()
        if not asset_paths:
            return {"to_add": [], "to_update": [], "to_delete": []}

        # 1. Get DB State
        # P1a stage 3: read indexed state from SQLite (kept in lockstep by
        # the dual-write mirror); fall back to paging Chroma pre-migration.
        if self.store.count_photos() > 0:
            db_files = self.store.get_photo_sync_states()
        else:
            db_files = self.db.get_all_files()
        
        # 2. Load directory mtime cache (for future optimization)
        dir_cache = self.store.get_config("dir_mtime_cache", {})
        if isinstance(dir_cache, str):
            try:
                dir_cache = json.loads(dir_cache)
            except:
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
                    print(f"[SyncManager] Scan error: {e}")

        scan_time = time.time() - start_time
        print(f"[SyncManager] Scanned {len(fs_files)} files in {scan_time:.2f}s")

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
        
        for norm_p, (db_path, db_mtime) in norm_db_files.items():
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
                 print("[SyncManager] Stop requested.")
                 return

            try:
                self.db.delete_by_path(path)
                self.store.delete_faces(path) # Clear faces from SQLite
            except Exception as e:
                print(f"Error deleting {path}: {e}")
            
            processed += 1
            if progress_callback: progress_callback(processed, total_ops, f"Deleting {os.path.basename(path)}", is_video=False)

        # Additions & Updates
        for i, path in enumerate(to_add + to_update):
            if stop_check and stop_check():
                 print("[SyncManager] Stop requested.")
                 return

            try:
                # Determine file type
                is_video = path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))
                
                # --- Video Processing ---
                if is_video:
                    print(f"[SyncManager] Processing video: {os.path.basename(path)}")
                    
                    # 1. Clear existing segments (essential for re-indexing)
                    self.db.delete_by_path(path)
                    self.store.delete_faces(path) # Although videos don't have faces yet, good practice
                    
                    # 2. Extract Scenes
                    frames_with_time = self.video_processor.process_video(path)
                    
                    file_mtime = fs_files.get(path, int(os.path.getmtime(path)))
                    
                    if not frames_with_time:
                        print(f"[SyncManager] No frames extracted from {path}. Marking as error.")
                        self._mark_file_as_error(path, file_mtime, "failed to extract frames (likely codec issue)")
                        # Fall through to increment processed counter and report progress
                    else:
                        # 3. Index each scene
                        for idx, (img, mid_time) in enumerate(frames_with_time):
                         if stop_check and stop_check(): return
                         
                         # Metadata
                         # For now, videos don't have EXIF location like photos usually do easily sans parsing tracks.
                         # Skip location for video segments for now or implement VideoLocationProcessor later.
                         loc = None
                         
                         vec = self.model.encode(img)
                         score = self.model.predict_aesthetic_score(img)
                         base_tag = "video" # Explicit tag
                         auto_tags = self.tag_generator.generate_tags(img)
                         
                         # Custom ID
                         doc_id = f"{path}#{idx}"
                         
                         # Captured time: Base file time + offset?
                         # Or just file mtime. Let's use file mtime for sort, but maybe store offset?
                         # captured_time in DB is int timestamp.
                         # Let's use file creation time.
                         captured = int(os.path.getmtime(path)) 
                         
                         self.db.insert(
                            vec, path, "hash", file_mtime,
                            captured_time=captured,
                            aesthetic_score=score,
                            tag=base_tag,
                            location_info=loc,
                            auto_tags=auto_tags,
                            custom_id=doc_id
                         )
                         
                         try:
                             from core.thumbnails import thumbnail_service
                             thumbnail_service.get_thumbnail(path)
                         except Exception as e:
                             print(f"[SyncManager] Warning: pre-generate thumbnail failed for {path}: {e}")
                         
                        print(f"[SyncManager] Indexed {len(frames_with_time)} scenes for {os.path.basename(path)}")

                # --- Image Processing ---
                else:
                    # Open original for location (exif)
                    img_original = Image.open(path)
                    
                    # 1. Location (Must use original to preserve EXIF)
                    loc = self.location_processor.get_location_info(img_original)
                    if loc:
                        print(f"DEBUG: Found location for {os.path.basename(path)}: {loc}")
                    else:
                        # Strategy 1: Path Inference
                        loc = self.location_processor.infer_from_path(path)
                        if loc:
                            print(f"DEBUG: Inferred location from path for {os.path.basename(path)}: {loc}")
                        else:
                            print(f"DEBUG: NO location found for {os.path.basename(path)}")

                    # Convert for model (strip exif is ok for model)
                    img = img_original.convert('RGB')
                    vec = self.model.encode(img)
                    
                    # Smart Organization: Score and Classify
                    score = self.model.predict_aesthetic_score(img)
                    base_tag = self.model.classify_type(img) # photo/screenshot
                    
                    # ... Location is already extracted ...
                    
                    # 2. Semantic Tags
                    auto_tags = self.tag_generator.generate_tags(img)
                    
                    # 3. Face Detection
                    # Clear old faces first to avoid duplicates
                    self.store.delete_faces(path)
                    
                    faces = self.face_processor.detect_faces(img)
                    # Store faces in SQLite
                    if faces:
                        for face in faces:
                            self.store.add_face(path, face['embedding'], face['bbox'])
                        
                        # Heuristic: If we found faces, it's very likely a Photo, not a Document.
                        # Override classification if it was dubbed 'document'
                        if base_tag == 'document':
                             print(f"DEBUG: Overriding 'document' tag to 'photo' due to face detection for {os.path.basename(path)}")
                             base_tag = 'photo'
                    
                    # Backup Heuristic: Check tags for non-document objects (if face detection failed)
                    if base_tag == 'document':
                         # List of tags that strongly imply a photo, not a document
                         non_doc_tags = {
                             'scissors', 'toy', 'food', 'fruit', 'vegetable', 'cat', 'dog', 'animal', 
                             'child', 'boy', 'girl', 'person', 'woman', 'man', 'baby', 'face', 'human body', 'hand',
                             'car', 'vehicle', 'tree', 'flower', 'sky', 'cloud', 'nature', 'party', 'wedding', 'eating'
                         }
                         found_non_doc = [t for t in auto_tags if t in non_doc_tags]
                         if found_non_doc:
                              print(f"DEBUG: Overriding 'document' tag to 'photo' due to semantic tags {found_non_doc} for {os.path.basename(path)}")
                              base_tag = 'photo'

                    mtime = fs_files.get(path, int(os.path.getmtime(path)))
                    captured = get_image_timestamp(path)
                    
                    self.db.insert(
                        vec, path, "hash", mtime, 
                        captured_time=captured, 
                        aesthetic_score=score, 
                        tag=base_tag,
                        location_info=loc,
                        auto_tags=auto_tags
                    )
                    
                    try:
                        from core.thumbnails import thumbnail_service
                        thumbnail_service.get_thumbnail(path)
                    except Exception as e:
                        print(f"[SyncManager] Warning: pre-generate thumbnail failed for {path}: {e}")
            except UnidentifiedImageError:
                print(f"[Warning] Skipping corrupt or unsupported image: {os.path.basename(path)}")
                self._mark_file_as_error(path, fs_files.get(path, int(os.path.getmtime(path))), "corrupt or unsupported image")
            except OSError as e:
                print(f"[Warning] Skipping truncated or unreadable file {os.path.basename(path)}: {e}")
                self._mark_file_as_error(path, fs_files.get(path, int(os.path.getmtime(path))), f"truncated/unreadable: {e}")
            except Exception as e:
                print(f"[Warning] Error indexing {os.path.basename(path)}: {e}. Skipping file.")
                self._mark_file_as_error(path, fs_files.get(path, int(os.path.getmtime(path))), f"unexpected error: {e}")
            
            processed += 1
            if progress_callback: progress_callback(processed, total_ops, f"Indexing {os.path.basename(path)}", is_video=is_video)
            
        if processed > 0:
            import datetime
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.store.set_config("last_indexed_time", now_str)

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
        print("[SyncManager] Starting location refinement (Sandwich Logic)...")
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
                            print(f"[Refine] Interpolated location for {os.path.basename(curr['file_path'])}")
                            
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
                print(f"[Refine] Updating {len(updates)} files with interpolated locations...")
                for path, info in updates:
                    self.db.update_location(path, info)
                    
        except Exception as e:
            print(f"[Refine] Error: {e}")
