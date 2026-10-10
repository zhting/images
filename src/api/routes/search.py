"""Search routes: /search/text, /search/image, /search/ai, /generate"""
import os
import io
import time
import base64
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File
from PIL import Image

from api.state import get_model, get_db, get_store, get_model_client, encode_gate
from api.models import TextSearchRequest, AISearchRequest, SearchResultItem, GenerateRequest
from api.helpers import filter_locked_items, cached_translate, is_ascii

import logging
logger = logging.getLogger(__name__)

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

    except Exception:
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
                logger.info(f"Translating '{query_text}' -> '{translated}'")
                if translated and len(translated) > 0:
                    query_text = translated
            except Exception as e:
                logger.error(f"Translation failed: {e}")
        t_translate = time.time() - t0

        t0 = time.time()
        with encode_gate:
            embedding = model.encode_text(query_text)
        t_encode = time.time() - t0

        t0 = time.time()
        results = db.search(embedding, top_k=top_k)
        t_search = time.time() - t0

        logger.debug(f"[Search Perf] Trans: {t_translate:.4f}s | Encode: {t_encode:.4f}s | "
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

    except Exception:
        raise


@router.post("/search/ai", response_model=List[SearchResultItem])
async def search_ai(req: AISearchRequest):
    try:
        store = get_store()
        model = get_model()
        db = get_db()
        gen = get_model_client("search_ai", store)

        logger.info(f"Generating image for prompt: {req.prompt}")
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
        logger.error(f"AI Search Error: {e}")
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
            logger.info(f"[Generate] Using configured generator: {gen.__class__.__name__}")

        logger.info(f"Generating image with {req.provider} for prompt: {req.prompt}")
        img = gen.generate(req.prompt)

        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return {"image": f"data:image/png;base64,{img_str}"}

    except Exception as e:
        logger.error(f"Generate Error: {e}")
        raise


# ---------------------------------------------------------------------------
# Combined search: natural-language filters + text in photos + semantics
# ---------------------------------------------------------------------------
_EXCLUDED_TAGS = {"trash", "error"}
_SEMANTIC_MIN = 0.1        # same floor as /search/text
_TEXT_HIT_SCORE = 0.3      # a photo containing the words is a strong match
_TEXT_HIT_BOOST = 0.1


def _encode_query(text: str):
    """Translate (CJK -> English, as /search/text does) and embed."""
    query_text = text
    if not is_ascii(text):
        try:
            translated = cached_translate(text, target_lang="English")
            if translated:
                query_text = translated
        except Exception as e:
            logger.error(f"Translation failed: {e}")
    with encode_gate:
        emb = get_model().encode_text(query_text)
    return emb, (query_text if query_text != text else None)


def _snippet(text: str, term: str, width: int = 24) -> str:
    """A short excerpt of *text* around *term* for the result card."""
    flat = " ".join((text or "").split())
    if not flat:
        return ""
    i = flat.lower().find((term or "").lower())
    if i == -1:
        # term matched with whitespace removed; fall back to the start
        return flat[:width * 2] + ("…" if len(flat) > width * 2 else "")
    start = max(0, i - width)
    end = min(len(flat), i + len(term) + width)
    return ("…" if start else "") + flat[start:end] + ("…" if end < len(flat) else "")


@router.get("/search/smart")
def search_smart(q: str = "", top_k: int = 200):
    """One search box for everything:

    - 时间/地点/人物/类型/收藏 phrases become filters (see core.query_parser),
      only for places and people that exist in the library;
    - quoted text must appear in the photo (OCR);
    - the rest is ranked with the existing SigLIP vectors — nothing is
      re-encoded or re-indexed — and also matched against photo text.
    """
    import numpy as np
    from core.query_parser import parse_query
    from core.ocr_worker import get_worker

    store = get_store()
    locked = store.get_locked_folders()
    people_map = store.get_named_people()
    parsed = parse_query(q, places=store.get_known_places(), people=people_map)
    id_to_name = {v: k for k, v in people_map.items()}
    semantic = parsed.text

    results: dict = {}          # path -> {score, match: set}
    candidates = None
    total_candidates = None
    if parsed.has_filters:
        items, total_candidates = store.filter_photos(
            date_from=parsed.date_from, date_to=parsed.date_to, places=parsed.places,
            people=parsed.people, types=parsed.types, favorite=parsed.favorite,
            ocr_terms=parsed.ocr_terms, locked_prefixes=locked, limit=5000)
        candidates = {i["file_path"]: i for i in items}

    translated = None
    if semantic:
        emb, translated = _encode_query(semantic)
        qv = np.asarray(emb, dtype=np.float32)
        db = get_db()
        if candidates is not None and len(candidates) <= 3000:
            # Exact ranking of the filtered set with its stored vectors.
            for fp, vecs in db.get_embeddings(list(candidates)).items():
                if fp in candidates:
                    score = float(max(np.dot(np.asarray(v, dtype=np.float32), qv) for v in vecs))
                    results[fp] = {"score": score, "match": {"semantic"}}
        else:
            hits = db.search(emb, top_k=3000 if candidates is not None else max(top_k * 2, 100))
            for h in hits:
                fp = (h.get("file_path") or "").replace("\\", "/")
                if candidates is not None and fp not in candidates:
                    continue
                if h.get("tag") in _EXCLUDED_TAGS:
                    continue
                score = 1 - h.get("distance", 0)
                if candidates is None and score < _SEMANTIC_MIN:
                    continue
                if fp not in results or score > results[fp]["score"]:
                    results[fp] = {"score": score, "match": {"semantic"}}

        # The same words written in the photo (receipts, signs, slides).
        if len(store.norm_text(semantic)) >= 2:
            for fp in store.search_photo_text(semantic, locked_prefixes=locked, limit=300):
                if candidates is not None and fp not in candidates:
                    continue
                if fp in results:
                    results[fp]["score"] += _TEXT_HIT_BOOST
                    results[fp]["match"].add("text")
                else:
                    results[fp] = {"score": _TEXT_HIT_SCORE, "match": {"text"}}
    elif candidates is not None:
        for fp in candidates:
            results[fp] = {"score": None, "match": {"filter"}}

    if parsed.ocr_terms:
        for r in results.values():
            r["match"].add("text")

    # Respect locked folders for vector hits (filter_photos already did).
    paths = [p for p in results if filter_locked_items([{"file_path": p}], locked)]
    details = store.get_photos_by_paths(paths)
    texts = store.get_texts([p for p in paths if "text" in results[p]["match"]])
    term = parsed.ocr_terms[0] if parsed.ocr_terms else semantic

    out = []
    for p in paths:
        d = details.get(p)
        if not d or d.get("tag") in _EXCLUDED_TAGS:
            continue
        r = results[p]
        out.append({
            "file_path": p,
            "basename": os.path.basename(p),
            "score": r["score"],
            "tag": d.get("tag", "photo"),
            "captured_time": d.get("captured_time", 0),
            "favorite": d.get("favorite", False),
            "match": sorted(r["match"]),
            "snippet": _snippet(texts.get(p, ""), term) if p in texts else "",
        })
    if semantic:
        out.sort(key=lambda x: x["score"] or 0, reverse=True)
    else:
        out.sort(key=lambda x: x["captured_time"] or 0, reverse=True)
    out = out[:top_k]

    parsed_dict = parsed.to_dict()
    parsed_dict["people_names"] = [id_to_name.get(pid, "") for pid in parsed.people]
    ocr_status = get_worker().status()
    return {
        "query": q,
        "results": out,
        "parsed": parsed_dict,
        "translated_query": translated,
        "total_candidates": total_candidates,
        "ocr": {"state": ocr_status["state"], "pending": ocr_status["pending"],
                "done": ocr_status["done"], "available": ocr_status["available"]},
    }


@router.get("/ocr/status")
def ocr_status():
    from core.ocr_worker import get_worker
    return get_worker().status()


@router.post("/ocr/config")
def ocr_config(body: dict):
    """{"enabled": bool} — pause or resume background text recognition."""
    from core.ocr_worker import get_worker
    enabled = bool(body.get("enabled", True))
    get_store().set_config("ocr_enabled", "true" if enabled else "false")
    w = get_worker()
    if enabled:
        w.start()
        w.wake()
    return w.status()
