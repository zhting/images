import sys
import os
from PIL import Image, ExifTags

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from src.database.vector_db import VectorDB
from src.core.location_processor import LocationProcessor

def analyze():
    print("Fetching file...")
    try:
        db = VectorDB()
        files = db.get_all_files_with_time()
        
        target_file = None
        for f in files:
            if os.path.exists(f['file_path']):
                target_file = f['file_path']
                break
        
        if not target_file:
            print("No existing files found in DB.")
            return

        print(f"Analyzing: {target_file}")
        
        img = Image.open(target_file)
        exif = img._getexif()
        
        if not exif:
            print("No EXIF data.")
            return
            
        # Find GPSInfo key
        gps_key = None
        for k, v in ExifTags.TAGS.items():
            if v == 'GPSInfo':
                gps_key = k
                break
        
        print(f"GPSInfo Key ID: {gps_key}")
        
        if gps_key not in exif:
            print("No GPSInfo tag in EXIF.")
            return
            
        gps_info = exif[gps_key]
        print(f"Raw GPSInfo: {gps_info}")
        
        # Check specific keys
        # 1: LatitudeRef, 2: Latitude, 3: LongitudeRef, 4: Longitude
        print(f"Has Lat (2): {2 in gps_info}")
        print(f"Has Lon (4): {4 in gps_info}")
        if 2 in gps_info: print(f"Lat val: {gps_info[2]} Type: {type(gps_info[2])}")
        
        # Test Processor
        lp = LocationProcessor()
        lat, lon = lp.get_lat_lon(img)
        print(f"Processor Result: {lat}, {lon}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze()
