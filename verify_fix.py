
import sys
import os
from PIL import Image

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from src.core.models import VisionModel

def verify():
    print("Loading VisionModel...")
    model = VisionModel()
    
    samples = {
        "IMG_7220 (Food)": r"E:\本地照片\赵挺的手机照片\位置测试\IMG_7220.JPEG",
        "IMG_6710 (Kid)": r"E:\本地照片\赵挺的手机照片\位置测试\IMG_6710.JPG"
    }
    
    for name, path in samples.items():
        if not os.path.exists(path):
            print(f"{name} not found.")
            continue
            
        print(f"Testing {name}...")
        img = Image.open(path)
        result = model.classify_type(img)
        print(f"  Result: {result}")
        
        if "Food" in name and result != "photo":
            print("  FAIL: Should be photo.")
        elif "Kid" in name and result != "photo":
            print("  WARN: Should ideally be photo, but might be document/screenshot.")
        else:
            print("  PASS")

if __name__ == "__main__":
    verify()
