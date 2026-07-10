"""Security helpers for file-serving routes.

Two concerns are centralized here:

1. Path guard — every user-supplied filesystem path must resolve to a
   location inside one of the configured photo root directories.  This
   closes the arbitrary-file-read / path-traversal hole in
   /files/content and /files/thumbnail.

2. Privacy sessions — instead of sending the privacy password with
   every request (previously as a GET query parameter, which leaks into
   logs and browser history), /privacy/verify now issues a short-lived
   in-memory session token.  Subsequent requests carry it via the
   ``X-Privacy-Token`` header, or — for <img> URLs where headers are
   not possible — via a ``token`` query parameter.

Sessions live in process memory only: restarting the app invalidates
them, which is the desired semantic for a local, single-user app.
"""
import os
import secrets
import time
import threading

from fastapi import HTTPException

from api.state import get_store

# ---------------------------------------------------------------------------
# 1. Path guard
# ---------------------------------------------------------------------------


def _norm(p: str) -> str:
    """Resolve symlinks / '..' and normalize case for comparison."""
    return os.path.normcase(os.path.realpath(p))


def resolve_safe_path(raw_path: str) -> str:
    """Return the real path if it lies inside a configured photo root.

    Raises HTTP 403 otherwise.  An empty root list denies everything —
    on a fresh install nothing has been indexed, so nothing should be
    servable.
    """
    if not raw_path:
        raise HTTPException(status_code=403, detail="Path required")

    real = os.path.realpath(raw_path)
    real_cmp = os.path.normcase(real)

    for root in get_store().get_asset_paths():
        root_cmp = _norm(root)
        try:
            if os.path.commonpath([real_cmp, root_cmp]) == root_cmp:
                return real
        except ValueError:
            # Different drives on Windows — cannot share a common path.
            continue

    raise HTTPException(status_code=403, detail="Path outside configured photo roots")


# ---------------------------------------------------------------------------
# 2. Privacy sessions
# ---------------------------------------------------------------------------

SESSION_TTL_SECONDS = 30 * 60  # 30 minutes, sliding

_sessions: dict = {}
_sessions_lock = threading.Lock()


def create_privacy_session() -> str:
    """Issue a new privacy session token after a successful password check."""
    token = secrets.token_urlsafe(32)
    with _sessions_lock:
        _sessions[token] = time.time() + SESSION_TTL_SECONDS
    return token


def check_privacy_session(token) -> bool:
    """True if the token exists and has not expired.  Renews TTL on use."""
    if not token:
        return False
    now = time.time()
    with _sessions_lock:
        expiry = _sessions.get(token)
        if expiry is None or expiry < now:
            _sessions.pop(token, None)
            return False
        _sessions[token] = now + SESSION_TTL_SECONDS
        return True


def clear_privacy_sessions() -> None:
    """Invalidate all sessions (e.g. after a password change)."""
    with _sessions_lock:
        _sessions.clear()


def require_unlocked(path: str, token) -> None:
    """Raise HTTP 403 if *path* is inside a locked folder and no valid
    privacy session token was supplied."""
    store = get_store()
    locked = store.get_locked_folders()
    if not locked:
        return
    if store.is_path_locked(path, locked) and not check_privacy_session(token):
        raise HTTPException(status_code=403, detail="Folder is locked")
