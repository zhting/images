# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

**Deep Photo (Local Vision Search v2.0)** - Privacy-first, AI-powered local photo organizer and search engine. Runs entirely offline using state-of-the-art open source models (SigLIP, Qwen2.5, InsightFace).

## Commands

### Backend
```bash
pip install -r requirements.txt
PYTHONPATH=src python -m api.server      # API server (port 8001)
```

### Frontend
```bash
cd web
npm install
npm run dev      # Development server (port 5173)
npm run build    # Production build
```

### Testing
```bash
pip install -r requirements-dev.txt
PYTHONPATH=src python -m pytest tests/ -v
```

### Quick Start
Run `start.bat` in the project root to start both backend and frontend.

## Architecture

```
Frontend (Vue 3 + TailwindCSS) <--API--> Backend (FastAPI)
                                                   |
                              +--------------------+--------------------+
                              |                    |                    |
                        Core Processors       VectorDB           SQLite
                        - VisionModel        (ChromaDB)        Store
                        - FaceProcessor
                        - LocationProcessor
                        - TagGenerator
                        - SyncManager
```

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `src/api/` | FastAPI app entry point (`server.py`) and shared modules |
| `src/api/state.py` | Global state, lazy initializers, AI model client factory |
| `src/api/models.py` | Pydantic request/response models |
| `src/api/helpers.py` | Shared utility functions |
| `src/api/routes/` | Modular API route handlers (search, timeline, files, etc.) |
| `src/core/` | Business logic: vision models, face processing, location, sync |
| `src/database/` | Data layer: ChromaDB vector store, SQLite metadata |
| `web/` | Vue 3 frontend application |
| `web/src/views/` | Page components (Timeline, Places, People, Tags, BestShots, OnThisDay) |
| `web/src/components/` | Reusable components (Search, Settings, etc.) |
| `tests/` | pytest test suite (unit + API integration) |
| `.github/workflows/` | CI/CD: test.yml (PR checks) + release.yml (tag deploy) |

## API Route Modules

| Module | Prefix / Endpoints | Description |
|--------|-------------------|-------------|
| `routes/search.py` | `/search/*`, `/generate` | Text, image, and AI-powered search |
| `routes/timeline.py` | `/timeline/*` | Photo timeline with burst detection |
| `routes/files.py` | `/files/thumbnail`, `/files/content`, `/files/browse_dir` | File serving & browsing |
| `routes/organize.py` | `/files/organize/places/*`, `/tags/*`, `/best_shots`, etc. | Photo organization features |
| `routes/people.py` | `/files/organize/people/*`, `/files/face/*` | Face recognition & clustering |
| `routes/privacy.py` | `/privacy/*` | Password management & folder locking |
| `routes/config.py` | `/config/*` | Settings & wishlist management |
| `routes/system.py` | `/index/*`, `/system/*` | Indexing, system info, filesystem |
| `routes/travel.py` | `/travel/*` | Travel postcard generation |
| `routes/trash.py` | `/files/trash/*` | Recycle bin operations |

## Technology Stack

- **Frontend**: Vue 3 (Composition API), Vue Router, TailwindCSS, Vite, Axios
- **Backend**: FastAPI, Python
- **Database**: ChromaDB (vector embeddings), SQLite (metadata)
- **AI Models**: Google SigLIP (vision), Qwen2.5 (translation), InsightFace (face recognition)
- **Testing**: pytest, httpx, FastAPI TestClient
- **CI/CD**: GitHub Actions

## Notes

- All AI processing happens locally - no cloud uploads
- Uses file watching (watchdog) for automatic indexing when photos are added
- Supports natural language search (e.g., "cat sleeping on sofa")
- Face clustering enables automatic people grouping
- AI model dependencies are mocked in tests — CI runs without GPU
