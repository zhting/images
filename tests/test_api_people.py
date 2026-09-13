"""People endpoint: clustering must not run on the request thread.

DBSCAN over a large library's face embeddings takes minutes. These tests
pin the async contract so it cannot regress back to an inline call.
"""
import time

import numpy as np
import pytest

from core.tasks import ACTIVE_STATES, runner


def _add_group(store, label, n=6, dim=64, jitter=0.01, seed=0):
    """Insert n near-identical face embeddings — one DBSCAN cluster."""
    rng = np.random.default_rng(seed)
    base = rng.normal(size=dim).astype("float32")
    base /= np.linalg.norm(base)
    for i in range(n):
        emb = base + rng.normal(scale=jitter, size=dim).astype("float32")
        emb /= np.linalg.norm(emb)
        store.add_face(f"/photos/{label}_{i}.jpg", emb, [0, 0, 10, 10])


def _drain(timeout=30.0):
    """Wait for the shared serial runner to go idle."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not any(t.state in ACTIVE_STATES for t in runner.tasks.values()):
            return True
        time.sleep(0.05)
    return False


@pytest.fixture(autouse=True)
def _clear_people_cache():
    from api.state import state
    state.people_cache = None
    yield
    state.people_cache = None
    _drain()


def test_no_faces_reports_nothing_to_cluster(app_client):
    body = app_client.get("/files/organize/people").json()

    assert body["items"] == []
    assert body["total"] == 0
    assert body["clustering"] is False
    assert body["task_id"] is None


def test_unclustered_faces_queue_a_task_instead_of_blocking(app_client, sqlite_store):
    _add_group(sqlite_store, "a", seed=1)
    assert sqlite_store.count_unclustered_faces() == 6

    started = time.time()
    body = app_client.get("/files/organize/people").json()
    elapsed = time.time() - started

    assert body["clustering"] is True
    assert body["task_id"], "response must carry a task id to poll"
    assert elapsed < 2.0, "clustering must not run inline on the request thread"


def test_background_pass_groups_the_faces(app_client, sqlite_store):
    _add_group(sqlite_store, "a", seed=1)
    _add_group(sqlite_store, "b", seed=2)

    app_client.get("/files/organize/people")
    assert _drain(), "clustering task did not finish"

    body = app_client.get("/files/organize/people").json()
    assert body["total"] == 2
    assert sorted(p["count"] for p in body["items"]) == [6, 6]
    assert sqlite_store.count_unclustered_faces() == 0


def test_concurrent_requests_share_one_clustering_task(app_client, sqlite_store):
    """Polls that arrive while a pass is running must join it, not queue more.

    The runner is serial, so occupying it with a blocking job makes the
    overlap deterministic instead of racing a fast DBSCAN over 6 faces.
    """
    import threading

    _add_group(sqlite_store, "a", seed=3)
    release = threading.Event()
    runner.submit("test_block", lambda t: release.wait(10))
    try:
        ids = {app_client.get("/files/organize/people").json()["task_id"]
               for _ in range(5)}
    finally:
        release.set()

    assert len(ids) == 1 and None not in ids, f"expected one shared task, got {ids}"


def test_empty_result_is_not_cached_as_final(app_client, sqlite_store):
    """A pass that produced nothing must not pin the view to 'no people'."""
    from api.state import state

    app_client.get("/files/organize/people")
    assert _drain()

    state.people_cache = []
    _add_group(sqlite_store, "late", seed=4)
    app_client.get("/files/organize/people")
    assert _drain()

    assert app_client.get("/files/organize/people").json()["total"] == 1
