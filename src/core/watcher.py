import time
import os
import sys

# Add src to path so we can import from database and core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from database.vector_db import VectorDB
from core.models import VisionModel
from PIL import Image

import logging
logger = logging.getLogger(__name__)

class ImageEventHandler(FileSystemEventHandler):
    def __init__(self, db: VectorDB, model: VisionModel):
        self.db = db
        self.model = model
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    
    def _is_image(self, path):
        return os.path.splitext(path)[1].lower() in self.image_extensions

    def _process_file(self, file_path):
        if not self._is_image(file_path):
            return
        
        logger.info(f"[Watcher] Processing file: {file_path}")
        try:
            # Add debounce logic if needed, but for now direct processing
            # Sleep briefly to ensure file write is complete
            time.sleep(0.5) 
            
            img = Image.open(file_path).convert('RGB')
            vector = self.model.encode(img)
            
            # Use mtime as heuristic for unique version or just store
            last_modified = int(os.path.getmtime(file_path))
            file_hash = f"{last_modified}" # Simplified hash
            
            self.db.insert(vector, file_path, file_hash, last_modified)
            logger.info(f"[Watcher] Indexed: {file_path}")
        except Exception as e:
            logger.error(f"[Watcher] Error processing {file_path}: {e}")

    def on_created(self, event):
        if not event.is_directory:
            self._process_file(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._process_file(event.src_path)
            
    def on_moved(self, event):
        if not event.is_directory:
            # Handle delete old, add new
            if self._is_image(event.src_path):
                logger.info(f"[Watcher] Removed (Moved from): {event.src_path}")
                self.db.delete_by_path(event.src_path)
            
            if self._is_image(event.dest_path):
                self._process_file(event.dest_path)

    def on_deleted(self, event):
        if not event.is_directory:
            if self._is_image(event.src_path):
                logger.info(f"[Watcher] Deleted: {event.src_path}")
                self.db.delete_by_path(event.src_path)

class FileWatcher:
    def __init__(self, watch_dir, db_path="./search.db"):
        self.watch_dir = watch_dir
        self.params = db_path # Hack to pass path if needed, but VectorDB takes it
        self.db = VectorDB(db_path=db_path)
        self.model = VisionModel()
        self.observer = Observer()
        self.handler = ImageEventHandler(self.db, self.model)

    def start(self):
        logger.info(f"[Watcher] Starting monitor on: {self.watch_dir}")
        self.observer.schedule(self.handler, self.watch_dir, recursive=True)
        self.observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()

if __name__ == "__main__":
    # Test watcher
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "./assets"
    watcher = FileWatcher(path)
    watcher.start()
