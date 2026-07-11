"""Search routes: /search/text, /search/image, /search/ai, /generate"""
import os
import io
import time
import base64
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException
from PIL import Image

from api.state import get_model, get_db, get_store, get_model_client, encode_gate
from api.models import TextSearchRequest, AISearchRequest, SearchResultItem, GenerateRequest
from api.helpers import filter_locked_items, cached_translate, is_ascii

router = APIRouter(tags=["search"])


@router.post("/search/image", response_model=List[SearchResultItem])
async def search_image(file: UploadFile = File(...), top_k: Optional[int] = None):
    try:
        model = get_model()
        db = get_db()
        store = get_store()
        limit = top_k if top_k is not None else int(store.get_config("top_k", 10))

        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        with encode_gate:
            embedding = model.encode(image)
        results = db.search(embedding, top_k=limit)

        response = []
        for res in results:
            path = res['file_path']
            score = 1 - res.get('distance', 0)
            if score < 0.1:
                continue
            response.append({
                "file_path": path,
                "score": score,
                "basename": os.path.basename(path),
                "tag": res.get('tag', 'photo')
            })

        locked_folders = store.get_locked_folders()
        response = filter_locked_items(response, locked_folders)
        return response

    except Exception as e:
        raise


@router.post("/search/text")
def search_text(request: TextSearchRequest):
    try:
        model = get_model()
        db = get_db()
        store = get_store()
        top_k = request.top_k if request.top_k is not None else int(store.get_config("top_k", 10))

        start_total = time.time()
        query_text = request.query

        t0 = time.time()
        if request.use_translation and not is_ascii(query_text):
            try:
                translated = cached_translate(query_text, target_lang="English")
                print(f"Translating '{query_text}' -> '{translated}'")
                if translated and len(translated) > 0:
                    query_text = translated
            except Exception as e:
                print(f"Translation failed: {e}")
        t_translate = time.time() - t0

        t0 = time.time()
        with encode_gate:
            embedding = model.encode_text(query_text)
        t_encode = time.time() - t0

        t0 = time.time()
        results = db.search(embedding, top_k=top_k)
        t_search = time.time() - t0

        print(f"[Search Perf] Trans: {t_translate:.4f}s | Encode: {t_encode:.4f}s | "
              f"DB: {t_search:.4f}s | Total: {time.time() - start_total:.4f}s")

        items = []
        for res in results:
            path = res['file_path']
            score = 1 - res.get('distance', 0)
            if score < 0.1:
                continue
            items.append({
                "file_path": path,
                "score": score,
                "basename": os.path.basename(path),
                "tag": res.get('tag', 'photo')
            })

        locked_folders = store.get_locked_folders()
        items = filter_locked_items(items, locked_folders)

        return {
            "results": items,
            "translated_query": query_text if query_text != request.query else None
        }

    except Exception as e:
        raise


@router.post("/search/ai", response_model=List[SearchResultItem])
async def search_ai(req: AISearchRequest):
    try:
        store = get_store()
        model = get_model()
        db = get_db()
        gen = get_model_client("search_ai", store)

        print(f"Generating image for prompt: {req.prompt}")
        generated_img = gen.generate(req.prompt)
        with encode_gate:
            vector = model.encode(generated_img)
        results = db.search(vector, top_k=req.top_k)

        formatted = []
        for res in results:
            path = res['file_path']
            score = 1 - res.get('distance', 0)
            if score < 0.1:
                continue
            formatted.append({
                "file_path": path,
                "score": score,
                "basename": os.path.basename(path)
            })
        return formatted

    except Exception as e:
        print(f"AI Search Error: {e}")
        raise


@router.post("/generate")
async def generate_image_endpoint(req: GenerateRequest):
    try:
        store = get_store()
        from core.generator import MockGenerator, OpenAIGenerator, NanoBananaGenerator

        gen = None
        if req.provider and req.provider != "config":
            if req.provider == "mock":
                gen = MockGenerator()
            elif req.provider == "openai":
                gen = OpenAIGenerator(api_key=store.get_config("api_key"))
            elif req.provider == "nano-banana":
                gen = NanoBananaGenerator(
                    api_key=store.get_config("api_key"),
                    model=store.get_config("model_name")
                )

        if not gen:
            gen = get_model_client("search_ai", store)
            print(f"[Generate] Using configured generator: {gen.__class__.__name__}")

        print(f"Generating image with {req.provider} for prompt: {req.prompt}")
        img = gen.generate(req.prompt)

        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return {"image": f"data:image/png;base64,{img_str}"}

    except Exception as e:
        print(f"Generate Error: {e}")
        raise
