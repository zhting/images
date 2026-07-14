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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from core.logging_setup import setup as _setup_logging

import logging
logger = logging.getLogger(__name__)
_setup_logging()

app = FastAPI(
    title="Deep Photo API",
    version="2.0.0",
    description="Privacy-first local AI photo management and search engine.",
)

# CORS — allow all origins for local desktop use

@app.on_event("startup")
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

for router in all_routers:
    app.include_router(router)

# ---------------------------------------------------------------------------
# Serve Frontend (Vue 3 SPA)
# ---------------------------------------------------------------------------
from core.paths import get_internal_data_dir

dist_path = os.path.join(get_internal_data_dir(), 'web', 'dist')

if os.path.exists(dist_path):
    assets_path = os.path.join(dist_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    # Static assets like favicon
    for f_name in os.listdir(dist_path):
        full_p = os.path.join(dist_path, f_name)
        if os.path.isfile(full_p) and f_name != "index.html":
            app.mount(f"/{f_name}", StaticFiles(directory=dist_path, html=True), name=f_name)

    @app.get("/{full_path:path}")
    async def serve_vue_app(full_path: str):
        index_file = os.path.join(dist_path, "index.html")
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
        return {"error": "Frontend not found"}

# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
