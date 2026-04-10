import os
import sqlite3
import shutil

# This script creates an empty "dist_db_template" directory which will be bundled 
# or copied by the installer script to initialize a completely clean environment for the user.

def create_empty_infrastructure():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_dir = os.path.join(base_dir, "dist_db_template")
    
    # 1. Clear if exists
    if os.path.exists(template_dir):
        shutil.rmtree(template_dir)
    os.makedirs(template_dir)
    
    # 2. Create empty history.db schema
    history_path = os.path.join(template_dir, "history.db")
    conn = sqlite3.connect(history_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS generation_history (
        id TEXT PRIMARY KEY, prompt TEXT, image_path TEXT, created_at TIMESTAMP, api_provider TEXT)''')
    cursor.execute('CREATE TABLE IF NOT EXISTS system_config (key TEXT PRIMARY KEY, value TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS faces (id INTEGER PRIMARY KEY AUTOINCREMENT, file_path TEXT, embedding BLOB, bbox TEXT, person_id INTEGER DEFAULT -1)')
    cursor.execute('CREATE TABLE IF NOT EXISTS person_names (person_id INTEGER PRIMARY KEY, custom_name TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS named_identities (name TEXT PRIMARY KEY, embedding BLOB)')
    conn.commit()
    conn.close()

    # 3. Create empty search_v2.db schema
    search_path = os.path.join(template_dir, "search_v2.db")
    conn = sqlite3.connect(search_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE locations (id INTEGER PRIMARY KEY, path TEXT UNIQUE, location TEXT)')
    cursor.execute('CREATE TABLE place_cache (coordinates TEXT PRIMARY KEY, location_data TEXT)')
    cursor.execute('''CREATE TABLE tags (
                        id INTEGER PRIMARY KEY,
                        path TEXT UNIQUE,
                        tags TEXT,
                        width INTEGER,
                        height INTEGER,
                        aspect_ratio REAL
                    )''')
    cursor.execute('''CREATE TABLE config (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )''')
    # Pre-seed the system with an empty asset_paths list so the first boot doesn't crash mapping
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('asset_paths', '[]')")
    cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('db_version', '2.0')")
    conn.commit()
    conn.close()

    # 4. Create an empty Chroma vector DB directory Structure
    chroma_dir = os.path.join(template_dir, "chroma_v2")
    os.makedirs(chroma_dir, exist_ok=True)

    print(f"Empty database infrastructure created at: {template_dir}")
    print("The packager should copy the contents of this folder into the target build output directory.")

if __name__ == "__main__":
    create_empty_infrastructure()
