import sys
import os

# Add src to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(os.path.dirname(current_dir), "src")
if src_dir not in sys.path:
    sys.path.append(src_dir)

from database.vector_db import VectorDB
from database.sqlite_store import SQLiteStore

def clean_translations():
    print("Reading config from SQLiteStore...")
    store = SQLiteStore()
    db_path = store.get_config("db_path", "./search.db")
    print(f"Target DB Path: {db_path}")

    print("Initialize VectorDB...")
    db = VectorDB(db_path=db_path) 
    
    # 1. Fetch all metadata
    print("Fetching all file metadata...")
    file_map = db.get_all_files_with_time(include_embeddings=False)
    
    refusal_keywords = [
        "cannot provide", "I can't", "apologize", "I am sorry", "I'm sorry", 
        "provide the translation", "content policy", "violate",
        "对不起", "不能提供", "无法提供", "语言模型", "Policy",
        "AI language model", "unable to translate", "cannot translate" 
    ]
    
    dirty_count = 0
    fixed_count = 0
    
    unique_cities = set()
    unique_provinces = set()

    print(f"Total files to scan: {len(file_map)}")

    for file_info in file_map:
        file_path = file_info.get("file_path")
        loc = file_info.get("location_info", {})
        
        city = loc.get("city", "")
        province = loc.get("province", "")
        
        if city: unique_cities.add(city)
        if province: unique_provinces.add(province)
        
        is_dirty = False
        
        # Check City
        for kw in refusal_keywords:
            if kw.lower() in city.lower():
                print(f"[Dirty City] {file_path}: {city}")
                city = "" # Reset
                is_dirty = True
                break
                
        # Check Province
        for kw in refusal_keywords:
            if kw.lower() in province.lower():
                print(f"[Dirty Province] {file_path}: {province}")
                province = "" # Reset
                is_dirty = True
                break
    
    print("--- Sample Cities ---")
    print(list(unique_cities)[:20])
    print("--- Sample Provinces ---")
    print(list(unique_provinces)[:20])
    
    # Re-loop to apply fixes if any (or we could have done it in the first loop)
    # The first loop logic was: check -> set updated var -> if is_dirty: update.
    # Wait, my previous code had `if is_dirty:` block INSIDE the loop. 
    # But I replaced the start of the loop. I need to be careful with indentation.
    # Actually, I am replacing lines 33-64 which covers the initial check loop.
    # I should construct the replacement correctly.
    
    # Let's just rewrite the loop part cleanly.
    
    for file_info in file_map:
        file_path = file_info.get("file_path")
        loc = file_info.get("location_info", {})
        
        original_city = loc.get("city", "")
        original_province = loc.get("province", "")
        
        city = original_city
        province = original_province
        
        is_dirty = False
        
        # Check City
        for kw in refusal_keywords:
            if kw.lower() in city.lower():
                print(f"[Dirty City] {file_path}: {city}")
                city = "" 
                is_dirty = True
                break
                
        # Check Province
        for kw in refusal_keywords:
            if kw.lower() in province.lower():
                print(f"[Dirty Province] {file_path}: {province}")
                province = "" 
                is_dirty = True
                break
        
        if is_dirty:
            dirty_count += 1
            # Update DB
            # We need to construct the full location info object carefully to avoid overwriting coords with None if they exist
            # But the 'update_location' method in VectorDB handles keys, but we should be careful.
            # Let's check update_location implementation again.
            # It merges: meta["city"] = location_info.get("city", "") ...
            
            new_loc = {
                "city": city,
                "province": province,
                "country_code": loc.get("country_code", ""),
                "latitude": loc.get("latitude"),
                "longitude": loc.get("longitude"),
                "source": "cleaned"
            }
            
            try:
                db.update_location(file_path, new_loc)
                fixed_count += 1
                print(f" -> Fixed: {file_path}")
            except Exception as e:
                print(f" -> Failed to update {file_path}: {e}")

    print(f"Scan complete. Found {dirty_count} dirty records. Fixed {fixed_count}.")

if __name__ == "__main__":
    clean_translations()
