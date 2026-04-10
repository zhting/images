import sqlite3
import datetime
import hashlib
import os
import secrets
import json
from contextlib import contextmanager

class SQLiteStore:
    def __init__(self, db_path="./history.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = __import__('threading').Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            cursor = self._conn.cursor()
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
            # Person names mapping
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS person_names (
                    person_id INTEGER PRIMARY KEY,
                    custom_name TEXT
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_faces_person_id ON faces(person_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_faces_file_path ON faces(file_path)')
            # NEW: Named identities with embeddings for persistent identification
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS named_identities (
                    name TEXT PRIMARY KEY,
                    embedding BLOB
                )
            ''')
            self._conn.commit()

    @contextmanager
    def _get_conn(self):
        with self._lock:
            yield self._conn

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

    def get_all_config(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT key, value FROM system_config')
            return {row[0]: row[1] for row in cursor.fetchall()}

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
        import json
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, file_path, embedding, person_id, bbox FROM faces')
            rows = cursor.fetchall()
            # convert bytes back to numpy
            faces = []
            for r in rows:
                faces.append({
                    "id": r[0],
                    "file_path": r[1],
                    "embedding": np.frombuffer(r[2], dtype=np.float32), 
                    "person_id": r[3],
                    "bbox": json.loads(r[4]) if r[4] else None
                })
            return faces

    def get_face(self, face_id):
        import json
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, file_path, bbox, person_id FROM faces WHERE id = ?', (face_id,))
            r = cursor.fetchone()
            if r:
                return {
                    "id": r[0],
                    "file_path": r[1],
                    "bbox": json.loads(r[2]) if r[2] else None,
                    "person_id": r[3]
                }
            return None

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

    def clear_faces(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM faces')
            conn.commit()

    def delete_faces(self, file_path: str):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM faces WHERE file_path = ?', (file_path,))
            conn.commit()

    # --- Person Management ---
    def set_person_name(self, person_id: int, name: str):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if not name:
                cursor.execute('DELETE FROM person_names WHERE person_id = ?', (person_id,))
            else:
                cursor.execute('INSERT OR REPLACE INTO person_names (person_id, custom_name) VALUES (?, ?)', 
                               (person_id, name))
            conn.commit()

    def get_person_names(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT person_id, custom_name FROM person_names')
            return {r[0]: r[1] for r in cursor.fetchall()}

    def get_faces_by_person_id(self, person_id: int):
        import numpy as np
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT embedding FROM faces WHERE person_id = ?', (person_id,))
            embeddings = [np.frombuffer(r[0], dtype=np.float32) for r in cursor.fetchall()]
            return embeddings

    # --- Persistent Identity Management ---
    def upsert_identity(self, name: str, embedding):
        """Save or update a named identity template."""
        emb_bytes = embedding.tobytes()
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO named_identities (name, embedding) VALUES (?, ?)', 
                           (name, emb_bytes))
            conn.commit()

    def get_all_identities(self):
        """Get all saved identity templates."""
        import numpy as np
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name, embedding FROM named_identities')
            return {r[0]: np.frombuffer(r[1], dtype=np.float32) for r in cursor.fetchall()}

    def reset_person_cluster(self, person_id: int):
        """Reset all faces in this cluster to -1 and remove custom name."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE faces SET person_id = -1 WHERE person_id = ?', (person_id,))
            cursor.execute('DELETE FROM person_names WHERE person_id = ?', (person_id,))
            conn.commit()

    def prune_orphaned_faces(self, valid_paths: set):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # 1. Get all distinct paths in faces
            cursor.execute('SELECT DISTINCT file_path FROM faces')
            rows = cursor.fetchall()
            existing_paths = {r[0] for r in rows}
            
            # 2. Find orphans
            orphans = existing_paths - valid_paths
            
            if orphans:
                print(f"Pruning {len(orphans)} orphaned file records from faces.")
                for path in orphans:
                     cursor.execute('DELETE FROM faces WHERE file_path = ?', (path,))
                conn.commit()
                return len(orphans)
            return 0

    def get_clustered_people(self):
        """
        Returns stats about clustered people from DB.
        result: [{person_id, count, cover_face_id, cover_file_path, custom_name}]
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # This query groups by person_id and counts faces.
            # It also joins with person_names to get custom names.
            # It blindly picks a cover image (MAX(id) or MIN(id) or arbitrary).
            # We exclude person_id = -1 (noise).
            
            query = '''
                SELECT 
                    f.person_id,
                    COUNT(f.id) as count,
                    n.custom_name,
                    MIN(f.id) as cover_id,
                    MIN(f.file_path) as cover_path
                FROM faces f
                LEFT JOIN person_names n ON f.person_id = n.person_id
                WHERE f.person_id != -1
                GROUP BY f.person_id
                ORDER BY count DESC
            '''
            cursor.execute(query)
            rows = cursor.fetchall()
            
            result = []
            for r in rows:
                result.append({
                    "id": r[0],
                    "count": r[1],
                    "name": r[2] if r[2] else f"Person {r[0]}",
                    "cover_face_id": r[3],
                    "cover_file_path": r[4],
                    "has_custom_name": bool(r[2])
                })
            return result

    def update_face_cluster(self, face_id: int, person_id: int):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE faces SET person_id = ? WHERE id = ?', (person_id, face_id))
            conn.commit()
            
    def batch_update_face_clusters(self, updates: list):
        """
        Batch updates face clusters. updates is a list of tuples: [(person_id, face_id), ...]
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.executemany('UPDATE faces SET person_id = ? WHERE id = ?', updates)
            conn.commit()
            
    def clear_all_clusters(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE faces SET person_id = -1')
            conn.commit()

    # --- Privacy & Locking ---
    def set_privacy_password(self, password: str):
        """Sets a new privacy password using PBKDF2 hashing."""
        salt = secrets.token_hex(16)
        # Using 100,000 iterations of SHA-256
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt.encode('utf-8'), 
            100000
        ).hex()
        
        self.set_config("privacy_password_hash", pwd_hash)
        self.set_config("privacy_password_salt", salt)

    def verify_privacy_password(self, password: str) -> bool:
        """Verifies the provided password against the stored hash."""
        stored_hash = self.get_config("privacy_password_hash")
        salt = self.get_config("privacy_password_salt")
        
        if not stored_hash or not salt:
            return False
            
        test_hash = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt.encode('utf-8'), 
            100000
        ).hex()
        
        return secrets.compare_digest(stored_hash, test_hash)

    def is_privacy_password_set(self) -> bool:
        """Returns True if a privacy password has been configured."""
        return self.get_config("privacy_password_hash") is not None

    def clear_privacy_password(self):
        """Removes the privacy password and salt."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM system_config WHERE key IN ("privacy_password_hash", "privacy_password_salt")')
            conn.commit()

    def get_locked_folders(self) -> list:
        """Returns the list of currently locked directory paths."""
        val = self.get_config("locked_folders")
        if val:
            try:
                return json.loads(val)
            except:
                return []
        return []

    def set_locked_folders(self, paths: list):
        """Saves the list of locked directory paths."""
        self.set_config("locked_folders", json.dumps(paths))

    def add_locked_folder(self, path: str):
        """Adds a path to the locked folders list."""
        paths = self.get_locked_folders()
        # Normalize path
        norm_path = path.replace("\\", "/").rstrip("/")
        if norm_path not in paths:
            paths.append(norm_path)
            self.set_locked_folders(paths)

    def remove_locked_folder(self, path: str):
        """Removes a path from the locked folders list."""
        paths = self.get_locked_folders()
        norm_path = path.replace("\\", "/").rstrip("/")
        if norm_path in paths:
            paths.remove(norm_path)
            self.set_locked_folders(paths)

    def is_path_locked(self, path: str, locked_folders: list = None) -> bool:
        """
        Checks if a given file or directory path is within a locked directory.
        If locked_folders is provided, it uses that list instead of fetching from DB.
        """
        if locked_folders is None:
            locked_folders = self.get_locked_folders()
            
        if not locked_folders:
            return False
            
        norm_path = path.replace("\\", "/").rstrip("/")
        for lp in locked_folders:
            # Check if norm_path is lp or a child of lp
            # e.g., lp = "C:/Photos/Private", norm_path = "C:/Photos/Private/1.jpg"
            if norm_path == lp or norm_path.startswith(lp + "/"):
                return True
        return False

