import os
import time
from database.vector_db import VectorDB
from core.models import VisionModel
from database.sqlite_store import SQLiteStore
from core.location_processor import LocationProcessor
from core.tag_generator import TagGenerator
from core.face_processor import FaceProcessor
from PIL import Image, ExifTags
import datetime
import json
import numpy as np

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
        
        # Ensure faces table exists
        self.store.create_faces_table()

    def scan_files(self):
        """
        Scans filesystem and DB to calculate diffs.
        Returns dict with 'to_add', 'to_update', 'to_delete' lists.
        """
        print("[SyncManager] Starting file scan...")
        asset_paths = self.store.get_asset_paths()
        if not asset_paths:
            return {"to_add": [], "to_update": [], "to_delete": []}

        # 1. Get DB State
        db_files = self.db.get_all_files()
        
        # 2. Get FS State
        fs_files = {} # {path: last_modified}
        
        for p in asset_paths:
            if not os.path.exists(p):
                continue
                
            for root, _, files in os.walk(p):
                for f in files:
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        full_path = os.path.abspath(os.path.join(root, f))
                        try:
                            mtime = int(os.path.getmtime(full_path))
                            fs_files[full_path] = mtime
                        except Exception:
                            pass

        # 3. Calculate Diff
        to_add = []
        to_update = []
        to_delete = []

        for path, mtime in fs_files.items():
            if path not in db_files:
                to_add.append(path)
            elif mtime > db_files[path]:
                to_update.append(path)
        
        for path in db_files:
            belongs = False
            for asset_root in asset_paths:
                if path.startswith(os.path.abspath(asset_root)):
                    belongs = True
                    break
            
            if belongs and path not in fs_files:
                to_delete.append(path)
        
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
            except Exception as e:
                print(f"Error deleting {path}: {e}")
            
            processed += 1
            if progress_callback: progress_callback(processed, total_ops, f"Deleting {os.path.basename(path)}")

        # Additions & Updates
        for i, path in enumerate(to_add + to_update):
            if stop_check and stop_check():
                 print("[SyncManager] Stop requested.")
                 return

            try:
                # Open original for location (exif)
                img_original = Image.open(path)
                
                # 1. Location (Must use original to preserve EXIF)
                loc = self.location_processor.get_location_info(img_original)
                if loc:
                    print(f"DEBUG: Found location for {os.path.basename(path)}: {loc}")
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
                faces = self.face_processor.detect_faces(img)
                # Store faces in SQLite
                if faces:
                    for face in faces:
                        self.store.add_face(path, face['embedding'], face['bbox'])
                
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
            except Exception as e:
                print(f"Error indexing {path}: {e}")
            
            processed += 1
            if progress_callback: progress_callback(processed, total_ops, f"Indexing {os.path.basename(path)}")
            
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
        return {"status": "completed"}
