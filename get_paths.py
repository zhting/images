import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from src.database.vector_db import VectorDB

try:
    db = VectorDB()
    files = db.get_all_files_with_time()
    if not files:
        print("No files in DB.")
    else:
        # Print first 5 paths
        for i, f in enumerate(files[:5]):
            print(f"File: {f['file_path']}")
except Exception as e:
    print(e)
