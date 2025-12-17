
import sys
import os
import sqlite3
from PIL import Image, ExifTags

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "src"))

from src.core.location_processor import LocationProcessor
from src.database.sqlite_store import SQLiteStore

def find_file(filename):
    # Try history.db
    db_path = "history.db"
    if not os.path.exists(db_path):
        db_path = os.path.join(current_dir, "history.db")
        
    if not os.path.exists(db_path):
         # Try parent
         db_path = os.path.join(os.path.dirname(current_dir), "history.db")

    print(f"Using Config DB: {db_path}")
    if os.path.exists(db_path):
        store = SQLiteStore(db_path)
        paths = store.get_asset_paths()
        print(f"Asset Paths: {paths}")
        
        for p in paths:
            if not os.path.exists(p): continue
            for root, _, files in os.walk(p):
                if filename in files:
                    return os.path.join(root, filename), paths
    else:
        print("DB not found")
        return None, []
        
    return None, paths

def diagnose():
    target_name = "IMG_6625.JPG"
    print(f"Searching for {target_name}...")
    
    file_path, paths = find_file(target_name)
    
    if not file_path:
        # Try explicit path from user screenshot
        potential_path = r"E:\本地照片\赵挺的手机照片\位置测试\IMG_6625.JPG"
        if os.path.exists(potential_path):
            file_path = potential_path
            print(f"Found at absolute path: {file_path}")
        else:
             print(f"File {target_name} not found in asset paths: {paths}")
             print(f"Absolute path checked: {potential_path}")
             return

    print(f"Diagnosing: {file_path}")
    
    try:
        img = Image.open(file_path)
        exif = img._getexif()
        if not exif:
            print("No EXIF data found.")
            return

        # Dump GPS
        print("\n--- Raw GPS Data ---")
        gps_tag_id = None
        for k, v in ExifTags.TAGS.items():
            if v == 'GPSInfo':
                gps_tag_id = k
                break
        
        if gps_tag_id and gps_tag_id in exif:
            gps_data = exif[gps_tag_id]
            print(f"GPSInfo Tag Found: {gps_data}")
            # print items details
            for k, v in gps_data.items():
                decoded = ExifTags.GPSTAGS.get(k, k)
                print(f"  {decoded} ({k}): {v} (Type: {type(v)})")
        else:
            print("No GPSInfo tag in EXIF.")

        print("\n--- LocationProcessor Result ---")
        lp = LocationProcessor()
        lat_lon = lp.get_lat_lon(img)
        print(f"get_lat_lon: {lat_lon}")
        
        if lat_lon:
            info = lp.get_location_info(img)
            print(f"get_location_info: {info}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose()
