
from PIL import Image
import sys
import os

def check():
    target = r"E:\本地照片\赵挺的手机照片\位置测试\IMG_6625.JPG"
    if not os.path.exists(target):
        # Scan for it
        import sqlite3
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, "history.db")
        if not os.path.exists(db_path):
             print("DB not found to scan assets.")
             return
             
        try:
             conn = sqlite3.connect(db_path)
             cursor = conn.cursor()
             # get config
             cursor.execute("SELECT value FROM system_config WHERE key='asset_paths'")
             row = cursor.fetchone()
             if row:
                  import json
                  paths = json.loads(row[0])
                  for p in paths:
                      for root, _, files in os.walk(p):
                           if "IMG_6625.JPG" in files:
                                target = os.path.join(root, "IMG_6625.JPG")
                                break
                      if target and os.path.exists(target): break
        except:
             pass

    if not target or not os.path.exists(target):
         print("Target not found.")
         return

    print(f"Testing: {target}")
    img = Image.open(target)
    exif = img._getexif()
    print(f"Original _getexif: {len(exif) if exif else 'None'}")
    
    img_conv = img.convert("RGB")
    exif_conv = img_conv._getexif()
    print(f"Converted _getexif: {len(exif_conv) if exif_conv else 'None'}")
    
    if (exif and not exif_conv):
        print("CONFIRMED: _getexif lost after convert.")
    else:
        print("Exif preserved.")

if __name__ == "__main__":
    check()
