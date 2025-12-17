
import sys
import os
import time

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "src"))

from src.core.sync import SyncManager
from src.database.vector_db import VectorDB
from src.core.models import VisionModel
from src.database.sqlite_store import SQLiteStore

def reindex():
    print("Initializing SyncManager components...")
    # Use config DB path
    db_path = "history.db"
    if not os.path.exists(db_path): db_path = os.path.join(current_dir, "history.db")
    
    store = SQLiteStore(db_path)
    db = VectorDB() # vector db handles its own path (search.db)
    model = VisionModel() # loads on cpu/cuda
    
    manager = SyncManager(db, model, store)
    
    # Find the file
    target = None
    paths = store.get_asset_paths()
    print(f"Scanning paths: {paths}")
    for p in paths:
        if not os.path.exists(p): continue
        for root, _, files in os.walk(p):
            if "IMG_6625.JPG" in files:
                target = os.path.join(root, "IMG_6625.JPG")
                break
        if target: break
        
    if not target:
        print("Target file IMG_6625.JPG not found in configured paths.")
        # Try absolute fallback
        target = r"E:\本地照片\赵挺的手机照片\位置测试\IMG_6625.JPG"
        if not os.path.exists(target):
            print("Absolute path also not found.")
            return

    print(f"Re-indexing: {target}")
    
    # Force update
    diff = {
        "to_add": [],
        "to_update": [target],
        "to_delete": [],
        "fs_files": {target: int(time.time())} # Mock time
    }
    
    # Monkey patch store.add_face to simulate valid face storage if needed, 
    # but more importantly, let's verify what happens in sync.
    
    print("Starting sync...")
    manager.sync_changes(diff, progress_callback=lambda c, t, m: print(f"[{c}/{t}] {m}"))
    print("Re-index complete.")

if __name__ == "__main__":
    reindex()
