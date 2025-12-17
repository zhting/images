
import os
import sys
import time
from datetime import datetime

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
if src_dir not in sys.path:
    sys.path.append(src_dir)

from database.vector_db import VectorDB

def check_file():
    db_path = os.path.join(current_dir, "search.db")
    db = VectorDB(db_path)
    files = db.get_all_files_with_time()

    print(f"Current System Time: {datetime.now()}")
    print(f"Target Month/Day: {datetime.now().month}/{datetime.now().day}")
    
    count_12_17 = 0
    matches = []
    
    for f in files:
        ts = f.get('captured_time')
        if ts:
            dt = datetime.fromtimestamp(ts)
            if dt.month == 12 and dt.day == 17:
                count_12_17 += 1
                matches.append(f"{f['file_path']} ({dt.year})")
    
    print(f"\nTotal files in DB for Dec 17: {count_12_17}")
    for m in matches[:10]:
        print(f" - {m}")
    if len(matches) > 10:
        print(f" ... and {len(matches)-10} more")

if __name__ == "__main__":
    check_file()
