import sys
import os
import json
import sqlite3
from PIL import Image

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Mock imports if needed, or import real ones
from src.database.vector_db import VectorDB
from src.core.tag_generator import TagGenerator
from src.core.models import VisionModel

def check_db_stats():
    print("=== DB Statistics ===")
    try:
        db = VectorDB()
        files = db.get_all_files_with_time()
        print(f"Total Files in VectorDB: {len(files)}")
        
        gps_count = 0
        tag_counts = {}
        
        for f in files:
            if f.get('latitude') is not None and f.get('longitude') is not None:
                gps_count += 1
            
            tags = f.get('auto_tags', [])
            for t in tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
                
        print(f"Files with GPS: {gps_count}")
        print(f"Unique Tags Found: {len(tag_counts)}")
        print(f"Top 5 Tags: {sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]}")
        
    except Exception as e:
        print(f"DB Error: {e}")

def test_tagging():
    print("\n=== Tagging Test ===")
    img_path = "proxy_debug.jpg"
    if not os.path.exists(img_path):
        # find one
        for root, _, files in os.walk("."):
            for f in files:
                if f.lower().endswith(('.jpg', '.png')):
                    img_path = os.path.join(root, f)
                    break
            if img_path != "proxy_debug.jpg": break
    
    if not os.path.exists(img_path):
        print("No test image found.")
        return

    print(f"Testing image: {img_path}")
    try:
        model = VisionModel()
        tg = TagGenerator(model)
        
        # Manually run generation with verbose score printing
        img = Image.open(img_path).convert('RGB')
        
        # This duplicates logic from generate_tags but allows us to see scores
        image_features = model.encode_image(img)
        text_features = tg.get_text_features() # Needs to be accessible
        
        # Calculate similarity
        # We need to access model internals likely, or use tg.generate_tags and debug
        # But tg.generate_tags filters.
        # Let's just run tg.generate_tags and modify source to print debug if needed?
        # Or just trust the output for now.
        
        tags = tg.generate_tags(img)
        print(f"Generated Tags: {tags}")
        
    except Exception as e:
        print(f"Tagging Error: {e}")

if __name__ == "__main__":
    check_db_stats()
    # test_tagging() # Commented out to avoid model load delay if not needed immediately
