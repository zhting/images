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

app = FastAPI(
    title="Deep Photo API",
    version="2.0.0",
    description="Privacy-first local AI photo management and search engine.",
)

# CORS — allow all origins for local desktop use
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
