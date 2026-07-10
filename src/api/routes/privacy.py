"""Privacy routes: password management, folder locking."""
from fastapi import APIRouter, HTTPException

from api.state import get_store
from api.security import create_privacy_session, clear_privacy_sessions
from api.models import PrivacyPasswordRequest, PrivacyVerifyRequest, PrivacyLockRequest

router = APIRouter(tags=["privacy"])


@router.get("/privacy/status")
def get_privacy_status():
    store = get_store()
    return {
        "has_password": store.is_privacy_password_set(),
        "locked_folders": store.get_locked_folders()
    }


@router.post("/privacy/set_password")
def set_privacy_password(req: PrivacyPasswordRequest):
    try:
        store = get_store()
        if store.is_privacy_password_set():
            if not req.old_password or not store.verify_privacy_password(req.old_password):
                raise HTTPException(status_code=403, detail="Old password incorrect")
        store.set_privacy_password(req.password)
        clear_privacy_sessions()  # old sessions die with the old password
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/privacy/verify")
def verify_privacy_password(req: PrivacyVerifyRequest):
    store = get_store()
    if store.verify_privacy_password(req.password):
        return {
            "status": "ok",
            "verified": True,
            # Client should keep this in memory (not localStorage) and send
            # it as the X-Privacy-Token header, or `token` param for <img> URLs.
            "session_token": create_privacy_session(),
        }
    raise HTTPException(status_code=403, detail="Incorrect password")


@router.post("/privacy/lock")
def lock_folder(req: PrivacyLockRequest):
    try:
        store = get_store()
        if not store.is_privacy_password_set():
            raise HTTPException(400, "Set a privacy password first")
        store.add_locked_folder(req.path)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/privacy/unlock")
def unlock_folder(req: PrivacyLockRequest):
    try:
        store = get_store()
        store.remove_locked_folder(req.path)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))
