import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from src.database.vector_db import VectorDB

def find_file():
    try:
        db = VectorDB()
        files = db.get_all_files_with_time()
        print(f"Total files: {len(files)}")
        
        found = None
        for f in files:
            if f['file_path'].endswith("IMG_6625.JPG") or f['file_path'].endswith("IMG_6625.jpg"):
                found = f
                break
                
        if found:
            print(f"Found in DB: {found['file_path']}")
            print(f"Metadata: {found}")
        else:
            print("IMG_6625.JPG not found in DB.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_file()
