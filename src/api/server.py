from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import os
import sys
import shutil
import base64
import time
from datetime import datetime
from typing import List, Optional

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.append(src_dir)

from core.models import VisionModel
from database.vector_db import VectorDB
from database.sqlite_store import SQLiteStore
from core.face_processor import FaceProcessor
# We might need to move index_worker to a shared place or import it
# For now, let's just scaffold the app

app = FastAPI(title="Local Vision Search API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- State Management ---
class GlobalState:
    model: Optional[VisionModel] = None
    vector_db: Optional[VectorDB] = None
    store: Optional[SQLiteStore] = None
    progress: Optional['IndexingProgress'] = None

state = GlobalState()

def get_store():
    if state.store is None:
        state.store = SQLiteStore()
    return state.store

def get_db():
    store = get_store()
    db_path = store.get_config("db_path", "./search.db")
    if state.vector_db is None:
        state.vector_db = VectorDB(db_path)
    return state.vector_db

def get_model():
    if state.model is None:
        state.model = VisionModel() # This might be heavy on startup
    return state.model

# --- Models ---
class ConfigUpdate(BaseModel):
    key: str
    value: str

# from deep_translator import GoogleTranslator # Replaced by local
from PIL import Image
import io
import collections

# ... (Previous imports)

# --- Models ---
class TextSearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = None
    use_translation: bool = True

class SearchResultItem(BaseModel):
    file_path: str
    score: float
    basename: str
    timestamp: float = 0
    date_str: str = ""

from functools import lru_cache

from core.translator import translator as local_translator

@lru_cache(maxsize=128)
def cached_translate(text: str, target_lang: str = "Simplified Chinese") -> str:
    # Use local offline translator
    return local_translator.translate(text, target_lang=target_lang)

def is_ascii(s):
    return all(ord(c) < 128 for c in s)

# --- Routes ---

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "vision-search-api"}

