"""Trash (recycle bin) routes."""
import os

from fastapi import APIRouter, HTTPException

from api.state import get_db, state
from api.models import TrashActionRequest

import logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["trash"])


@router.post("/files/trash")
def move_to_trash(req: TrashActionRequest):
    try:
        db = get_db()
        for path in req.file_paths:
            db.soft_delete_file(path)
        state.timeline_cache = None
        state.on_this_day_cache = None
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/files/restore")
def restore_from_trash(req: TrashActionRequest):
    try:
        db = get_db()
        for path in req.file_paths:
            db.restore_file(path)
        state.timeline_cache = None
        state.on_this_day_cache = None
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/files/trash")
def empty_trash(req: TrashActionRequest):
    try:
        db = get_db()
        targets = req.file_paths
        trash_files = {f['file_path']: f for f in db.get_trash_files()}

        if "ALL" in targets:
            targets = list(trash_files.keys())

        deleted_count = 0
        for path in targets:
            if path in trash_files:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as err:
                        logger.error(f"Error deleting file {path}: {err}")
                db.delete_by_path(path)
                deleted_count += 1

        state.timeline_cache = None
        state.on_this_day_cache = None
        return {"status": "ok", "deleted": deleted_count}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/files/organize/trash")
def get_trash_files():
    try:
        db = get_db()
        return db.get_trash_files()
    except Exception as e:
        raise HTTPException(500, str(e))
