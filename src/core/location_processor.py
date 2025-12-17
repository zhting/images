import logging
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import reverse_geocoder as rg
import os

logger = logging.getLogger(__name__)

class LocationProcessor:
    def __init__(self):
        # translator instance
        from core.translator import translator
        self.translator = translator
        self._translation_cache = {}
        
        # Load Static Map
        self.place_map = {}
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            map_path = os.path.join(base_dir, "assets", "place_map.json")
            
            if os.path.exists(map_path):
                import json
                with open(map_path, 'r', encoding='utf-8') as f:
                    self.place_map = json.load(f)
                print(f"[LocationProcessor] Loaded {len(self.place_map)} manual translations.")
        except Exception as e:
            print(f"[LocationProcessor] Warning: Could not load place_map.json: {e}")

    def _get_gps_from_exif(self, image: Image.Image):
        """Extract GPS info from PIL Image."""
        try:
            exif = image._getexif()
            if not exif:
                return None
                
            gps_info = {}
            for tag, value in exif.items():
                decoded = TAGS.get(tag, tag)
                if decoded == "GPSInfo":
                    for t in value:
                        sub_decoded = GPSTAGS.get(t, t)
                        gps_info[sub_decoded] = value[t]
            
            return gps_info
        except Exception:
            return None

    def _to_float(self, val):
        """Convert distinct exif value (tuple or float) to float."""
        if isinstance(val, tuple) and len(val) == 2:
            # (numerator, denominator)
            if val[1] == 0: return 0.0
            return val[0] / val[1]
        try:
            return float(val)
        except:
            return 0.0

    def _convert_to_degrees(self, value):
        """Helper to convert DMS to decimal degrees."""
        # value is (deg, min, sec), each item might be (num, den) tuple or simple number
        d = self._to_float(value[0])
        m = self._to_float(value[1])
        s = self._to_float(value[2])
        return d + (m / 60.0) + (s / 3600.0)

    def get_lat_lon(self, image: Image.Image):
        """Return (lat, lon) tuple or None."""
        try:
            gps_info = self._get_gps_from_exif(image)
            if not gps_info:
                return None
            
            gps_lat = gps_info.get("GPSLatitude")
            gps_lat_ref = gps_info.get("GPSLatitudeRef", "N")
            gps_lon = gps_info.get("GPSLongitude")
            gps_lon_ref = gps_info.get("GPSLongitudeRef", "E")

            if gps_lat and gps_lon:
                lat = self._convert_to_degrees(gps_lat)
                if gps_lat_ref != "N":
                    lat = -lat

                lon = self._convert_to_degrees(gps_lon)
                if gps_lon_ref != "E":
                    lon = -lon

                return lat, lon
            return None
        except Exception as e:
            logger.debug(f"GPS extraction error: {e}")
            return None

    def _translate_cached(self, text: str) -> str:
        if not text:
            return ""
        if text in self.place_map:
            return self.place_map[text]
        if text in self._translation_cache:
            return self._translation_cache[text]
        
        # Use 7B Model for location
        try:
            res = self.translator.translate_location(text)
            self._translation_cache[text] = res
            return res
        except Exception as e:
            print(f"Translation failed for '{text}': {e}")
            return text 

    def get_location_info(self, image: Image.Image):
        """
        Returns a dict with location info: city, province (Translated)
        """
        coords = self.get_lat_lon(image)
        if not coords:
            return None
        
        lat, lon = coords
        
        try:
            # reverse_geocoder takes list of tuples
            results = rg.search((lat, lon))
            if results:
                res = results[0]
                city_en = res.get("name", "")
                province_en = res.get("admin1", "")
                country = res.get("cc", "")
                
                # Hybrid Translation (Map -> 7B)
                city_zh = self._translate_cached(city_en)
                province_zh = self._translate_cached(province_en)
                
                return {
                    "latitude": lat,
                    "longitude": lon,
                    "city": city_zh,
                    "province": province_zh,
                    "country_code": country
                }
        except Exception as e:
            logger.error(f"Reverse geocoding error: {e}")
            print(f"[LocationProcessor] Reverse geocoding error: {e}")
            
        return {
            "latitude": lat,
            "longitude": lon,
            "city": "",
            "province": "",
            "country_code": ""
        }
