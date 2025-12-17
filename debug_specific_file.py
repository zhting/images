
import os
import sys
from datetime import datetime

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
if src_dir not in sys.path:
    sys.path.append(src_dir)

from database.vector_db import VectorDB

def check_file():
    db_path = os.path.join(current_dir, "search.db")
    db = VectorDB(db_path)
    files = db.get_all_files_with_time()
    
    target_name = "IMG_20211217_105423.JPG"
    found = None
    
    for f in files:
        if target_name in f['file_path']:
            found = f
            break
            
    if found:
        print(f"Found File: {found['file_path']}")
        print(f"Timestamp: {found.get('captured_time')}")
        print(f"Last Modified (DB): {found.get('last_modified')}")
        if found.get('captured_time'):
            print(f"Date: {datetime.fromtimestamp(found.get('captured_time'))}")
    else:
        print(f"File {target_name} NOT FOUND in database.")

if __name__ == "__main__":
    check_file()
