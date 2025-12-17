
import os
import sys

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
if src_dir not in sys.path:
    sys.path.append(src_dir)

from database.vector_db import VectorDB

def check_gps():
    db_path = os.path.join(current_dir, "search.db")
    print(f"Checking DB at: {db_path}")
    
    try:
        db = VectorDB(db_path)
        files = db.get_all_files_with_time()
        
        total = len(files)
        with_gps = 0
        samples = []
        
        for f in files:
            lat = f.get('latitude')
            lon = f.get('longitude')
            if lat is not None and lon is not None:
                with_gps += 1
                if len(samples) < 5:
                    samples.append(f)
                    
        print(f"Total Files in DB: {total}")
        print(f"Files with GPS: {with_gps}")
        
        if with_gps > 0:
            print("\nSample GPS Data:")
            for s in samples:
                print(f"File: {os.path.basename(s['file_path'])}")
                print(f"  Loc: {s.get('city')}, {s.get('province')}")
                print(f"  Lat/Lon: {s.get('latitude')}, {s.get('longitude')}")
        else:
            print("\nNO GPS DATA FOUND found in any file.")
            print("Likely causes:")
            print("1. Indexing crashed before GPS extraction.")
            print("2. Images simply don't have GPS.")
            print("3. LocationProcessor failed silently.")
            
    except Exception as e:
        print(f"Error checking DB: {e}")

if __name__ == "__main__":
    check_gps()
