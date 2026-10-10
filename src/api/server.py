"""
Deep Photo — FastAPI Application Entry Point

This is the slim application bootstrap. All route handlers live in
``api.routes.*`` sub-modules. Shared state / initializers are in
``api.state``, Pydantic models in ``api.models``, and utilities in
``api.helpers``.
"""
import os
import sys
import uvicorn

# ---------------------------------------------------------------------------
# Path Setup — must run before any relative import
# ---------------------------------------------------------------------------
if getattr(sys, 'frozen', False):
    app_base = os.path.dirname(sys.executable)
    src_dir = app_base
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(current_dir)

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Hugging-Face mirror (China)
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('NO_ALBUMENTATIONS_UPDATE', '1')

# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

from core.logging_setup import setup as _setup_logging

import logging
logger = logging.getLogger(__name__)
_setup_logging()

def _preheat_model():
    """Load AI models in the background right after startup (config key
    'preheat_model', default on). First search previously paid the full
    30-60s model load; with preheat it is warm by the time the user
    finishes typing. Runs on a daemon thread so startup is not blocked."""
    import threading

    def _load():
        try:
            from api.state import get_store, get_model
            store = get_store()
            enabled = str(store.get_config("preheat_model", "true")).lower()
            if enabled in ("false", "0", "off"):
                logger.info("[Preheat] disabled by config")
                return
            logger.info("[Preheat] loading AI models in background...")
            get_model()
            logger.info("[Preheat] models ready")
        except Exception as e:
            # Never let preheat failures affect the server; lazy loading
            # remains the fallback on first use.
            logger.warning(f"[Preheat] skipped: {e}")

    threading.Thread(target=_load, daemon=True, name="model-preheat").start()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup/shutdown hook. on_event() is deprecated in FastAPI."""
    _preheat_model()
    yield
    # SQLite runs in WAL mode, so recent commits sit in history.db-wal
    # until a checkpoint. Fold them back in on the way out, otherwise the
    # .db file alone is not a complete copy for backups or db-sync.
    try:
        from api.state import state
        if state.store is not None:
            state.store.checkpoint()
    except Exception as e:
        logger.warning(f"[Shutdown] WAL checkpoint skipped: {e}")


app = FastAPI(
    title="Deep Photo API",
    version="2.0.0",
    description="Privacy-first local AI photo management and search engine.",
    lifespan=lifespan,
)

# CORS — allow all origins for local desktop use

app.add_middleware(
    CORSMiddleware,
    # Only the Vite dev server needs CORS; the packaged desktop build is
    # served same-origin by this backend.  A wildcard here combined with a
    # localhost API allows any web page the user visits to read local files.
    # LAN access (phone/PWA) is opt-in: enabling it widens the origin
    # allowlist to private-network hosts. Default stays localhost-only —
    # a wildcard here on a localhost API is exactly the hole the
    # security pass closed.
    allow_origin_regex=(
        r"^http://(localhost|127\.0\.0\.1|10\.[\d.]+|192\.168\.[\d.]+|172\.(1[6-9]|2\d|3[01])\.[\d.]+)(:\d+)?$"
        if os.environ.get("DEEPPHOTO_LAN") == "1" else None
    ),
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1024)

from api.errors import register_handlers
register_handlers(app)

# ---------------------------------------------------------------------------
# Register All Route Modules
# ---------------------------------------------------------------------------
from api.routes import all_routers

# Every API route lives under /api. The frontend's page routes (/timeline,
# /people, /travel, ...) used to share paths with API routes of the same
# name, so reloading such a page in the packaged app returned JSON (and in
# dev, the Vite proxy forwarded the page itself to the API: 404). With one
# prefix the two namespaces can never collide, and the dev proxy, the
# service worker and the SPA fallback below all key off a single rule.
API_PREFIX = "/api"

for router in all_routers:
    app.include_router(router, prefix=API_PREFIX)


@app.get(API_PREFIX + "/version_check")
@app.get("/version_check", include_in_schema=False)  # start.bat / older launchers
async def version_check():
    # App.vue polls this until {status: "READY"} before entering the UI, and
    # it must be registered before the SPA catch-all below or it would be
    # answered with index.html.
    return {"status": "READY"}


# ---------------------------------------------------------------------------
# Serve Frontend (Vue 3 SPA)
# ---------------------------------------------------------------------------
from core.paths import get_internal_data_dir

dist_path = os.path.join(get_internal_data_dir(), 'web', 'dist')

if os.path.exists(dist_path):
    assets_path = os.path.join(dist_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    dist_root = os.path.realpath(dist_path)

    @app.get("/{full_path:path}")
    async def serve_vue_app(full_path: str):
        # An unknown API path is an API 404, not the app shell.
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        # Real files at the dist root (sw.js, manifest, icons, china.json).
        # These used to be mounted one StaticFiles app per file with
        # html=True, which strips the filename and answers index.html — so
        # the packaged app served HTML for china.json and the service worker.
        if full_path:
            candidate = os.path.realpath(os.path.join(dist_root, full_path))
            if (os.path.commonpath([candidate, dist_root]) == dist_root
                    and os.path.isfile(candidate)):
                return FileResponse(candidate)
        index_file = os.path.join(dist_path, "index.html")
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
        return {"error": "Frontend not found"}

# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Loopback unless LAN access is explicitly enabled — same rule as
    # main_desktop.py. start.bat runs this entry point, and it used to
    # expose every photo to the whole network by default.
    host = "0.0.0.0" if os.environ.get("DEEPPHOTO_LAN") == "1" else "127.0.0.1"
    uvicorn.run(app, host=host, port=8001)
