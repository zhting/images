import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from database.vector_db import VectorDB
from database.sqlite_store import SQLiteStore

def inspect_db():
    print("Initializing DB...")
    try:
        db = VectorDB(db_path="./search.db")
        store = SQLiteStore()
        
        print(f"Total documents: {db.count()}")
        
        files = db.get_all_files_with_time()
        if not files:
            print("No files found in DB.")
            return

        print(f"Retrieved {len(files)} files.")
        
        # Check first 5 files for smart metadata
        print("\n--- Inspecting Metadata (First 5) ---")
        for i, f in enumerate(files[:5]):
            print(f"\nFile: {os.path.basename(f['file_path'])}")
            print(f"  City: {f.get('city')}")
            print(f"  Province: {f.get('province')}")
            print(f"  Auto Tags: {f.get('auto_tags')}")
            # Check embedding presence
            has_emb = f.get('embedding') is not None
            print(f"  Has Embedding: {has_emb}")
            
        # Check Faces in SQLite
        print("\n--- Inspecting Faces (SQLite) ---")
        faces = store.get_all_faces()
        print(f"Total Faces: {len(faces)}")
        if faces:
            print(f"Sample Face: {faces[0]}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    inspect_db()
