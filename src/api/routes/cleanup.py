"""Cleanup assistant: suggestions of what to move to the recycle bin
(duplicates, bursts, accidental and blurry shots, old screenshots, large
videos) with the space each would free. Deleting goes through the normal
/files/trash endpoint, so it is undoable like everywhere else."""
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.state import get_store
from core import cleanup
from core.tasks import runner

import logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["cleanup"])


class KeepRequest(BaseModel):
    kind: str
    file_paths: List[str]


def _quality_status():
    try:
        from core.quality_worker import get_worker
        w = get_worker()
        w.wake()
        return w.status()
    except Exception:
        store = get_store()
        return {"state": "idle", "pending": store.count_quality_pending(), "done": store.count_quality_done()}


@router.get("/cleanup")
def get_cleanup():
    store = get_store()
    locked = store.get_locked_folders()
    result = cleanup.build(store, locked, texts=store.get_texts)
    # Old libraries may still be computing content hashes; duplicates
    # fill in once that finishes.
    pending_hash = store.count_unhashed_photos()
    if pending_hash:
        from api.routes.organize import _hash_backfill
        runner.submit("hash_backfill", _hash_backfill)
    result["hash_pending"] = pending_hash
    result["quality"] = _quality_status()
    return result


@router.post("/cleanup/keep")
def keep(req: KeepRequest):
    if req.kind not in cleanup.LABELS:
        raise HTTPException(status_code=400, detail="unknown category")
    n = get_store().keep_for_cleanup(req.file_paths, req.kind)
    return {"kept": n}
