"""One-time migration of photo metadata from ChromaDB into the SQLite
``photos`` table (P1a data-layer refactor).

Idempotent: upserts by file_path, safe to run repeatedly.  Video
segment entries (ids like ``path#N``) collapse into one row per file
because they share the same file_path metadata.

``maybe_migrate`` is the startup guard: it runs the migration exactly
once — when the photos table is empty while the vector collection is
not (i.e. an existing library upgrading to this version).
"""

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


def maybe_migrate(db, store) -> bool:
    """Run the migration if (and only if) it has never run before.

    Returns True if a migration was performed.
    """
    try:
        if store.count_photos() > 0:
            return False
        if db.count() == 0:
            return False
        print("[Migrate] photos table empty but vector DB has data — "
              "migrating metadata to SQLite (one-time)...")
        n = migrate_photos_metadata(db, store)
        print(f"[Migrate] done: {n} rows migrated to photos table.")
        return True
    except Exception as e:
        # Migration must never block startup; legacy read paths still work.
        print(f"[Migrate] skipped due to error: {e}")
        return False
