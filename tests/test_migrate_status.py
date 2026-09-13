"""The one-time metadata migration must report failure, not swallow it.

A failed migration leaves the app on the legacy full-scan read paths.
That is correct but much slower, and it used to be visible only as a
single line in the log file — so these tests pin the recorded status
that the settings page surfaces.
"""
from core.migrate import STATUS_KEY, get_status, maybe_migrate


class EmptyDB:
    def count(self):
        return 0


class PopulatedDB:
    def __init__(self, rows):
        self._rows = rows

    def count(self):
        return len(self._rows)

    def get_all_files_with_time(self, include_embeddings=False):
        return self._rows


class BrokenDB:
    def count(self):
        return 42

    def get_all_files_with_time(self, include_embeddings=False):
        raise RuntimeError("chroma collection corrupt")


def test_defaults_to_ok_when_nothing_was_ever_recorded(sqlite_store):
    assert get_status(sqlite_store)["state"] == "ok"


def test_nothing_indexed_records_ok(sqlite_store):
    assert maybe_migrate(EmptyDB(), sqlite_store) is False
    assert get_status(sqlite_store)["state"] == "ok"


def test_successful_migration_records_the_row_count(sqlite_store):
    rows = [{"file_path": "/a.jpg", "captured_time": 1},
            {"file_path": "/b.jpg", "captured_time": 2}]

    assert maybe_migrate(PopulatedDB(rows), sqlite_store) is True

    status = get_status(sqlite_store)
    assert status["state"] == "ok"
    assert status["migrated"] == 2
    assert sqlite_store.count_photos() == 2


def test_failure_is_recorded_with_the_reason(sqlite_store):
    assert maybe_migrate(BrokenDB(), sqlite_store) is False

    status = get_status(sqlite_store)
    assert status["state"] == "failed"
    assert "corrupt" in status["error"]


def test_failure_does_not_raise_into_startup(sqlite_store):
    # Startup must survive a broken migration — the legacy paths still work.
    maybe_migrate(BrokenDB(), sqlite_store)


def test_a_later_successful_run_clears_the_failure(sqlite_store):
    maybe_migrate(BrokenDB(), sqlite_store)
    assert get_status(sqlite_store)["state"] == "failed"

    maybe_migrate(PopulatedDB([{"file_path": "/a.jpg"}]), sqlite_store)
    assert get_status(sqlite_store)["state"] == "ok"


def test_unreadable_status_degrades_to_ok(sqlite_store):
    sqlite_store.set_config(STATUS_KEY, "{not json")
    assert get_status(sqlite_store)["state"] == "ok"


def test_index_status_endpoint_exposes_it(app_client, sqlite_store):
    maybe_migrate(BrokenDB(), sqlite_store)

    body = app_client.get("/index/status").json()
    assert body["migration"]["state"] == "failed"
