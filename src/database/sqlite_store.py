import sqlite3
import datetime
import hashlib
import os
import secrets
import json
from contextlib import contextmanager

import logging
logger = logging.getLogger(__name__)

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
            # P1a data-layer refactor: SQLite is becoming the single source
            # of truth for photo metadata (ChromaDB keeps vectors only).
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS photos (
                    id              INTEGER PRIMARY KEY,
                    file_path       TEXT NOT NULL UNIQUE,
                    file_hash       TEXT,
                    last_modified   INTEGER NOT NULL DEFAULT 0,
                    captured_time   REAL NOT NULL DEFAULT 0,
                    tag             TEXT NOT NULL DEFAULT 'photo',
                    prev_tag        TEXT DEFAULT '',
                    aesthetic_score REAL NOT NULL DEFAULT 0.0,
                    latitude        REAL,
                    longitude       REAL,
                    city            TEXT NOT NULL DEFAULT '',
                    province        TEXT NOT NULL DEFAULT '',
                    country         TEXT NOT NULL DEFAULT '',
                    auto_tags       TEXT NOT NULL DEFAULT '',
                    indexed_at      INTEGER NOT NULL DEFAULT (strftime('%s','now'))
                )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_photos_captured ON photos(captured_time DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_photos_tag ON photos(tag)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_photos_city ON photos(city)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_photos_hash ON photos(file_hash)")
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
            except Exception:
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
                logger.info(f"Pruning {len(orphans)} orphaned file records from faces.")
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
            except Exception:
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


    # ------------------------------------------------------------------
    # Photos metadata (P1a refactor: single source of truth for metadata)
    # ------------------------------------------------------------------

    HIDDEN_TAGS = ('document', 'screenshot', 'trash', 'error')

    @staticmethod
    def norm_path(path: str) -> str:
        """Canonical path form used everywhere in the photos table."""
        return (path or '').replace('\\', '/')

    def upsert_photos(self, rows: list):
        """Idempotent batch upsert. Each row is a dict; only file_path is
        required — missing fields keep sensible defaults on insert and are
        preserved on update via COALESCE-style handling in Python."""
        if not rows:
            return 0
        with self._get_conn() as conn:
            cur = conn.cursor()
            for r in rows:
                fp = self.norm_path(r.get('file_path'))
                if not fp:
                    continue
                loc = r.get('location_info') or {}
                auto_tags = r.get('auto_tags')
                if isinstance(auto_tags, list):
                    auto_tags = ','.join(t for t in auto_tags if t)
                cur.execute('''
                    INSERT INTO photos (file_path, file_hash, last_modified,
                        captured_time, tag, aesthetic_score,
                        latitude, longitude, city, province, country, auto_tags)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(file_path) DO UPDATE SET
                        file_hash       = COALESCE(excluded.file_hash, photos.file_hash),
                        last_modified   = excluded.last_modified,
                        captured_time   = excluded.captured_time,
                        tag             = excluded.tag,
                        aesthetic_score = excluded.aesthetic_score,
                        latitude        = COALESCE(excluded.latitude, photos.latitude),
                        longitude       = COALESCE(excluded.longitude, photos.longitude),
                        city            = CASE WHEN excluded.city != '' THEN excluded.city ELSE photos.city END,
                        province        = CASE WHEN excluded.province != '' THEN excluded.province ELSE photos.province END,
                        country         = CASE WHEN excluded.country != '' THEN excluded.country ELSE photos.country END,
                        auto_tags       = CASE WHEN excluded.auto_tags != '' THEN excluded.auto_tags ELSE photos.auto_tags END
                ''', (
                    fp,
                    r.get('file_hash'),
                    int(r.get('last_modified') or 0),
                    float(r.get('captured_time') or 0),
                    r.get('tag') or 'photo',
                    float(r.get('aesthetic_score') or 0.0),
                    loc.get('latitude'), loc.get('longitude'),
                    loc.get('city') or '', loc.get('province') or '',
                    loc.get('country_code') or loc.get('country') or '',
                    auto_tags or '',
                ))
            conn.commit()
            return len(rows)

    def count_photos(self) -> int:
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM photos").fetchone()[0]

    def delete_photo(self, path: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM photos WHERE file_path = ?", (self.norm_path(path),))
            conn.commit()

    def trash_photo(self, path: str):
        """Mirror of VectorDB.soft_delete_file: tag -> trash, remember prev."""
        with self._get_conn() as conn:
            conn.execute('''UPDATE photos SET prev_tag = tag, tag = 'trash'
                            WHERE file_path = ? AND tag != 'trash' ''',
                         (self.norm_path(path),))
            conn.commit()

    def restore_photo(self, path: str):
        with self._get_conn() as conn:
            conn.execute('''UPDATE photos
                            SET tag = CASE WHEN prev_tag != '' THEN prev_tag ELSE 'photo' END,
                                prev_tag = ''
                            WHERE file_path = ? AND tag = 'trash' ''',
                         (self.norm_path(path),))
            conn.commit()

    def update_photo_location(self, path: str, info: dict):
        info = info or {}
        with self._get_conn() as conn:
            conn.execute('''UPDATE photos SET
                                latitude  = COALESCE(?, latitude),
                                longitude = COALESCE(?, longitude),
                                city      = CASE WHEN ? != '' THEN ? ELSE city END,
                                province  = CASE WHEN ? != '' THEN ? ELSE province END,
                                country   = CASE WHEN ? != '' THEN ? ELSE country END
                            WHERE file_path = ?''',
                         (info.get('latitude'), info.get('longitude'),
                          info.get('city') or '', info.get('city') or '',
                          info.get('province') or '', info.get('province') or '',
                          info.get('country_code') or info.get('country') or '',
                          info.get('country_code') or info.get('country') or '',
                          self.norm_path(path)))
            conn.commit()

    @staticmethod
    def _locked_clause(locked_prefixes: list):
        """WHERE fragment excluding photos under locked folders."""
        if not locked_prefixes:
            return '', []
        frags, params = [], []
        for p in locked_prefixes:
            norm = SQLiteStore.norm_path(p).rstrip('/') + '/'
            frags.append("file_path NOT LIKE ? ESCAPE '\\'")
            params.append(norm.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%')
        return ' AND ' + ' AND '.join(frags), params

    def get_timeline_page(self, limit: int, offset: int, locked_prefixes: list = None):
        """Paged timeline, newest first. Returns (items, total)."""
        ph = ','.join('?' * len(self.HIDDEN_TAGS))
        lock_sql, lock_params = self._locked_clause(locked_prefixes)
        base = f"FROM photos WHERE tag NOT IN ({ph}){lock_sql}"
        params = list(self.HIDDEN_TAGS) + lock_params
        with self._get_conn() as conn:
            total = conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
            rows = conn.execute(
                f'''SELECT file_path, captured_time, tag, aesthetic_score
                    {base} ORDER BY captured_time DESC LIMIT ? OFFSET ?''',
                params + [limit, offset]).fetchall()
        items = [{
            'file_path': r[0],
            'captured_time': float(r[1] or 0),
            'tag': r[2] or 'photo',
            'aesthetic_score': float(r[3] or 0.0),
            'basename': os.path.basename(r[0]) if r[0] else '',
        } for r in rows]
        return items, total

    def get_timeline_dates(self, locked_prefixes: list = None):
        """Month buckets for the date jump selector, newest first.
        Returns [{key: 'YYYY-MM'|'Unknown', index, count}] where index is
        the cumulative offset of the bucket in the timeline ordering."""
        ph = ','.join('?' * len(self.HIDDEN_TAGS))
        lock_sql, lock_params = self._locked_clause(locked_prefixes)
        params = list(self.HIDDEN_TAGS) + lock_params
        with self._get_conn() as conn:
            rows = conn.execute(
                f'''SELECT CASE WHEN captured_time <= 0 THEN 'Unknown'
                        ELSE strftime('%Y-%m', captured_time, 'unixepoch', 'localtime') END AS ym,
                        COUNT(*)
                    FROM photos WHERE tag NOT IN ({ph}){lock_sql}
                    GROUP BY ym
                    ORDER BY MAX(captured_time) DESC''', params).fetchall()
        dates, idx = [], 0
        for ym, count in rows:
            dates.append({'key': ym, 'index': idx, 'count': count})
            idx += count
        return dates

    def get_photos_by_paths(self, paths: list):
        """Batch detail lookup, chunked to stay under SQLite variable limits."""
        result = {}
        if not paths:
            return result
        norm = [self.norm_path(p) for p in paths]
        with self._get_conn() as conn:
            for i in range(0, len(norm), 500):
                chunk = norm[i:i + 500]
                ph = ','.join('?' * len(chunk))
                for r in conn.execute(
                        f'''SELECT file_path, captured_time, tag, aesthetic_score,
                                   latitude, longitude, city, province, country, auto_tags
                            FROM photos WHERE file_path IN ({ph})''', chunk):
                    result[r[0]] = {
                        'file_path': r[0], 'captured_time': float(r[1] or 0),
                        'tag': r[2], 'aesthetic_score': float(r[3] or 0.0),
                        'location_info': {
                            'latitude': r[4], 'longitude': r[5], 'city': r[6],
                            'province': r[7], 'country_code': r[8]},
                        'auto_tags': [t for t in (r[9] or '').split(',') if t],
                    }
        return result

    # ------------------------------------------------------------------
    # Organize-domain queries (P1a stage 2: full-scan call sites -> SQL)
    # ------------------------------------------------------------------

    def _row_to_item(self, r):
        return {
            'file_path': r[0], 'captured_time': float(r[1] or 0),
            'last_modified': int(r[2] or 0), 'tag': r[3] or 'photo',
            'aesthetic_score': float(r[4] or 0.0),
            'basename': os.path.basename(r[0]) if r[0] else '',
            'location_info': {
                'latitude': r[5], 'longitude': r[6], 'city': r[7] or '',
                'province': r[8] or '', 'country_code': r[9] or ''},
            'auto_tags': [t for t in (r[10] or '').split(',') if t],
        }

    _ITEM_COLS = ('file_path, captured_time, last_modified, tag, aesthetic_score, '
                  'latitude, longitude, city, province, country, auto_tags')

    def get_photos_by_tag(self, tag: str, limit: int, offset: int,
                          locked_prefixes: list = None):
        """Paged listing of a single tag (e.g. documents view)."""
        lock_sql, lock_params = self._locked_clause(locked_prefixes)
        base = f"FROM photos WHERE tag = ?{lock_sql}"
        params = [tag] + lock_params
        with self._get_conn() as conn:
            total = conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT {self._ITEM_COLS} {base} ORDER BY captured_time DESC LIMIT ? OFFSET ?",
                params + [limit, offset]).fetchall()
        return [self._row_to_item(r) for r in rows], total

    def get_places_summary(self, locked_prefixes: list = None):
        """One row per (city, province): count, average GPS, newest file as
        cover. Bare file_path alongside MAX(captured_time) is SQLite's
        documented way to pick the column value from the max row."""
        lock_sql, lock_params = self._locked_clause(locked_prefixes)
        with self._get_conn() as conn:
            rows = conn.execute(f'''
                SELECT city, province, COUNT(*),
                       AVG(latitude), AVG(longitude),
                       MAX(captured_time), file_path
                FROM photos
                WHERE tag NOT IN ('document','screenshot','trash','error')
                  AND (city != '' OR province != ''){lock_sql}
                GROUP BY city, province
                ORDER BY COUNT(*) DESC''', lock_params).fetchall()
        result = []
        for city, province, count, lat, lon, _t, cover in rows:
            name = f"{city}, {province}" if city and province else (city or province)
            result.append({
                'name': name, 'count': count,
                'cover': {'file_path': cover or '',
                          'basename': os.path.basename(cover) if cover else ''},
                'latitude': lat, 'longitude': lon,
                'province': province, 'city': city, 'items': [],
            })
        return result

    def get_map_points(self, locked_prefixes: list = None):
        lock_sql, lock_params = self._locked_clause(locked_prefixes)
        with self._get_conn() as conn:
            rows = conn.execute(f'''
                SELECT file_path, latitude, longitude, tag FROM photos
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                  AND tag NOT IN ('document','screenshot','trash','error'){lock_sql}''',
                lock_params).fetchall()
        return [{'file_path': r[0], 'basename': os.path.basename(r[0]),
                 'latitude': r[1], 'longitude': r[2], 'tag': r[3]} for r in rows]

    def get_photos_by_place(self, name: str, locked_prefixes: list = None):
        """Photos for a place page. Accepts 'City, Province' pairs or a
        single name matching either column."""
        parts = name.split(', ')
        lock_sql, lock_params = self._locked_clause(locked_prefixes)
        if len(parts) == 2:
            where, params = "city = ? AND province = ?", [parts[0], parts[1]]
        else:
            where, params = "(city = ? OR province = ?)", [name, name]
        with self._get_conn() as conn:
            rows = conn.execute(f'''
                SELECT {self._ITEM_COLS} FROM photos
                WHERE {where} AND tag NOT IN ('document','screenshot','trash','error'){lock_sql}
                ORDER BY captured_time DESC''', params + lock_params).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_on_this_day(self, month: int, day: int, locked_prefixes: list = None):
        lock_sql, lock_params = self._locked_clause(locked_prefixes)
        md = f"{month:02d}-{day:02d}"
        with self._get_conn() as conn:
            rows = conn.execute(f'''
                SELECT {self._ITEM_COLS} FROM photos
                WHERE captured_time > 0
                  AND strftime('%m-%d', captured_time, 'unixepoch', 'localtime') = ?
                  AND tag NOT IN ('document','screenshot','trash','error'){lock_sql}
                ORDER BY captured_time DESC''', [md] + lock_params).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_auto_tag_counts(self, locked_prefixes: list = None):
        """{tag: count} across visible photos. Only the auto_tags column is
        read; splitting stays in Python because tags are stored CSV."""
        lock_sql, lock_params = self._locked_clause(locked_prefixes)
        counts = {}
        with self._get_conn() as conn:
            for (csv,) in conn.execute(f'''
                    SELECT auto_tags FROM photos
                    WHERE auto_tags != ''
                      AND tag NOT IN ('document','screenshot','trash','error'){lock_sql}''',
                    lock_params):
                for t in csv.split(','):
                    if t:
                        counts[t] = counts.get(t, 0) + 1
        return counts

    def get_photos_by_auto_tag(self, tag: str, locked_prefixes: list = None):
        """Exact auto-tag membership via padded-CSV match — avoids the
        substring collisions a plain LIKE '%tag%' would cause."""
        lock_sql, lock_params = self._locked_clause(locked_prefixes)
        needle = f"%,{tag},%"
        with self._get_conn() as conn:
            rows = conn.execute(f'''
                SELECT {self._ITEM_COLS} FROM photos
                WHERE (',' || auto_tags || ',') LIKE ?
                  AND tag NOT IN ('document','screenshot','trash','error'){lock_sql}
                ORDER BY captured_time DESC''', [needle] + lock_params).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_photo_times(self, tags: tuple = ('photo', 'video'),
                        locked_prefixes: list = None):
        """Slim (file_path, captured_time) stream ordered by time, for the
        best-shots burst detector — two columns instead of full metadata."""
        ph = ','.join('?' * len(tags))
        lock_sql, lock_params = self._locked_clause(locked_prefixes)
        with self._get_conn() as conn:
            rows = conn.execute(f'''
                SELECT file_path, captured_time, aesthetic_score FROM photos
                WHERE tag IN ({ph}){lock_sql}
                ORDER BY captured_time ASC''',
                list(tags) + lock_params).fetchall()
        return [{'file_path': r[0], 'captured_time': float(r[1] or 0),
                 'aesthetic_score': float(r[2] or 0.0)} for r in rows]

    def count_photos_under_prefix(self, prefix: str) -> int:
        norm = self.norm_path(prefix).rstrip('/') + '/'
        esc = norm.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        with self._get_conn() as conn:
            return conn.execute('''
                SELECT COUNT(*) FROM photos
                WHERE file_path LIKE ? ESCAPE '\\'
                  AND tag NOT IN ('document','screenshot','trash','error')''',
                (esc,)).fetchone()[0]

    def get_photos_under_prefix(self, prefix: str):
        """Visible photos below a folder — the browse view's working set,
        instead of scanning the whole library."""
        norm = self.norm_path(prefix).rstrip('/') + '/'
        esc = norm.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        with self._get_conn() as conn:
            rows = conn.execute(f'''
                SELECT {self._ITEM_COLS} FROM photos
                WHERE file_path LIKE ? ESCAPE '\\'
                  AND tag NOT IN ('document','screenshot','trash','error')
                ORDER BY captured_time DESC''', (esc,)).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_random_photos(self, n: int, locked_prefixes: list = None):
        lock_sql, lock_params = self._locked_clause(locked_prefixes)
        with self._get_conn() as conn:
            rows = conn.execute(f'''
                SELECT {self._ITEM_COLS} FROM photos
                WHERE tag = 'photo'{lock_sql}
                ORDER BY RANDOM() LIMIT ?''', lock_params + [n]).fetchall()
        return [self._row_to_item(r) for r in rows]

    def get_photo_sync_states(self):
        """{file_path: last_modified} for the sync diff — replaces paging
        the entire Chroma collection through Python."""
        with self._get_conn() as conn:
            return {r[0]: int(r[1] or 0) for r in
                    conn.execute("SELECT file_path, last_modified FROM photos")}
