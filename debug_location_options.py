
import reverse_geocoder as rg
from deep_translator import GoogleTranslator
import sys
import os

# Mock Qwen LocalTranslator
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from src.core.translator import translator

def test_location(lat, lon):
    print(f"\n--- Testing ({lat}, {lon}) ---")
    
    # 1. Reverse Geocoder (Offline, English)
    results = rg.search((lat, lon))
    name = ""
    admin1 = ""
    if results:
        res = results[0]
        name = res.get("name", "")
        admin1 = res.get("admin1", "")
        print(f"rg output: name='{name}', admin1='{admin1}'")
        
    # 2. Google Translate (Online)
    try:
        g_trans = GoogleTranslator(source='auto', target='zh-CN')
        print(f"Google Translate 'name': {g_trans.translate(name)}")
    except Exception as e:
        print(f"Google Translate Error: {e}")

    # 3. Local Qwen 0.5B (Offline)
    print(f"Qwen 0.5B 'name': {translator.translate_to_chinese(name)}")

if __name__ == "__main__":
    # IMG_6625 coords (Shaanxi, Yanta?)
    test_location(34.204333, 108.956008)
    
    # Changyanbao coords? 
    # Let's try to mock the name "Changyanbao" since we don't have coords
    print("\n--- Testing specific names ---")
    names = ["Yanta", "Changyanbao", "Ziyou"]
    
    for n in names:
        print(f"\nName: {n}")
        try:
            g = GoogleTranslator(source='auto', target='zh-CN').translate(n)
            print(f"Google: {g}")
        except: pass
        
        q = translator.translate_to_chinese(n)
        print(f"Qwen 0.5B: {q}")
