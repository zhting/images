import logging
import math
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import reverse_geocoder as rg

logger = logging.getLogger(__name__)

# Comprehensive standard city coordinates (synced with frontend chinaPopularCities)
STANDARD_CHINA_CITIES = {
    # 直辖市
    "北京": (39.9042, 116.4074, "北京"),
    "上海": (31.2304, 121.4737, "上海"),
    "天津": (39.0841, 117.2010, "天津"),
    "重庆": (29.5630, 106.5516, "重庆"),
    # 河北
    "承德": (40.9762, 117.9333, "河北"),
    "保定": (38.8741, 115.4646, "河北"),
    "秦皇岛": (39.9354, 119.5977, "河北"),
    "石家庄": (38.0423, 114.5089, "河北"),
    # 山西
    "大同": (40.0762, 113.2980, "山西"),
    "平遥": (37.1896, 112.1760, "山西"),
    "太原": (37.8706, 112.5489, "山西"),
    # 内蒙古
    "呼和浩特": (40.8414, 111.7521, "内蒙古"),
    "包头": (40.6571, 109.8403, "内蒙古"),
    "呼伦贝尔": (49.2117, 119.7653, "内蒙古"),
    # 辽宁
    "沈阳": (41.8057, 123.4315, "辽宁"),
    "大连": (38.9140, 121.6147, "辽宁"),
    # 吉林
    "长春": (43.8171, 125.3235, "吉林"),
    "吉林": (43.8380, 126.5496, "吉林"),
    # 黑龙江
    "哈尔滨": (45.8038, 126.5350, "黑龙江"),
    "漠河": (52.9722, 122.5290, "黑龙江"),
    # 江苏
    "南京": (32.0603, 118.7969, "江苏"),
    "苏州": (31.2990, 120.5853, "江苏"),
    "无锡": (31.4912, 120.3119, "江苏"),
    "镇江": (32.2036, 119.4551, "江苏"),
    # 浙江
    "杭州": (30.2741, 120.1551, "浙江"),
    "宁波": (29.8683, 121.5440, "浙江"),
    "乌镇": (30.7447, 120.4875, "浙江"),
    "温州": (27.9943, 120.6993, "浙江"),
    "嘉兴": (30.7459, 120.7555, "浙江"),
    # 安徽
    "黄山": (30.1330, 118.1627, "安徽"),
    "合肥": (31.8206, 117.2272, "安徽"),
    # 福建
    "厦门": (24.4798, 118.0894, "福建"),
    "福州": (26.0745, 119.2965, "福建"),
    # 江西
    "庐山": (29.5626, 115.9927, "江西"),
    "婺源": (29.2484, 117.8614, "江西"),
    "南昌": (28.6820, 115.8579, "江西"),
    # 山东
    "济南": (36.6512, 117.1201, "山东"),
    "青岛": (36.0671, 120.3826, "山东"),
    "泰山": (36.2561, 117.1009, "山东"),
    "烟台": (37.4638, 121.4479, "山东"),
    "威海": (37.5013, 122.1204, "山东"),
    # 河南
    "洛阳": (34.6202, 112.4539, "河南"),
    "开封": (34.7970, 114.3072, "河南"),
    "郑州": (34.7466, 113.6253, "河南"),
    # 湖北
    "武汉": (30.5928, 114.3055, "湖北"),
    "三峡": (30.8234, 111.0032, "湖北"),
    # 湖南
    "张家界": (29.1169, 110.4794, "湖南"),
    "凤凰古城": (27.9482, 109.5987, "湖南"),
    "长沙": (28.2282, 112.9388, "湖南"),
    # 广东
    "广州": (23.1291, 113.2644, "广东"),
    "深圳": (22.5431, 114.0579, "广东"),
    "珠海": (22.2707, 113.5767, "广东"),
    "佛山": (23.0215, 113.1214, "广东"),
    "东莞": (23.0205, 113.7518, "广东"),
    "中山": (22.5176, 113.3928, "广东"),
    "惠州": (23.1118, 114.4162, "广东"),
    "汕头": (23.3541, 116.6818, "广东"),
    "韶关": (24.8111, 113.5975, "广东"),
    "清远": (23.6811, 113.0560, "广东"),
    # 广西
    "南宁": (22.8170, 108.3661, "广西"),
    "桂林": (25.2736, 110.2907, "广西"),
    # 海南
    "三亚": (18.2528, 109.5119, "海南"),
    "海口": (20.0174, 110.3492, "海南"),
    # 四川
    "成都": (30.5728, 104.0668, "四川"),
    "九寨沟": (33.2600, 103.9200, "四川"),
    "稻城亚丁": (28.4100, 100.3000, "四川"),
    # 贵州
    "贵阳": (26.5783, 106.7139, "贵州"),
    "黄果树": (25.9918, 105.6657, "贵州"),
    # 云南
    "昆明": (25.0406, 102.7122, "云南"),
    "大理": (25.6065, 100.2676, "云南"),
    "丽江": (26.8721, 100.2299, "云南"),
    "香格里拉": (27.8299, 99.7069, "云南"),
    # 西藏
    "拉萨": (29.6500, 91.1000, "西藏"),
    "林芝": (29.6490, 94.3624, "西藏"),
    # 陕西
    "西安": (34.3416, 108.9398, "陕西"),
    "延安": (36.5853, 109.4898, "陕西"),
    "蒲城": (34.9566, 109.5878, "陕西"),
    # 甘肃
    "兰州": (36.0611, 103.8343, "甘肃"),
    "敦煌": (40.1421, 94.6626, "甘肃"),
    "张掖": (38.9260, 100.4514, "甘肃"),
    # 青海
    "西宁": (36.6171, 101.7782, "青海"),
    "青海湖": (36.9000, 100.1500, "青海"),
    # 宁夏
    "银川": (38.4872, 106.2309, "宁夏"),
    # 新疆
    "乌鲁木齐": (43.8256, 87.6168, "新疆"),
    "喀什": (39.4547, 75.9900, "新疆"),
    "吐鲁番": (42.9513, 89.1899, "新疆"),
    # 特别行政区 & 台湾
    "香港": (22.3193, 114.1694, "香港"),
    "澳门": (22.1987, 113.5439, "澳门"),
    "台北": (25.0330, 121.5654, "台湾"),
    "高雄": (22.6273, 120.3014, "台湾"),
}


