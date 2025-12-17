
import sqlite3
import os
import json

def find_paths():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, "history.db")
    
    if not os.path.exists(db_path):
        print("DB not found")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM system_config WHERE key='asset_paths'")
    row = cursor.fetchone()
    if not row:
        print("No asset paths config.")
        return
        
    paths = json.loads(row[0])
    print(f"Scanning paths: {paths}")
    
    targets = ["IMG_7220", "IMG_686", "IMG_683", "IMG_684", "IMG_6812", "IMG_6760", "IMG_6711", "IMG_6710"]
    
    found = {}
    
    for p in paths:
        if not os.path.exists(p): continue
        for root, _, files in os.walk(p):
            for f in files:
                for t in targets:
                    if t in f:
                        found[t] = os.path.join(root, f)
                        
    print("Found files:")
    for k, v in found.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    find_paths()
