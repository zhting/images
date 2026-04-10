"""
Route registration centre.

Each sub-module exposes a FastAPI ``APIRouter``.  This module collects them
all so the main ``server.py`` can register them with a single call.
"""
from fastapi import APIRouter

from .search import router as search_router
from .timeline import router as timeline_router
from .files import router as files_router
from .organize import router as organize_router
from .people import router as people_router
from .privacy import router as privacy_router
from .config import router as config_router
from .system import router as system_router
from .travel import router as travel_router
from .trash import router as trash_router

all_routers: list[APIRouter] = [
    search_router,
    timeline_router,
    files_router,
    organize_router,
    people_router,
    privacy_router,
    config_router,
    system_router,
    travel_router,
    trash_router,
]