class LocationProcessor:
    def __init__(self):
        # translator instance
        from core.translator import get_translator
        self.translator = get_translator()
        self._translation_cache = {}
        
        # Load Static Map
        self.place_map = {}
        try:
            import os
            import json
            # Try multiple possible locations for place_map.json
            current_dir = os.path.dirname(os.path.abspath(__file__))
            possible_paths = [
                os.path.join(current_dir, "..", "assets", "place_map.json"),
                os.path.join(current_dir, "assets", "place_map.json"), # In case integrated
                os.path.join(os.path.dirname(current_dir), "assets", "place_map.json")
            ]
            
            # Add absolute path check for src/assets as found in research
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            possible_paths.append(os.path.join(base_dir, "assets", "place_map.json"))
            possible_paths.append(os.path.join(base_dir, "src", "assets", "place_map.json"))

            found = False
            for map_path in possible_paths:
                if os.path.exists(map_path):
                    with open(map_path, 'r', encoding='utf-8') as f:
                        self.place_map = json.load(f)
                    logger.info(f"[LocationProcessor] Loaded {len(self.place_map)} manual translations from {map_path}")
                    found = True
                    break
            
            if not found:
                logger.warning("[LocationProcessor] Warning: place_map.json not found in searched paths.")
        except Exception as e:
            logger.warning(f"[LocationProcessor] Warning: Could not load place_map.json: {e}")

    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2):
        """Calculate distance in km between two GPS coordinates using Haversine formula."""
        R = 6371.0  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def match_nearest_china_city(self, lat, lon, max_distance_km=50):
        """
        Match GPS coordinates to the nearest standard China city name.
        Returns dict {city, province} or None if no match within max_distance_km.
        """
        if lat is None or lon is None:
            return None

        best_city = None
        best_province = None
        best_dist = float('inf')

        for city_name, (city_lat, city_lon, province) in STANDARD_CHINA_CITIES.items():
            dist = self._haversine_km(lat, lon, city_lat, city_lon)
            if dist < best_dist:
                best_dist = dist
                best_city = city_name
                best_province = province

        if best_dist <= max_distance_km:
            return {"city": best_city, "province": best_province, "distance_km": round(best_dist, 1)}
        return None

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
        except Exception:
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
            logger.error(f"Translation failed for '{text}': {e}")
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
            logger.error(f"[LocationProcessor] Reverse geocoding error: {e}")
            
        return {
            "latitude": lat,
            "longitude": lon,
            "city": "",
            "province": "",
            "country_code": ""
        }
    def infer_from_path(self, path: str):
        """
        从文件路径中推断位置。
        简单策略：检查路径中是否包含已知的城市/省份名称。
        利用 place_map 中的中文名称及常见城市列表。
        """
        # 中国主要城市坐标字典 (中心点) - 用于路径识别后的坐标补全
        CHINA_CITY_COORDS = {
            "北京": (39.9042, 116.4074), "上海": (31.2304, 121.4737), "广州": (23.1291, 113.2644), "深圳": (22.5431, 114.0579),
            "杭州": (30.2741, 120.1551), "南京": (32.0603, 118.7969), "武汉": (30.5928, 114.3055), "西安": (34.3416, 108.9398),
            "成都": (30.5728, 104.0668), "重庆": (29.5630, 106.5516), "苏州": (31.2990, 120.5853), "天津": (39.0841, 117.2010),
            "青岛": (36.0671, 120.3826), "长沙": (28.2282, 112.9388), "沈阳": (41.8057, 123.4315), "郑州": (34.7466, 113.6253),
            "大连": (38.9140, 121.6147), "东莞": (23.0205, 113.7518), "宁波": (29.8683, 121.5440), "厦门": (24.4798, 118.0894),
            "昆明": (25.0406, 102.7122), "合肥": (31.8206, 117.2272), "佛山": (23.0215, 113.1214), "福州": (26.0745, 119.2965),
            "哈尔滨": (45.8038, 126.5350), "济南": (36.6512, 117.1201), "无锡": (31.4912, 120.3119), "长春": (43.8171, 125.3235),
            "温州": (27.9943, 120.6993), "石家庄": (38.0423, 114.5089), "南宁": (22.8170, 108.3661), "贵阳": (26.5783, 106.7139),
            "南昌": (28.6820, 115.8579), "太原": (37.8706, 112.5489), "烟台": (37.4638, 121.4479), "海口": (20.0174, 110.3492),
            "珠海": (22.2707, 113.5767), "兰州": (36.0611, 103.8343), "中山": (22.5176, 113.3928), "清远": (23.6811, 113.0560),
            "惠州": (23.1118, 114.4162), "汕头": (23.3541, 116.6818), "嘉兴": (30.7459, 120.7555), "威海": (37.5013, 122.1204),
            "韶关": (24.8111, 113.5975), "蒲城": (34.9566, 109.5878), # 用户特别提到的地点
            "河南": (34.7655, 113.7536), "开封": (34.7970, 114.3072), "澳门": (22.1987, 113.5439), "镇江": (32.2036, 119.4551)  # 新增地点
        }

        try:
            # 1. 构建关键词库
            known_places = set(self.place_map.values())
            known_places.update(CHINA_CITY_COORDS.keys())
            
            # 2. 规范化路径
            normalized_path = path.replace("\\", "/")
            parts = normalized_path.split("/")
            
            # 查找逻辑：优先匹配文件名前面的目录名，匹配尽可能详细的地名
            # 为了防止“上海”匹配到“上海滩”，我们按照地名长度递减排序
            sorted_places = sorted(list(known_places), key=len, reverse=True)
            
            for part in reversed(parts): # 检查所有部分，包括文件名
                for place in sorted_places:
                    if place and len(place) >= 2 and place in part:
                        # 找到匹配!
                        coords = CHINA_CITY_COORDS.get(place)
                        
                        return {
                            "city": place,
                            "province": "", 
                            "source": "path",
                            "latitude": coords[0] if coords else None,
                            "longitude": coords[1] if coords else None
                        }
            return None
        except Exception as e:
            logger.error(f"[LocationProcessor] Path inference error: {e}")
            return None

    def interpolate(self, t1, loc1, t2, loc2, t_target):
        """
        线性插值计算经纬度。
        loc: (lat, lon)
        """
        if not loc1 or not loc2: return None
        
        ratio = (t_target - t1) / (t2 - t1)
        if ratio < 0 or ratio > 1: return None # Should not happen if sandwiched
        
        lat = loc1[0] + (loc2[0] - loc1[0]) * ratio
        lon = loc1[1] + (loc2[1] - loc1[1]) * ratio
        
        return lat, lon

    def infer_from_vlm(self, image: Image.Image):
        """
        使用 Qwen2-VL 识别地标。
        """
        try:
            # 尝试导入 Transformers
            from transformers import Qwen2VLForConditionalGeneration, AutoProcessor  # noqa: F401
            import torch  # noqa: F401
            
            
            # 这是一个重型操作，建议做成单例或者是类变量，避免每次加载
            # 简易实现：检查是否已在 GlobalState 加载？ 或者这里独立加载（很慢）
            # 为了演示，我们假设模型已加载或在此处加载（仅供 Refiner 批量调用）
            # 实际部署应由 ModelManager 管理
            
            # 暂时 Mock 或者 检查本地是否存在模型，不存在则跳过
            # print("[LocationProcessor] VLM inference is a placeholder unless model exists.")
            return None 

        except ImportError:
            return None
        except Exception as e:
            logger.error(f"[LocationProcessor] VLM error: {e}")
            return None

    def infer_from_ocr(self, image: Image.Image):
        """
        使用 OCR 提取文字并进行地理编码。
        """
        try:
            from paddleocr import PaddleOCR  # noqa: F401
            # ocr = PaddleOCR(use_angle_cls=True, lang="ch") 
            # res = ocr.ocr(image_array)
            # 提取文本 -> 匹配地名 -> Geocode
            return None
        except ImportError:
            return None
        except Exception as e:
            logger.error(f"[LocationProcessor] OCR error: {e}")
            return None
