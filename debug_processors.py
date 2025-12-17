from PIL import Image
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from src.core.location_processor import LocationProcessor

def test_loc():
    img_path = "proxy_debug.jpg"
    if not os.path.exists(img_path):
        print("proxy_debug.jpg not found, trying to find any jpg in assets")
        # try find one
        for root, dirs, files in os.walk("."):
            for f in files:
                if f.lower().endswith(".jpg") or f.lower().endswith(".jpeg"):
                    img_path = os.path.join(root, f)
                    break
            if img_path != "proxy_debug.jpg": break
    
    print(f"Testing on: {img_path}")
    try:
        img = Image.open(img_path)
        lp = LocationProcessor()
        
        # Test 1: Raw EXIF GPS
        exif_gps = lp._get_gps_from_exif(img)
        print(f"Raw GPS Data found: {exif_gps is not None}")
        if exif_gps:
            print(f"Raw GPS Keys: {exif_gps.keys()}")
            
        # Test 2: Lat/Lon
        latlon = lp.get_lat_lon(img)
        print(f"Lat/Lon: {latlon}")
        
        # Test 3: Full Info
        info = lp.get_location_info(img)
        print(f"Location Info: {info}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_loc()
