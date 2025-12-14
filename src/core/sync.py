import os
import time
from database.vector_db import VectorDB
from core.models import VisionModel
from database.sqlite_store import SQLiteStore
from PIL import Image

class SyncManager:
    def __init__(self, db: VectorDB, model: VisionModel, store: SQLiteStore):
        self.db = db
        self.model = model
        self.store = store

    def run_startup_sync(self, dry_run: bool = False):
        """
        Synchronizes the filesystem state with the vector database.
        Detects new, modified, and deleted files in configured directories.
        If dry_run is True, only returns the diff stats without modifying the DB.
        """
        print("[SyncManager] Starting startup synchronization...")
        
        asset_paths = self.store.get_asset_paths()
        if not asset_paths:
            print("[SyncManager] No asset paths configured. Skipping.")
            return

        # 1. Get DB State
        # {path: last_modified}
        db_files = self.db.get_all_files()
        
        # 2. Get FS State
        fs_files = {} # {path: last_modified}
        
        for p in asset_paths:
            if not os.path.exists(p):
                print(f"[SyncManager] Warning: Path not found {p}")
                continue
                
            for root, _, files in os.walk(p):
                for f in files:
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        full_path = os.path.abspath(os.path.join(root, f))
                        try:
                            mtime = int(os.path.getmtime(full_path))
                            fs_files[full_path] = mtime
                        except Exception as e:
                            print(f"[SyncManager] Error reading file {full_path}: {e}")

        # 3. Calculate Diff
        to_add = []
        to_update = []
        to_delete = []

        # Check FS against DB
        for path, mtime in fs_files.items():
            if path not in db_files:
                to_add.append(path)
            elif mtime > db_files[path]:
                to_update.append(path)
        
        # Check DB against FS (only for files that belong to configured paths)
        # We assume if a file is in DB but not in FS_FILES, AND it starts with one of the asset_paths, strictly it is deleted.
        for path in db_files:
            # Check if path belongs to any configured asset root
            belongs = False
            for asset_root in asset_paths:
                if path.startswith(os.path.abspath(asset_root)):
                    belongs = True
                    break
            
            if belongs and path not in fs_files:
                to_delete.append(path)

        print(f"[SyncManager] Diff calculated: {len(to_add)} new, {len(to_update)} modified, {len(to_delete)} deleted.")

        if dry_run:
             return {
                "added": len(to_add),
                "updated": len(to_update),
                "deleted": len(to_delete)
            }

        # 4. Execute Updates
        changes_made = False
        
        # Deletions
        for path in to_delete:
            try:
                self.db.delete_by_path(path)
                changes_made = True
            except Exception as e:
                print(f"[SyncManager] Error deleting {path}: {e}")

        # Additions & Updates
        for path in to_add + to_update:
            try:
                img = Image.open(path).convert('RGB')
                vec = self.model.encode(img)
                mtime = fs_files[path]
                self.db.insert(vec, path, "hash", mtime)
                changes_made = True
            except Exception as e:
                 print(f"[SyncManager] Error indexing {path}: {e}")

        if changes_made:
            import datetime
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.store.set_config("last_indexed_time", now_str)
            print("[SyncManager] Sync complete. Index updated.")
        else:
            print("[SyncManager] No changes detected.")
            
        return {
            "added": len(to_add),
            "updated": len(to_update),
            "deleted": len(to_delete)
        }
