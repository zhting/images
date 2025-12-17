import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from src.database.vector_db import VectorDB

def check_file_db():
    try:
        db = VectorDB()
        files = db.get_all_files_with_time()
        
        target = "IMG_6625.JPG"
        found = False
        for f in files:
            if f['file_path'].endswith(target):
                print(f"File found: {f['file_path']}")
                print(f"Lat: {f.get('latitude')}")
                print(f"Lon: {f.get('longitude')}")
                print(f"City: {f.get('city')}")
                print(f"All keys: {list(f.keys())}")
                found = True
                break
        
        if not found:
            print("File NOT found in DB.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_file_db()
