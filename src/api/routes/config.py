"""Config routes: /config, /config/wishlist, /config/world_wishlist"""
import json

from fastapi import APIRouter

from api.state import get_store
from api.models import ConfigUpdate, WishlistUpdate

router = APIRouter(tags=["config"])


@router.get("/config")
def get_config():
    store = get_store()
    model_name = store.get_config("model_name", "")
    if not model_name:
        model_name = "nano-banana"
    return {
        "db_path": store.get_config("db_path", "./search.db"),
        "assets_dir": store.get_config("assets_dir", "./assets"),
        "top_k": int(store.get_config("top_k", "10")),
        "api_key": store.get_config("api_key", ""),
        "model_name": model_name,
        "saved_model_list": store.get_config("saved_model_list", "[]"),
        "api_sources": store.get_config("api_sources", "[]"),
        "module_assignments": store.get_config("module_assignments", "{}")
    }


@router.post("/config")
def update_config(conf: ConfigUpdate):
    try:
        store = get_store()
        store.set_config(conf.key, conf.value)
        return {"status": "ok", "key": conf.key, "value": conf.value}
    except Exception:
        raise


# --- Wishlist ---
@router.get("/config/wishlist")
def get_wishlist():
    store = get_store()
    wishlist = store.get_config("travel_wishlist", "[]")
    try:
        return json.loads(wishlist)
    except Exception:
        return []


@router.post("/config/wishlist")
def update_wishlist(req: WishlistUpdate):
    store = get_store()
    store.set_config("travel_wishlist", json.dumps(req.wishlist))
    return {"status": "ok", "wishlist": req.wishlist}


# --- World Wishlist ---
@router.get("/config/world_wishlist")
def get_world_wishlist():
    store = get_store()
    wishlist = store.get_config("world_travel_wishlist", "[]")
    try:
        return json.loads(wishlist)
    except Exception:
        return []


@router.post("/config/world_wishlist")
def update_world_wishlist(req: WishlistUpdate):
    store = get_store()
    store.set_config("world_travel_wishlist", json.dumps(req.wishlist))
    return {"status": "ok", "wishlist": req.wishlist}
