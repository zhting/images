import sys
import os

# Add src to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(os.path.dirname(current_dir), "src")
if src_dir not in sys.path:
    sys.path.append(src_dir)

from database.vector_db import VectorDB
from database.sqlite_store import SQLiteStore

def count_stats():
    print("Reading config from SQLiteStore...")
    store = SQLiteStore()
    db_path = store.get_config("db_path", "./search.db")
    # For safety/debug, print the db path
    print(f"Target DB Path: {db_path}")

    print("Initialize VectorDB...")
    try:
        db = VectorDB(db_path=db_path) 
        
        print("Fetching stats...")
        stats = db.get_stats()
        print("\n=== Database Statistics ===")
        print(f"Total Items: {stats.get('total')}")
        print(f"Photos:      {stats.get('photo')}")
        print(f"Videos:      {stats.get('video')}")
        print(f"Screenshots: {stats.get('screenshot')}")
        print(f"Documents:   {stats.get('document')}")
        if 'other' in stats and stats['other'] > 0:
            print(f"Others:      {stats.get('other')}")
        print("===========================\n")
        
    except Exception as e:
        print(f"Error checking stats: {e}")

if __name__ == "__main__":
    count_stats()
