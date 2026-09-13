"""One-time migration of photo metadata from ChromaDB into the SQLite
``photos`` table (P1a data-layer refactor).

Idempotent: upserts by file_path, safe to run repeatedly.  Video
segment entries (ids like ``path#N``) collapse into one row per file
because they share the same file_path metadata.

``maybe_migrate`` is the startup guard: it runs the migration exactly
once — when the photos table is empty while the vector collection is
not (i.e. an existing library upgrading to this version).
"""
import json
import logging
import time

logger = logging.getLogger(__name__)

BATCH = 1000


def migrate_photos_metadata(db, store, progress=None) -> int:
    """Copy all metadata rows from *db* (VectorDB) into *store* (SQLiteStore).

    Returns the number of migrated rows.
    """
    files = db.get_all_files_with_time(include_embeddings=False) or []
    total = len(files)
    migrated = 0
    batch = []
    for f in files:
        batch.append(f)  # shape already matches upsert_photos expectations
        if len(batch) >= BATCH:
            migrated += store.upsert_photos(batch)
            batch = []
            if progress:
                progress(migrated, total)
    if batch:
        migrated += store.upsert_photos(batch)
    if progress:
        progress(migrated, total)
    return migrated


STATUS_KEY = "migration_status"


def _record(store, state: str, **extra):
    """Persist the migration outcome so the UI can surface a failure.

    Without this a failed migration only left one log line, and the app
    silently served every request from the slow legacy full-scan paths
    forever — a degradation nobody could see.
    """
    payload = {"state": state, "at": int(time.time()), **extra}
    try:
        store.set_config(STATUS_KEY, json.dumps(payload))
    except Exception as e:
        logger.error(f"[Migrate] could not record status: {e}")
    return payload


def get_status(store) -> dict:
    """Last recorded migration outcome.

    ``state`` is one of:
      ok        — migrated, or never needed (SQL paths active)
      failed    — migration raised; the app is on the legacy scan paths
      pending   — there is Chroma data to migrate that has not been yet
    """
    try:
        raw = store.get_config(STATUS_KEY)
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"[Migrate] unreadable status: {e}")
    return {"state": "ok", "at": 0, "note": "no migration recorded"}


def maybe_migrate(db, store) -> bool:
    """Run the migration if (and only if) it has never run before.

    Returns True if a migration was performed.
    """
    try:
        if store.has_photos():
            _record(store, "ok", reason="photos table already populated")
            return False
        if db.count() == 0:
            _record(store, "ok", reason="nothing indexed yet")
            return False
        logger.info("[Migrate] photos table empty but vector DB has data — "
                    "migrating metadata to SQLite (one-time)...")
        n = migrate_photos_metadata(db, store)
        logger.info(f"[Migrate] done: {n} rows migrated to photos table.")
        _record(store, "ok", migrated=n)
        return True
    except Exception as e:
        # Migration must never block startup; legacy read paths still work,
        # but the degradation is now recorded rather than silent.
        logger.error(f"[Migrate] failed, falling back to legacy scan paths: {e}")
        _record(store, "failed", error=str(e))
        return False