@app.post("/search/image", response_model=List[SearchResultItem])
async def search_image(file: UploadFile = File(...), top_k: Optional[int] = None):
    try:
        model = get_model()
        db = get_db()
        store = get_store()
        
        limit = top_k if top_k is not None else int(store.get_config("top_k", 10))
        
        # Read image
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        # Encode
        embedding = model.encode(image)
        
        # Search
        results = db.search(embedding, top_k=limit)
        
        response = []
        if results and len(results) > 0:
            for res in results[0]:
                entity = res.get('entity', {})
                path = entity.get('file_path', res['id'])
                distance = res.get('distance', 0)
                score = 1 - distance
                
                # Filter low similarity
                if score < 0.1: continue
                
                # Get timestamp if available (from DB metadata or file system)
                # For now, let's keep it simple, client might need to fetch metadata separately 
                # or we include it here if available in VectorDB results.
                # VectorDB search results usually return 'metadatas'.
                
                response.append({
                    "file_path": path,
                    "score": score,
                    "basename": os.path.basename(path)
                })
        return response
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search/text")
def search_text(request: TextSearchRequest):
    try:
        model = get_model()
        db = get_db()
        store = get_store()
        
        # Resolve top_k: use request value if present, else config, else 10
        top_k = request.top_k if request.top_k is not None else int(store.get_config("top_k", 10))
        print(f"[DEBUG] Search top_k resolved: request={request.top_k}, config={store.get_config('top_k')}, final={top_k}")
        
        start_total = time.time()
        
        query_text = request.query
        
        t0 = time.time()
        # Optimization: Skip translation if pure ASCII (likely English)
        if request.use_translation and not is_ascii(query_text):
             try:
                 translated = cached_translate(query_text, target_lang="English")
                 print(f"Translating '{query_text}' -> '{translated}'")
                 if translated and len(translated) > 0:
                     query_text = translated
             except Exception as e:
                 print(f"Translation failed: {e}")
                 pass # Fallback to original
        t_translate = time.time() - t0
        
        t0 = time.time()
        embedding = model.encode_text(query_text)
        t_encode = time.time() - t0
        
        t0 = time.time()
        results = db.search(embedding, top_k=top_k)
        t_search = time.time() - t0
        
        print(f"[Search Perf] Trans: {t_translate:.4f}s | Encode: {t_encode:.4f}s | DB: {t_search:.4f}s | Total: {time.time() - start_total:.4f}s")
        
        items = []
        if results and len(results) > 0:
            for res in results[0]:
                entity = res.get('entity', {})
                path = entity.get('file_path', res['id'])
                distance = res.get('distance', 0)
                score = 1 - distance # Convert cosine distance to similarity
                
                if score < 0.1: continue
                
                items.append({
                    "file_path": path,
                    "score": score,
                    "basename": os.path.basename(path)
                })
        
        # Return object wrapper
        return {
            "results": items,
            "translated_query": query_text if query_text != request.query else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/timeline")
def get_timeline():
    print("DEBUG: Enter get_timeline")
    try:
        db = get_db()
        all_files = db.get_all_files_with_time()
        
        # Sanitize data to prevent numpy ambiguity errors during sort
        # Ensure primitive types
        for f in all_files:
            # captured_time
            ct = f.get('captured_time', 0)
            if hasattr(ct, 'item'): ct = ct.item() # numpy scalar
            elif hasattr(ct, '__len__') and not isinstance(ct, str) and len(ct) > 0: ct = ct[0] # array
            f['captured_time'] = float(ct)
            
            # aesthetic_score
            sc = f.get('aesthetic_score', 0.0)
            if hasattr(sc, 'item'): sc = sc.item()
            elif hasattr(sc, '__len__') and not isinstance(sc, str) and len(sc) > 0: sc = sc[0]
            f['aesthetic_score'] = float(sc)
                
        all_files.sort(key=lambda x: x['captured_time'], reverse=True)
        
        # Filter out documents/screenshots
        photos = [f for f in all_files if f.get('tag') not in ['document', 'screenshot']]
        
        # Sort by time for grouping
        photos.sort(key=lambda x: x['captured_time'], reverse=True) # Newest first
        
        # Group bursts (reverse logic of BestShots: here we scan formatted list)
        # Actually simplest is to scan sorted list, if diff < 2.0s join group.
        
        # Helper for cosine similarity
        def cosine_similarity(v1, v2):
            if v1 is None or v2 is None or len(v1) == 0 or len(v2) == 0: return 0.0
            dot = sum(a*b for a,b in zip(v1, v2))
            norm1 = sum(a*a for a in v1) ** 0.5
            norm2 = sum(b*b for b in v2) ** 0.5
            if norm1 == 0 or norm2 == 0: return 0.0
            return dot / (norm1 * norm2)

        grouped_results = []
        if not photos:
            return []
            
        current_group = [photos[0]]
        
        for i in range(1, len(photos)):
            curr = photos[i]
            prev = photos[i-1] 
            
            # Ensure float
            t_curr = float(curr.get('captured_time', 0))
            t_prev = float(prev.get('captured_time', 0))
            time_diff = abs(t_curr - t_prev)
            
            is_burst = False
            if time_diff < 5.0:
                sim = cosine_similarity(curr.get('embedding'), prev.get('embedding'))
                threshold = 0.85
                if time_diff > 2.0: threshold = 0.92
                
                if sim >= threshold:
                    is_burst = True
            
            if is_burst:
                current_group.append(curr)
            else:
                # Process current_group
                # best_shot = max(current_group, key=lambda x: x.get('aesthetic_score', 0.0))
                # Safe max with float conversion
                best_shot = current_group[0]
                max_score = -1.0
                for p in current_group:
                    s = float(p.get('aesthetic_score', 0.0))
                    if s > max_score:
                        max_score = s
                        best_shot = p
                
                best_shot['similar_count'] = len(current_group) - 1
                best_shot['basename'] = os.path.basename(best_shot['file_path'])
                
                # Remove embedding before sending to frontend to save bandwidth
                if 'embedding' in best_shot: del best_shot['embedding']
                
                grouped_results.append(best_shot)
                current_group = [curr]
                
        # Last group
        if current_group:
            best_shot = current_group[0]
            max_score = -1.0
            for p in current_group:
                s = float(p.get('aesthetic_score', 0.0))
                if s > max_score:
                    max_score = s
                    best_shot = p
                    
            best_shot['similar_count'] = len(current_group) - 1
            best_shot['basename'] = os.path.basename(best_shot['file_path'])
            if 'embedding' in best_shot: del best_shot['embedding']
            grouped_results.append(best_shot)
            
        return grouped_results
        
    except Exception as e:
        import traceback
        import sys
        traceback.print_exc()
        print(f"Timeline Error: {e}", file=sys.stderr)
        sys.stderr.flush()
        raise HTTPException(status_code=500, detail=str(e))

# ... (imports)
from core.generator import MockGenerator, NanoBananaGenerator, OpenAIGenerator

class AISearchRequest(BaseModel):
    prompt: str
    provider: str = "config" # config, mock, openai, nano-banana
    top_k: Optional[int] = None

@app.post("/search/ai", response_model=List[SearchResultItem])
async def search_ai(req: AISearchRequest):
    try:
        store = get_store()
        model = get_model()
        db = get_db()
        
        # Determine provider
        provider = req.provider
        if provider == "config":
             # Logic to pick from config
             api_key = store.get_config("api_key", "")
             model_name = store.get_config("model_name", "nano-banana")
             # Simple heuristic or explicit config needed. For now default to nano-banana if key exists, else mock
             if api_key and len(api_key) > 5:
                  provider = "nano-banana" # Default to nano-banana for now if key present
             else:
                  provider = "mock"

        # Instantiate Generator
        gen = None
        if provider == "mock":
             gen = MockGenerator()
        elif provider == "openai":
             gen = OpenAIGenerator(api_key=store.get_config("api_key"))
        elif provider == "nano-banana":
             gen = NanoBananaGenerator(api_key=store.get_config("api_key", ""), model=store.get_config("model_name", "nano-banana"))
        else:
             gen = MockGenerator()

        # Generate
        print(f"Generating image with {provider} for prompt: {req.prompt}")
        generated_img = gen.generate(req.prompt)
        
        # Encode
        vector = model.encode(generated_img)
        
        # Search
        results = db.search(vector, top_k=req.top_k)
        
        # Format
        formatted = []
        if results and len(results) > 0:
            for res in results[0]:
                path = res['entity'].get('file_path')  
                # If path isn't in entity (some chroma versions), check id
                if not path: path = res['id']
                
                distance = res.get('distance', 0)
                score = 1 - distance

                if score < 0.1: continue

                formatted.append({
                    "file_path": path,
                    "score": score, # Chroma returns distance usually
                    "basename": os.path.basename(path)
                })
        return formatted

    except Exception as e:
        print(f"AI Search Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class GenerateRequest(BaseModel):
    prompt: str
    provider: str = "config"

@app.post("/generate")
async def generate_image_endpoint(req: GenerateRequest):
    try:
        store = get_store()
        provider = req.provider
        if provider == "config":
             api_key = store.get_config("api_key", "")
             model_name = store.get_config("model_name", "nano-banana")
             if api_key and len(api_key) > 5:
                  provider = "nano-banana"
             else:
                  provider = "mock"

        gen = None
        if provider == "mock":
             gen = MockGenerator()
        elif provider == "openai":
             gen = OpenAIGenerator(api_key=store.get_config("api_key"))
        elif provider == "nano-banana":
             gen = NanoBananaGenerator(api_key=store.get_config("api_key", ""), model=store.get_config("model_name", "nano-banana"))
        else:
             gen = MockGenerator()

        print(f"Generating image with {provider} for prompt: {req.prompt}")
        img = gen.generate(req.prompt)
        
        # Convert to base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return {"image": f"data:image/png;base64,{img_str}"}

    except Exception as e:
        print(f"Generate Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Serving local files (SECURITY WARNING: In production, use a proper file server or signed URLs. For local app, serving drive root or specific folder is tricky via StaticFiles if paths are absolute window paths).
# We need a custom endpoint to serve files by absolute path.
from fastapi.responses import FileResponse

# ... (existing imports)
from core.sync import SyncManager
from database.sqlite_store import SQLiteStore

# ... (existing state)

def get_sync_manager():
    model = get_model()
    db = get_db()
    store = get_store()
    return SyncManager(db, model, store)

# ... (existing routes)

# --- Settings & Indexing ---

@app.get("/config/paths")
def get_asset_paths():
    store = get_store()
    return store.get_asset_paths()

class PathRequest(BaseModel):
    path: str

@app.post("/config/paths")
def add_asset_path(req: PathRequest):
    store = get_store()
    store.add_asset_path(req.path)
    return {"status": "added", "path": req.path, "current_paths": store.get_asset_paths()}

@app.delete("/config/paths")
def remove_asset_path(req: PathRequest):
    store = get_store()
    store.remove_asset_path(req.path)
    return {"status": "removed", "path": req.path, "current_paths": store.get_asset_paths()}

class IndexRunRequest(BaseModel):
    force: bool = False

# --- Indexing State ---
class IndexingProgress(BaseModel):
    state: str = "idle" # idle, scanning, indexing, completed, error
    phase: str = "" # "Scanning files...", "Processing images..."
    current: int = 0
    total: int = 0
    current_file: str = ""
    scan_result: Optional[dict] = None # {to_add: [], ...}
    start_time: float = 0
    last_updated: str = ""
    stop_requested: bool = False

state.progress = IndexingProgress()

@app.get("/index/scan")
def scan_indexing_files(background_tasks: BackgroundTasks):
    if state.progress.state in ["scanning", "indexing"]:
        raise HTTPException(status_code=400, detail="Indexing already in progress")
    
    def _do_scan():
        try:
            state.progress.state = "scanning"
            state.progress.phase = "正在扫描文件变动..."
            manager = get_sync_manager()
            diff = manager.scan_files()
            
            # Estimate time (approx 0.1s per image with SigLIP? Maybe slower depending on CPU/GPU)
            # Actually with SigLIP 400M on CPU it might be 0.5s-1s per image.
            # SigLIP is heavy.
            count = len(diff['to_add']) + len(diff['to_update']) + len(diff['to_delete'])
            
            state.progress.scan_result = {
                "added": len(diff['to_add']),
                "updated": len(diff['to_update']),
                "deleted": len(diff['to_delete']),
                "total_ops": count,
                "diff_obj": diff # Store internal diff to run index later? Or re-scan?
                # Storing diff in memory is risky if large, but list of paths is fine.
            }
            state.progress.state = "scanned"
            state.progress.phase = f"扫描完成. 发现 {count} 个变动."
        except Exception as e:
            state.progress.state = "error"
            print(f"Scan failed: {e}")

    background_tasks.add_task(_do_scan)
    return {"status": "scan_started"}

@app.post("/index/stop")
def stop_indexing():
    if state.progress.state not in ["indexing", "scanning"]:
        return {"status": "ignored", "message": "Not running"}
    
    state.progress.stop_requested = True
    state.progress.phase = "正在停止..."
    return {"status": "stopping"}

@app.post("/index/run")
def run_indexing(req: IndexRunRequest, background_tasks: BackgroundTasks):
    print(f"DEBUG: run_indexing called. Force={req.force}")
    if state.progress.state == "indexing":
         raise HTTPException(status_code=400, detail="Indexing already in progress")

    def _progress_cb(curr, total, msg):
        state.progress.current = curr
        state.progress.total = total
        state.progress.current_file = msg
        state.progress.phase = f"正在处理 {curr}/{total}"

    def _do_run():
        try:
            state.progress.state = "indexing"
            state.progress.start_time = time.time()
            manager = get_sync_manager()
            
            # If force, or if we have a scan result? 
            # If force is true, we ignore scan result and just reset + scan again or just proceed.
            # Ideally:
            # 1. If force: Reset DB -> Scan all (all appear as new) -> Sync
            # 2. If not force: If scanned, use diff? Or re-scan? Re-scanning is safer.
            
            if req.force:
                 state.progress.phase = "正在清空旧索引..."
                 get_db().reset_collection()
                 # After reset, we must re-scan to get all files as 'new'
                 state.progress.phase = "正在重新扫描文件..."
                 diff = manager.scan_files()
            elif state.progress.scan_result and state.progress.scan_result.get('diff_obj'):
                 # Use cached diff if fresh?
                 diff = state.progress.scan_result['diff_obj']
            else:
                 diff = manager.scan_files()
                 
            # Run Sync
            state.progress.stop_requested = False # Reset before run
            
            def stop_check():
                return state.progress.stop_requested
                
            manager.sync_changes(diff, progress_callback=_progress_cb, stop_check=stop_check)
            
            if state.progress.stop_requested:
                state.progress.state = "stopped"
                state.progress.phase = "索引已中止"
            else:
                state.progress.state = "completed"
                state.progress.phase = "索引更新完成"
                
            state.progress.scan_result = None # Clear
            
            # Update last_updated time in store/ui
            store = get_store()
            state.progress.last_updated = store.get_config("last_indexed_time", "")
            
        except Exception as e:
            state.progress.state = "error"
            state.progress.phase = str(e)
            print(f"Index run error: {e}")

    background_tasks.add_task(_do_run)
    return {"status": "indexing_started"}

@app.get("/index/status")
def get_index_status():
    store = get_store()
    
    try:
        db_count = get_db().count()
    except Exception:
        # Collection might be resetting or not ready
        db_count = 0
        
    last_updated = store.get_config("last_indexed_time", "Unknown")
    
    return {
        "status": state.progress.state,
        "phase": state.progress.phase,
        "current": state.progress.current,
        "total": state.progress.total,
        "current_file": state.progress.current_file,
        "scan_result": state.progress.scan_result,
        "db_count": db_count,
        "last_updated": last_updated,
        "start_time": state.progress.start_time
    }

@app.get("/system/info")
def get_system_info():
    try:
        model = get_model()
        return {
            "device": model.device, # 'cuda' or 'cpu'
            "model_type": "VisionModel"
        }
    except Exception as e:
        return {"device": "unknown", "error": str(e)}

import subprocess

@app.post("/system/dialog/folder")
def open_folder_dialog():
    """
    Opens a native folder selection dialog on the server (local machine).
    Returns the selected path.
    """
    try:
        # Run a subprocess to open the dialog. This is safer than running tkinter in the server process.
        # We need to make sure we use the same python executable.
        cmd = [
            sys.executable, 
            "-c", 
            "import tkinter.filedialog; import tkinter; root=tkinter.Tk(); root.withdraw(); root.attributes('-topmost', True); print(tkinter.filedialog.askdirectory())"
        ]
        
        # Run and capture output
        # creationflags=0x08000000 (CREATE_NO_WINDOW) can hide the console window on Windows if desired,
        # but askdirectory needs a hidden root window anyway.
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        path = result.stdout.strip()
        
        if path:
            return {"path": path}
        else:
            return {"path": ""} # Cancelled
            
    except Exception as e:
        print(f"Dialog Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Serving local files (SECURITY WARNING: In production, use a proper file server or signed URLs. For local app, serving drive root or specific folder is tricky via StaticFiles if paths are absolute window paths).
# We need a custom endpoint to serve files by absolute path.
from fastapi.responses import FileResponse

# ... (existing imports)
from core.thumbnails import thumbnail_service

@app.get("/files/thumbnail")
def get_file_thumbnail(path: str):
    # Security check: exist?
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    
    thumb_path = thumbnail_service.get_thumbnail(path)
    if not thumb_path or not os.path.exists(thumb_path):
        # Fallback to original if thumbnail fails
        return FileResponse(path)
        
    return FileResponse(thumb_path)

@app.get("/files/content")
def get_file_content(path: str):
    # Security check: exist?
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)

# ... (Existing Config routes)

@app.get("/files/organize/best_shots")
def get_best_shots():
    try:
        db = get_db()
        all_files = db.get_all_files_with_time()
        
        # Sanitize data (Robust Fix for Numpy Ambiguity)
        for i, f in enumerate(all_files):
            # captured_time
            ct = f.get('captured_time', 0)
            if hasattr(ct, 'item'): ct = ct.item()
            elif hasattr(ct, '__len__') and not isinstance(ct, str) and len(ct) > 0: ct = ct[0]
            f['captured_time'] = float(ct)
            
            # aesthetic_score
            sc = f.get('aesthetic_score', 0.0)
            # Handle None explicitly if present
            if sc is None: sc = 0.0
            if hasattr(sc, 'item'): sc = sc.item()
            elif hasattr(sc, '__len__') and not isinstance(sc, str) and len(sc) > 0: sc = sc[0]
            f['aesthetic_score'] = float(sc)
            
        # Filter for photos only
        photos = [f for f in all_files if f.get('tag', 'photo') == 'photo']
        photos.sort(key=lambda x: x['captured_time'])
        
        groups = []
        current_group = []
        
        # Helper for cosine similarity
        def cosine_similarity(v1, v2):
            if v1 is None or v2 is None or len(v1) == 0 or len(v2) == 0: return 0.0
            # Manually compute dot product and norms if numpy not available or just simple list
            dot = sum(a*b for a,b in zip(v1, v2))
            norm1 = sum(a*a for a in v1) ** 0.5
            norm2 = sum(b*b for b in v2) ** 0.5
            if norm1 == 0 or norm2 == 0: return 0.0
            return dot / (norm1 * norm2)

        # Simple Clustering: Time gap < 5.0 seconds AND Similarity > 0.85
        # Relaxed time gap to 5s to catch loose bursts, but enforces visual similarity
        for photo in photos:
            if not current_group:
                current_group.append(photo)
                continue
                
            prev = current_group[-1]
            prev = current_group[-1]
            # Data is already sanitized to float
            time_diff = abs(photo.get('captured_time', 0) - prev.get('captured_time', 0))
            
            # 1. Time Check (Primary Filter)
            if time_diff < 5.0:
                # 2. Similarity Check (Secondary Filter)
                # Compare with the previous one (chaining) or the first one (star)?
                # Chaining is better for evolving bursts.
                sim = cosine_similarity(photo.get('embedding'), prev.get('embedding'))
                
                # If very close in time (< 1s), we can be lenient on similarity (maybe 0.8)
                # If further apart (1-5s), we need high similarity (0.9)
                
                threshold = 0.85
                if time_diff > 2.0: threshold = 0.92
                
                if sim >= threshold:
                    current_group.append(photo)
                else:
                    # Time is close but content is different -> Break
                    if len(current_group) > 1:
                        groups.append(current_group)
                    current_group = [photo]
            else:
                if len(current_group) > 1:
                    groups.append(current_group)
                current_group = [photo]
        
        # Check last group
        if len(current_group) > 1:
            groups.append(current_group)
            
        # Process groups to find best shot
        result = []
        for idx, group in enumerate(groups):
            # Find max score
            best_score = -1.0
            best_idx = 0
            for i, p in enumerate(group):
                s = p.get('aesthetic_score', 0.0)
                if s > best_score:
                    best_score = s
                    best_idx = i
            
            # Mark best
            processed_group = []
            for i, p in enumerate(group):
                p['is_best'] = (i == best_idx)
                p['basename'] = os.path.basename(p['file_path'])
                if 'embedding' in p: del p['embedding']
                processed_group.append(p)
            
            # Sort: Best first, then chronological
            processed_group.sort(key=lambda x: (not x['is_best'], x['captured_time']))
                
            result.append({
                "id": idx,
                "items": processed_group,
                "best_score": best_score
            })
            
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Best Shots Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/organize/documents")
def get_documents():
    try:
        db = get_db()
        all_files = db.get_all_files_with_time()
        
        # Sanitize data (Robust Fix for Numpy Ambiguity)
        for f in all_files:
            # captured_time
            ct = f.get('captured_time', 0)
            if hasattr(ct, 'item'): ct = ct.item()
            elif hasattr(ct, '__len__') and not isinstance(ct, str) and len(ct) > 0: ct = ct[0]
            f['captured_time'] = float(ct)
        
        # Filter for docs
        docs = [
            f for f in all_files 
            if f.get('tag') in ['document', 'screenshot']
        ]
        
        # Sort by recent
        docs.sort(key=lambda x: x['captured_time'], reverse=True)
        
        for f in docs:
            f['basename'] = os.path.basename(f['file_path'])
            if 'embedding' in f: del f['embedding']
            
        return docs
        
    except Exception as e:
         print(f"Documents Error: {e}")
         raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/organize/places")
def get_places():
    try:
        db = get_db()
        # We need all files to group
        all_files = db.get_all_files_with_time()
        
        places = {} # "City, Province": [files]
        
        for f in all_files:
            if f.get('tag') in ['document', 'screenshot']: continue
            
            city = f.get('city', "")
            province = f.get('province', "")
            
            if not city and not province:
                continue
                
            # Key: "City, Province" or just "City"
            # If city is empty but province exists?
            if city:
                key = f"{city}, {province}" if province else city
            else:
                key = province
                
            if key not in places:
                places[key] = []
            places[key].append(f)
            
        # Format response
        result = []
        for loc, files in places.items():
            if not files: continue

            # Calculate representative coordinate (Centroid)
            lat_sum = 0.0
            lon_sum = 0.0
            count_gps = 0
            
            for f in files:
                if f.get('latitude') and f.get('longitude'):
                    lat_sum += f['latitude']
                    lon_sum += f['longitude']
                    count_gps += 1
            
            avg_lat = lat_sum / count_gps if count_gps > 0 else None
            avg_lon = lon_sum / count_gps if count_gps > 0 else None

            # Sort by time (newest first)
            files.sort(key=lambda x: x.get('captured_time', 0), reverse=True)
            cover = files[0]
            if 'embedding' in cover: del cover['embedding']
            cover['basename'] = os.path.basename(cover['file_path'])
            
            result.append({
                "name": loc,
                "count": len(files),
                "cover": cover,
                "latitude": avg_lat,
                "longitude": avg_lon,
                "items": [] # Don't send all items in list view
            })
            
        result.sort(key=lambda x: x['count'], reverse=True)
        return result
        
    except Exception as e:
        print(f"Places Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/organize/on_this_day")
def get_on_this_day():
    try:
        db = get_db()
        files = db.get_all_files_with_time()
        
        now = datetime.now()
        current_month = now.month
        current_day = now.day
        
        # Group by year: { year: [files] }
        years_group = {}
        
        for f in files:
            ts = f.get('captured_time', 0)
            if not ts: continue
            
            try:
                dt = datetime.fromtimestamp(ts)
                # Check if same month and day
                if dt.month == current_month and dt.day == current_day:
                    # Exclude current year? Usually "On This Day" implies past years, 
                    # but seeing today's photos is also fine. Let's include all.
                    # Or maybe strictly past? "那年今日" usually means past.
                    # Let's include all for now, user can see today's too.
                    y = dt.year
                    if y not in years_group:
                        years_group[y] = []
                    
                    # Add necessary processing like basename
                    if 'embedding' in f: del f['embedding']
                    f['basename'] = os.path.basename(f['file_path'])
                    years_group[y].append(f)
            except:
                continue
                
        # Format response
        result = []
        sorted_years = sorted(years_group.keys(), reverse=True)
        
        for y in sorted_years:
            photos = years_group[y]
            # Sort photos by time desc
            photos.sort(key=lambda x: x.get('captured_time', 0), reverse=True)
            result.append({
                "year": y,
                "photos": photos
            })
            
        return result
    except Exception as e:
        print(f"OnThisDay Error: {e}")
        return []

@app.get("/files/organize/places/{location_name}")
def get_place_photos(location_name: str):
    try:
        db = get_db()
        all_files = db.get_all_files_with_time()
        
        # Determine strict matching or return all for map
        return_all = (location_name == "all_map_data")
        
        photos = []
        for f in all_files:
            if f.get('tag') in ['document', 'screenshot']: continue
            
            # Map View Request: Return anything with GPS
            if return_all:
                if f.get('latitude') is not None and f.get('longitude') is not None:
                     if 'embedding' in f: del f['embedding']
                     f['basename'] = os.path.basename(f['file_path'])
                     photos.append(f)
                continue

            city = f.get('city', "")
            province = f.get('province', "")
            
            key = ""
            if city:
                 key = f"{city}, {province}" if province else city
            else:
                 key = province
                 
            if key == location_name:
                # Sanitize
                if 'embedding' in f: del f['embedding']
                f['basename'] = os.path.basename(f['file_path'])
                photos.append(f)
                
        photos.sort(key=lambda x: x.get('captured_time', 0), reverse=True)
        return photos

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/organize/people")
def get_people():
    try:
        store = get_store()
        
        # 1. Fetch all faces
        all_faces = store.get_all_faces()
        if not all_faces:
            return []
            
        # 2. Check if clustering is needed
        # Simple heuristic: if > 10 faces have person_id = -1, run clustering on unassigned?
        # Or just run clustering on *ALL* faces every time?
        # DBSCAN is fast for < 5000 points.
        # Let's run full re-clustering to be safe and simple.
        
        embeddings = [f['embedding'] for f in all_faces]
        ids = [f['id'] for f in all_faces]
        
        import numpy as np
        if embeddings:
             embeddings_np = np.stack(embeddings)
             
             # Init processor just for clustering logic
             # Ideally we check if loaded? But FaceProcessor() without param is okay/fast if insightface imported
             # Wait, FaceProcessor __init__ loads model. We don't want to load model just for DBSCAN.
             # We should extract cluster_faces to a static method or separate module?
             # Or just instantiate it? Loading model takes memory.
             # Let's use the one in state if available? No, state.model is VisionModel.
             # Let's modify FaceProcessor to lazy load model.
             
             # For now, let's duplicate DBSCAN logic here or assume FaceProcessor allows init without model.
             # Actually `cluster_faces` only uses sklearn.
             from sklearn.cluster import DBSCAN
             db = DBSCAN(eps=0.5, min_samples=3, metric='cosine')
             db.fit(embeddings_np)
             labels = db.labels_
             
             # Update DB
             # Map label (int) to person_id (int)
             # Optimization: Bulk update? Store has `update_person_id` one by one. Slow.
             # But for <1000 faces ok.
             
             # Group in memory first
             clusters = {} # label_id: [face_objs]
             
             for i, label in enumerate(labels):
                 if label == -1: continue # Noise
                 
                 face_id = ids[i]
                 # Persist clustering result!
                 try:
                    store.update_person_id(face_id, int(label))
                 except Exception as e:
                    print(f"Error updating person_id for face {face_id}: {e}")
                 
                 # Optimization: also update the in-memory object so we don't need to re-fetch
                 all_faces[i]['person_id'] = int(label)

                 if label not in clusters:
                     clusters[label] = []
                 clusters[label].append(all_faces[i])
                 
             # Prepare result
             result = []
             for pid, faces in clusters.items():
                 # Pick a cover
                 # Ideally center of cluster, or just first
                 cover_face = faces[0]
                 
                 # Need full image file path and bbox to crop thumb on frontend?
                 # Or backend serves cropped thumb.
                 # Let's serve full image path and bbox, frontend does crop? No, clumsy.
                 # Backend `/files/face/thumbnail/{face_id}`?
                 
                 result.append({
                     "id": int(pid),
                     "name": f"Person {pid}",
                     "count": len(faces),
                     "cover_face_id": cover_face['id'],
                     "cover_file_path": cover_face['file_path'],
                     # "cover_bbox": ...
                 })
                 
             result.sort(key=lambda x: x['count'], reverse=True)
             return result
             
        return []
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/organize/people/{person_id}")
def get_person_photos(person_id: int):
    try:
        # Get faces with this person_id
        # Ideally we stored the clustering result.
        # But above logic re-clusters on the fly without saving?
        # If we didn't save `store.update_person_id`, then `get_person_photos` won't work if it queries DB.
        # So we MUST persist clustering results.
        
        # FIX: The `/people` endpoint above needs to PERSIST IDs.
        # Since loop update is slow, proceed with it for now (sqlite is fast enough for <1000 updates in transaction)
        
        store = get_store()
        
        # 1. Fetch, Cluster, Update (same logic as list, or specialized endpoint?)
        # To avoid re-clustering on every list view, we should only re-cluster if "dirty".
        # For V1, let's just do it in listing but persist it.
        
        # Rerunning logic here is separate...
        # Wait, if user clicks person 1, we expect person 1 to be the same person 1.
        # If we re-cluster, ID might change (DBSCAN labels aren't stable across runs if data changes).
        # This is a classic problem. "Person Re-Identification Stability".
        # For local V1: we accept that IDs might shift if new photos added.
        # But for `get_person_photos` to work, the DB must have `person_id` set.
        
        # So: calling `GET /people` updates the DB. Then `GET /people/{id}` queries DB.
        
        faces = store.get_faces_by_person(person_id)
        
        # Unique photos
        seen_paths = set()
        photos = []
        db = get_db() # To get standard file metadata
        
        # This is inefficient: getting all files to match path
        # Optimized: `db.get_by_path(path)`? 
        # VectorDB doesn't expose get single easily without loading all?
        # Actually `get_all_files_with_time` is cached/fast-ish?
        # Let's just create a map.
        
        all_metadata = {f['file_path']: f for f in db.get_all_files_with_time()}
        
        for f in faces:
            path = f['file_path']
            if path in seen_paths: continue
            seen_paths.add(path)
            
            if path in all_metadata:
                meta = all_metadata[path]
                if 'embedding' in meta: del meta['embedding']
                meta['basename'] = os.path.basename(path)
                # Add bbox? A photo might have multiple faces of same person?
                # For `get_person_photos`, we just show the photo.
                photos.append(meta)
                
        photos.sort(key=lambda x: x.get('captured_time', 0), reverse=True)
        return photos

    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/face/thumbnail/{face_id}")
def get_face_thumbnail_img(face_id: int):
    # Retrieve face info, crop and serve
    # Requires FaceProcessor or manual crop
    try:
        store = get_store()
        # We need get_face_by_id logic
        # store.get_face(id)?
        # Let's assume we can add it or scan
        all_faces = store.get_all_faces()
        target = next((f for f in all_faces if f['id'] == face_id), None)
        
        if not target:
             raise HTTPException(404, "Face not found")
             
        # Crop
        # Need to re-read bbox from DB? `get_all_faces` doesn't return bbox in my impl above (I returned id, path, embedding, person_id).
        # I need to fix `get_all_faces` or add `get_face(id)`.
        
        # For now, simplistic: return full image or placeholder.
        # Real impl needs `get_face_details(id)` returning bbox.
        pass
        return HTTPException(501, "Not implemented yet")
    except Exception as e:
        raise HTTPException(500, str(e))
        
@app.get("/files/organize/tags")
def get_tags():
    # Return tag cloud
    try:
        db = get_db()
        files = db.get_all_files_with_time()
        
        tag_counts = collections.defaultdict(int)
        
        for f in files:
            tags = f.get('auto_tags', [])
            for t in tags:
                if t: tag_counts[t] += 1
                
        # Load translation map
        import json
        zh_map = {}
        try:
             map_path = os.path.join(src_dir, "..", "assets", "tags_zh.json")
             if os.path.exists(map_path):
                 with open(map_path, "r", encoding="utf-8") as f:
                     zh_map = json.load(f)
        except Exception as e:
             print(f"Error loading tag translations: {e}")

        # Format
        result = []
        for t, c in tag_counts.items():
            display = zh_map.get(t, t)
            result.append({"name": t, "display_name": display, "count": c})
            
        result.sort(key=lambda x: x['count'], reverse=True)
        return result
    except Exception as e:
        print(f"Tags Error: {e}")
        return []

@app.get("/files/organize/tags/{tag_name}")
def get_tag_photos(tag_name: str):
    try:
        db = get_db()
        files = db.get_all_files_with_time()
        result = []
        for f in files:
            tags = f.get('auto_tags', [])
            if tag_name in tags:
                if 'embedding' in f: del f['embedding']
                f['basename'] = os.path.basename(f['file_path'])
                result.append(f)
        
        result.sort(key=lambda x: x.get('captured_time', 0), reverse=True)
        return result
    except Exception:
        return []

@app.get("/config")
def get_config():
    store = get_store()
    return {
        "db_path": store.get_config("db_path", "./search.db"),
        "assets_dir": store.get_config("assets_dir", "./assets"),
        "top_k": int(store.get_config("top_k", "10")),
        "api_key": store.get_config("api_key", ""),
        "model_name": store.get_config("model_name", "nano-banana")
    }

@app.post("/config")
def update_config(config: ConfigUpdate):
    store = get_store()
    store.set_config(config.key, config.value)
    return {"status": "updated", "key": config.key, "value": config.value}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
