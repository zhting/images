"""Favorites and manual albums — the basic organizing primitives a photo
app is expected to have (product plan §2.5 ②③)."""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.state import get_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["albums"])


class FavoriteRequest(BaseModel):
    file_path: str
    favorite: bool = True


class AlbumCreate(BaseModel):
    name: str


class AlbumItems(BaseModel):
    file_paths: list


def _locked():
    return get_store().get_locked_folders()


# --- Favorites ---------------------------------------------------------

@router.post("/favorites")
def set_favorite(req: FavoriteRequest):
    get_store().set_favorite(req.file_path, req.favorite)
    return {"status": "ok", "favorite": req.favorite}


@router.get("/favorites")
def list_favorites():
    return get_store().get_favorites(locked_prefixes=_locked())


# --- Albums ------------------------------------------------------------

@router.get("/albums")
def list_albums():
    return get_store().get_albums(locked_prefixes=_locked())


@router.post("/albums")
def create_album(req: AlbumCreate):
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Album name required")
    return {"id": get_store().create_album(name), "name": name}


@router.delete("/albums/{album_id}")
def delete_album(album_id: int):
    get_store().delete_album(album_id)
    return {"status": "ok"}


@router.get("/albums/{album_id}/photos")
def album_photos(album_id: int):
    return get_store().get_album_photos(album_id, locked_prefixes=_locked())


@router.post("/albums/{album_id}/items")
def add_items(album_id: int, req: AlbumItems):
    added = get_store().add_to_album(album_id, req.file_paths)
    return {"status": "ok", "added": added}


@router.delete("/albums/{album_id}/items")
def remove_items(album_id: int, req: AlbumItems):
    get_store().remove_from_album(album_id, req.file_paths)
    return {"status": "ok"}
