"""
Global state management and lazy-initialization for core services.

Provides thread-safe singletons for VisionModel, VectorDB, SQLiteStore,
and the AI model client factory.
"""
import os
import sys
import threading
import json
from typing import Optional, List

# --- Path Setup (must happen before core imports) ---
if getattr(sys, 'frozen', False):
    app_base = os.path.dirname(sys.executable)
    src_dir = app_base
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(current_dir)

if src_dir not in sys.path:
    sys.path.append(src_dir)

from core.paths import get_models_dir, get_db_dir

# Ensure models are cached locally
os.environ['HF_HOME'] = get_models_dir()
os.environ['SENTENCE_TRANSFORMERS_HOME'] = get_models_dir()


# ---------------------------------------------------------------------------
# Global State
# ---------------------------------------------------------------------------
class GlobalState:
    """Holds cached references to heavy-weight singletons and data caches."""
    model = None              # VisionModel
    vector_db = None          # VectorDB
    store = None              # SQLiteStore
    progress = None           # IndexingProgress (set in system routes)
    timeline_cache: Optional[List[dict]] = None
    places_cache: Optional[List[dict]] = None
    map_data_cache: Optional[List[dict]] = None
    on_this_day_cache: Optional[List[dict]] = None
    people_cache: Optional[List[dict]] = None
    tags_cache: Optional[List[dict]] = None


state = GlobalState()
_init_lock = threading.Lock()

# Interactive-inference gate: at most 2 concurrent encode calls from the
# request path (search/upload). Indexing runs on the TaskRunner worker and
# is unaffected; this only prevents a burst of parallel searches from
# spiking model memory.
encode_gate = threading.Semaphore(2)


# ---------------------------------------------------------------------------
# Lazy Initializers
# ---------------------------------------------------------------------------
def get_store():
    """Return the SQLiteStore singleton (thread-safe lazy init)."""
    if state.store is None:
        with _init_lock:
            if state.store is None:
                from database.sqlite_store import SQLiteStore
                db_file = os.path.join(get_db_dir(), 'history.db')
                state.store = SQLiteStore(db_path=db_file)
    return state.store


def get_db():
    """Return the VectorDB singleton (thread-safe lazy init)."""
    store = get_store()
    default_db = os.path.join(get_db_dir(), "search_v2.db")
    db_path = store.get_config("db_path", default_db)

    # Override legacy relative paths
    if db_path in ("./search.db", "d:/project/find/search_v2.db"):
        db_path = default_db

    if state.vector_db is None:
        with _init_lock:
            if state.vector_db is None:
                from database.vector_db import VectorDB
                print(f"[DEBUG] Initializing VectorDB with path: {db_path}")
                state.vector_db = VectorDB(db_path)
                # P1a: metadata writes are mirrored into the SQLite photos
                # table; reads migrate route-by-route to SQL queries.
                state.vector_db.metadata_sink = store
                from core.migrate import maybe_migrate
                maybe_migrate(state.vector_db, store)
    return state.vector_db


def get_model():
    """Return the VisionModel singleton (thread-safe lazy init)."""
    if state.model is None:
        with _init_lock:
            if state.model is None:
                from core.models import VisionModel
                state.model = VisionModel()
    return state.model


def get_sync_manager():
    """Create a new SyncManager (not a singleton – it's lightweight)."""
    from core.sync import SyncManager
    return SyncManager(get_db(), get_model(), get_store())


def invalidate_all_caches():
    """Clear every server-side data cache."""
    state.timeline_cache = None
    state.places_cache = None
    state.map_data_cache = None
    state.on_this_day_cache = None
    state.people_cache = None
    state.tags_cache = None


# ---------------------------------------------------------------------------
# AI Model Client Factory
# ---------------------------------------------------------------------------
def get_model_client(module_key: str, store=None):
    """
    Resolves the appropriate generator client for a given module
    (e.g. 'travel_prompt', 'travel_image', 'search_ai') based on the
    configuration (API Sources & Module Assignments).
    """
    from core.generator import (
        MockGenerator, NanoBananaGenerator, OpenAIGenerator,
        GeminiGenerator, GrsAIChatGenerator, AntiGravityGenerator,
    )

    if store is None:
        store = get_store()

    config = store.get_all_config()

    def parse_json_config(key, default):
        val = config.get(key)
        if not val:
            return default
        try:
            return json.loads(val)
        except Exception as e:
            print(f"[Config] Parse Error for {key}: {e}")
            return default

    api_sources = parse_json_config("api_sources", [])
    assignments = parse_json_config("module_assignments", {})

    # Legacy support
    legacy_key = config.get("api_key", "")
    legacy_model = config.get("model_name", "nano-banana")

    # Determine target source & model
    assignment = assignments.get(module_key)
    target_api_key = legacy_key
    target_model_name = legacy_model
    target_api_url = None
    source = None

    if assignment:
        source_id = assignment.get("sourceId")
        assigned_model = assignment.get("model")
        source = next((s for s in api_sources if s.get("id") == source_id), None)
        if source:
            target_api_key = source.get("apiKey", "")
            target_api_url = source.get("apiUrl")
        if assigned_model:
            target_model_name = assigned_model

    print(f"[{module_key}] using Source Key: "
          f"{'***' + target_api_key[-4:] if target_api_key else 'None'}, "
          f"Model: {target_model_name}")

    # Instantiate generator
    if target_api_url and (
        "8045" in target_api_url
        or "反重力" in (source.get("name", "") if source else "")
    ):
        return AntiGravityGenerator(
            api_key=target_api_key, model=target_model_name, api_url=target_api_url
        )

    mn = target_model_name.lower()
    if "mock" in mn:
        return MockGenerator()
    if "nano" in mn or "banana" in mn:
        return NanoBananaGenerator(api_key=target_api_key, model=target_model_name)
    if "gemini-3" in mn and "flash" in mn:
        return GrsAIChatGenerator(api_key=target_api_key, model=target_model_name)
    if "gemini" in mn:
        return GeminiGenerator(api_key=target_api_key, model=target_model_name)
    if "gpt" in mn or "dall" in mn or "o1" in mn:
        return OpenAIGenerator(api_key=target_api_key, model=target_model_name)

    # Default fallback
    return NanoBananaGenerator(api_key=target_api_key, model=target_model_name)
