import sqlite3
import datetime
from contextlib import contextmanager

class SQLiteStore:
    def __init__(self, db_path="./history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS generation_history (
                    id TEXT PRIMARY KEY, 
                    prompt TEXT, 
                    image_path TEXT, 
                    created_at TIMESTAMP,
                    api_provider TEXT
                )
            ''')
            # Configuration table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            # Faces table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS faces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT,
                    embedding BLOB,
                    bbox TEXT,
                    person_id INTEGER DEFAULT -1
                )
            ''')
            conn.commit()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    # --- Config Methods ---
    def set_config(self, key: str, value: str):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)', (key, value))
            conn.commit()

    def get_config(self, key: str, default=None) -> str:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM system_config WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    # --- Asset Path Helpers ---
    def get_asset_paths(self) -> list:
        import json
        val = self.get_config("asset_paths")
        if val:
            try:
                return json.loads(val)
            except:
                return []
        return []

    def save_asset_paths(self, paths: list):
        import json
        self.set_config("asset_paths", json.dumps(paths))

    def add_asset_path(self, path: str):
        paths = self.get_asset_paths()
        if path not in paths:
            paths.append(path)
            self.save_asset_paths(paths)

    def remove_asset_path(self, path: str):
        paths = self.get_asset_paths()
        if path in paths:
            paths.remove(path)
            self.save_asset_paths(paths)

    # --- History Methods ---
    def add_record(self, record_id: str, prompt: str, image_path: str, api_provider: str = "mock"):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO generation_history (id, prompt, image_path, created_at, api_provider)
                VALUES (?, ?, ?, ?, ?)
            ''', (record_id, prompt, image_path, datetime.datetime.now(), api_provider))
            conn.commit()

    def get_recent(self, limit=10):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, prompt, image_path, created_at, api_provider 
                FROM generation_history 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            return cursor.fetchall()
            
    # --- Face Methods ---
    def create_faces_table(self):
        # Already done in _init_db, but keep for compatibility if called explicitly
        pass

    def add_face(self, file_path, embedding, bbox):
        # embedding is numpy array, convert to bytes
        import numpy as np
        import json
        emb_bytes = embedding.tobytes()
        bbox_json = json.dumps(bbox)
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO faces (file_path, embedding, bbox) VALUES (?, ?, ?)', 
                           (file_path, emb_bytes, bbox_json))
            conn.commit()
    
    def get_all_faces(self):
        import numpy as np
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, file_path, embedding, person_id FROM faces')
            rows = cursor.fetchall()
            # convert bytes back to numpy
            faces = []
            for r in rows:
                faces.append({
                    "id": r[0],
                    "file_path": r[1],
                    "embedding": np.frombuffer(r[2], dtype=np.float32), 
                    "person_id": r[3]
                })
            return faces

    def update_person_id(self, face_id, person_id):
         with self._get_conn() as conn:
             cursor = conn.cursor()
             cursor.execute('UPDATE faces SET person_id = ? WHERE id = ?', (person_id, face_id))
             conn.commit()
         
    def get_faces_by_person(self, person_id):
        import json
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT file_path, bbox FROM faces WHERE person_id = ?', (person_id,))
            return [{"file_path": r[0], "bbox": json.loads(r[1])} for r in cursor.fetchall()]
