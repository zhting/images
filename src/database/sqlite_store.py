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

    def get_config(self, key: str) -> str:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM system_config WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row[0] if row else None

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
