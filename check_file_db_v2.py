import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from src.database.vector_db import VectorDB

def check():
    try:
        db = VectorDB()
        files = db.get_all_files_with_time()
        
        target = "IMG_6625.JPG"
        for f in files:
            if f['file_path'].endswith(target):
                lat = f.get('latitude')
                lon = f.get('longitude')
                
                print(f"TARGET_FILE: {target}")
                print(f"FULL_PATH: {f['file_path']}")
                
                if lat is not None:
                    print(f"STATUS: LAT_FOUND {lat}")
                else:
                    print("STATUS: LAT_MISSING")
                    
                if lon is not None:
                    print(f"STATUS: LON_FOUND {lon}")
                else:
                    print("STATUS: LON_MISSING")
                    
                # helper
                print(f"RAW_KEYS: {list(f.keys())}")
                return

        print("STATUS: FILE_NOT_IN_DB")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check()
