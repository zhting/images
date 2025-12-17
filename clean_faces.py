
import os
import sys
import numpy as np
from PIL import Image
import sqlite3
import json

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)
# Also add parent dir for src.core resolution if run from root
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from src.core.face_processor import FaceProcessor
from src.database.sqlite_store import SQLiteStore

def cleanup_faces():
    print("Starting face cleanup...")
    
    # Init DB and Processor
    db_name = "history.db" # The faces are in history.db (SQLiteStore default), not search.db (VectorDB)
    db_path = os.path.join(current_dir, db_name)
    if not os.path.exists(db_path):
        # try parent
        db_path = os.path.join(parent_dir, db_name)
        
    print(f"Using DB: {db_path}")
    store = SQLiteStore(db_path=db_path)
    processor = FaceProcessor(provider="cpu") 
    
    # Get all faces
    # SQLiteStore.get_all_faces returns id, file_path, embedding, person_id
    # We ALSO need bbox to strict check. 
    # But `get_all_faces` currently doesn't return bbox.
    # We need to query manually or extend store.
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT id, file_path, bbox FROM faces')
    rows = cursor.fetchall()
    
    total = len(rows)
    print(f"Total faces to check: {total}")
    
    removed_count = 0
    
    for i, (face_id, file_path, bbox_json) in enumerate(rows):
        if i % 10 == 0:
            print(f"Processing {i}/{total}...", end='\r')
            
        if not os.path.exists(file_path):
            print(f"File missing: {file_path}. Removing face.")
            cursor.execute('DELETE FROM faces WHERE id=?', (face_id,))
            removed_count += 1
            continue
            
        try:
            # Parse stored bbox
            bbox = json.loads(bbox_json) # [x1, y1, x2, y2]
            stored_box = np.array(bbox)
            
            # Re-detect
            img = Image.open(file_path)
            new_faces = processor.detect_faces(img)
            
            # Check overlap
            match_found = False
            for new_face in new_faces:
                nb = np.array(new_face['bbox']) # [x1, y1, x2, y2]
                
                # Compute IoU
                xA = max(stored_box[0], nb[0])
                yA = max(stored_box[1], nb[1])
                xB = min(stored_box[2], nb[2])
                yB = min(stored_box[3], nb[3])
                
                interArea = max(0, xB - xA) * max(0, yB - yA)
                boxAArea = (stored_box[2] - stored_box[0]) * (stored_box[3] - stored_box[1])
                boxBArea = (nb[2] - nb[0]) * (nb[3] - nb[1])
                
                iou = interArea / float(boxAArea + boxBArea - interArea)
                
                if iou > 0.3: # Loose IoU match to confirm it's roughly the same "thing" that is now detecting as a face
                    match_found = True
                    break
            
            if not match_found:
                # The stored face is NO LONGER detecting as a face with stricter settings
                print(f"Removing invalid face ID {face_id} from {os.path.basename(file_path)}")
                cursor.execute('DELETE FROM faces WHERE id=?', (face_id,))
                removed_count += 1
                
        except Exception as e:
            print(f"Error checking face {face_id}: {e}")
            
    conn.commit()
    conn.close()
    print(f"\nCleanup complete. Removed {removed_count} faces.")

if __name__ == "__main__":
    cleanup_faces()
