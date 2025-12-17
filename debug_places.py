import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from src.database.vector_db import VectorDB

def debug():
    try:
        db = VectorDB()
        print(f"DEBUG: Collection Name: {db.collection.name}")
        count = db.collection.count()
        print(f"DEBUG: Total Count: {count}")
        
        if count > 0:
            peek = db.collection.peek(limit=1)
            metas = peek['metadatas']
            if metas and len(metas) > 0:
                print("DEBUG: Sample Metadata:")
                print(json.dumps(metas[0], indent=2, ensure_ascii=False))
            else:
                print("DEBUG: No metadata found in peek.")
                
            # Check a few for latitude
            res = db.collection.get(include=["metadatas"])
            all_meta = res['metadatas']
            gps_count = 0
            for m in all_meta:
                if 'latitude' in m:
                    gps_count += 1
            print(f"DEBUG: Files with 'latitude': {gps_count}")
        else:
            print("DEBUG: Collection is empty.")

    except Exception as e:
        print(f"DEBUG: Error: {e}")

if __name__ == "__main__":
    debug()
