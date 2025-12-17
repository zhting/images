
import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from src.database.vector_db import VectorDB

def check():
    try:
        db = VectorDB()
        print("Checking DB for IMG_6625.JPG...")
        # This might be slow if DB is huge, but locally it's fine.
        files = db.get_all_files_with_time()
        
        found = None
        for f in files:
            if "IMG_6625.JPG" in f['file_path']:
                found = f
                break
                
        if found:
            print(f"File FOUND in DB: {found['file_path']}")
            # Chroma might return metadata flattened or nested
            
            # Check for location keys directly or in 'location_info' string/dict?
            # VectorDB usually stores simple types. Nested dicts might be stringified or flattened?
            # let's print all
            if 'location_info' in found:
                print(f"Location Info (Raw): {type(found['location_info'])} - {found['location_info']}")
            
            # Check for flattened keys if any (city, country etc)
            keys = ['city', 'province', 'country_code', 'latitude', 'longitude']
            extracted = {k: found.get(k) for k in keys if k in found}
            print(f"Flattened Location Keys: {extracted}")
            
        else:
            print("File NOT FOUND in DB.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check()
