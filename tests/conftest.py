"""
Pytest fixtures for Deep Photo test suite.

Provides mock objects for VisionModel, VectorDB, and SQLiteStore
so tests can run without GPU or large model downloads.
"""
import os
import sys
import pytest
import tempfile

# Ensure src/ is on the Python path
src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


# ---------------------------------------------------------------------------
# Mock Classes
# ---------------------------------------------------------------------------
class MockVisionModel:
    """Lightweight mock for VisionModel — returns deterministic vectors."""
    device = "cpu"
    dim = 1152

    def encode(self, image):
        import numpy as np
        vec = np.random.rand(self.dim).astype("float32")
        return vec / (np.linalg.norm(vec) + 1e-9)

    def encode_text(self, text: str):
        import numpy as np
        vec = np.random.rand(self.dim).astype("float32")
        return vec / (np.linalg.norm(vec) + 1e-9)

    def predict_aesthetic_score(self, image):
        return 0.5

    def classify_type(self, image):
        return "photo"


class MockVectorDB:
    """In-memory stub that mimics VectorDB without ChromaDB."""
    def __init__(self):
        self._store = {}

    def search(self, embedding, top_k=10):
        return []

    def get_all_files(self):
        return self._store

    def get_all_files_with_time(self, include_embeddings=True):
        return []

    def get_stats(self):
        return {"total": len(self._store)}

    def get_timeline_dates_stats(self):
        return []

    def get_timeline_page(self, limit=50, offset=0):
        return None, 0

    def get_embeddings_for_files(self, paths):
        return {}

    def get_trash_files(self):
        return []

    def insert(self, *args, **kwargs):
        pass

    def delete_by_path(self, path):
        self._store.pop(path, None)

    def soft_delete_file(self, path):
        pass

    def restore_file(self, path):
        pass

    def reset_collection(self):
        self._store.clear()

    def update_location(self, path, info):
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_db_path(tmp_path):
    """Create a temporary path for SQLite database."""
    return str(tmp_path / "test_history.db")


@pytest.fixture
def sqlite_store(tmp_db_path):
    """Real SQLiteStore backed by a temp file."""
    from database.sqlite_store import SQLiteStore
    store = SQLiteStore(db_path=tmp_db_path)
    yield store
    # Close SQLite connection to release file lock (Windows compat)
    try:
        store._get_conn().close()
    except Exception:
        pass


@pytest.fixture
def mock_model():
    return MockVisionModel()


@pytest.fixture
def mock_db():
    return MockVectorDB()


@pytest.fixture
def app_client(sqlite_store, mock_model, mock_db):
    """
    FastAPI TestClient with all heavy dependencies mocked out.
    Directly injects mocks into the global state so that all route modules
    (which call get_store/get_db/get_model) receive the mocked objects.
    """
    from fastapi.testclient import TestClient
    from api.state import state

    # Inject mocks directly into global state (get_store/get_db/get_model
    # check state.store/state.vector_db/state.model first before init)
    old_store = state.store
    old_db = state.vector_db
    old_model = state.model

    state.store = sqlite_store
    state.vector_db = mock_db
    state.model = mock_model

    from api.server import app
    client = TestClient(app)
    yield client

    # Restore
    state.store = old_store
    state.vector_db = old_db
    state.model = old_model

