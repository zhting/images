import sys
import os
from PIL import Image, ExifTags

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from src.database.vector_db import VectorDB

def scan_all():
    print("Scanning for GPS...")
    try:
        db = VectorDB()
        files = db.get_all_files_with_time()
        
        gps_found = 0
        scanned = 0
        tags_set = set()
        
        for f in files:
            path = f['file_path']
            tags = f.get('auto_tags', [])
            for t in tags: tags_set.add(t)
            
            if not os.path.exists(path): continue
            
            scanned += 1
            try:
                img = Image.open(path)
                exif = img._getexif()
                if exif and 34853 in exif: # GPSInfo
                    gps_found += 1
                    gps_info = exif[34853]
                    # Print first found
                    if gps_found == 1:
                        print(f"FOUND GPS in: {path}")
                        print(f"GPS Data: {gps_info}")
            except:
                pass
                
            if scanned >= 200: break
            
        print(f"Scanned {scanned} files.")
        print(f"Files with GPS Information: {gps_found}")
        print(f"Unique Tags in DB: {len(tags_set)}")
        print(f"Sample Tags: {list(tags_set)[:10]}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scan_all()
