"""File serving routes: /files/thumbnail, /files/content, /files/browse_dir"""
import os
import io
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image, ImageOps

from api.state import get_db, get_store
from api.security import resolve_safe_path, require_unlocked, check_privacy_session
from core.thumbnails import thumbnail_service

router = APIRouter(tags=["files"])

PLACEHOLDER_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300">'
    '<rect width="100%" height="100%" fill="#1a1a1a"/>'
    '<path d="M110 190l35-45 25 30 20-25 35 40z" fill="#333"/>'
    '<circle cx="120" cy="115" r="14" fill="#333"/></svg>'
)


def _extract_privacy_token(request: Request, header_token: Optional[str]) -> Optional[str]:
    """Privacy token comes from the X-Privacy-Token header, or — for
    <img>/<video> URLs where headers are impossible — a `token` query
    parameter."""
    return header_token or request.query_params.get("token")


@router.get("/files/browse_dir")
def browse_directory(
    request: Request,
    path: str = "",
    password: Optional[str] = None,
    x_privacy_token: Optional[str] = Header(default=None),
):
    try:
        store = get_store()
        db = get_db()
        locked_folders = store.get_locked_folders()

        if path and store.is_path_locked(path, locked_folders):
            token = _extract_privacy_token(request, x_privacy_token)
            authorized = check_privacy_session(token)
            # Legacy fallback (deprecated): raw password query param.
            if not authorized and password and store.verify_privacy_password(password):
                authorized = True
            if not authorized:
                return {
                    "is_locked": True, "authorized": False,
                    "current_path": path, "directories": [], "files": []
                }

        if not path:
            asset_paths = store.get_asset_paths()
            roots = []
            use_sql = store.count_photos() > 0
            all_files = None if use_sql else db.get_all_files_with_time(include_embeddings=False)
            for p in asset_paths:
                p_normalized = p.replace("\\", "/").rstrip("/") + "/"
                if use_sql:
                    # P1a stage 2: indexed prefix COUNT per root.
                    count = store.count_photos_under_prefix(p)
                else:
                    count = sum(
                        1 for f in all_files
                        if f.get('file_path', '').replace("\\", "/").startswith(p_normalized)
                        and f.get('tag') not in ['document', 'screenshot', 'trash', 'error']
                    )
                roots.append({
                    "name": os.path.basename(p_normalized.rstrip("/")) or p,
                    "path": p, "count": count, "is_dir": True,
                    "is_locked": store.is_path_locked(p, locked_folders)
                })
            return {"directories": roots, "files": [], "current_path": "", "parent_path": ""}

        norm_path = path.replace("\\", "/").rstrip("/") + "/"
        if store.count_photos() > 0:
            # P1a stage 2: work on the subtree only, not the whole library.
            candidates = store.get_photos_under_prefix(path)
        else:
            candidates = db.get_all_files_with_time(include_embeddings=False)
        direct_files = []
        subdirs = {}

        for f in candidates:
            fp = f.get('file_path', '').replace("\\", "/")
            tag = f.get('tag', 'photo')
            if tag in ['document', 'screenshot', 'trash', 'error']:
                continue
            if not fp.startswith(norm_path):
                continue
            rel = fp[len(norm_path):]
            if "/" not in rel:
                direct_files.append({
                    "file_path": f.get('file_path'),
                    "basename": os.path.basename(f.get('file_path', '')),
                    "captured_time": float(f.get('captured_time', 0)),
                    "aesthetic_score": float(f.get('aesthetic_score', 0.0)),
                    "tag": tag
                })
            else:
                subdir_name = rel.split("/")[0]
                subdirs[subdir_name] = subdirs.get(subdir_name, 0) + 1

        direct_files.sort(key=lambda x: x['captured_time'], reverse=True)

        dir_list = []
        for name, count in sorted(subdirs.items()):
            dir_path = os.path.join(path, name).replace("\\", "/")
            dir_list.append({
                "name": name, "path": dir_path, "count": count, "is_dir": True,
                "is_locked": store.is_path_locked(dir_path, locked_folders)
            })

        parent_path = ""
        stripped = path.replace("\\", "/").rstrip("/")
        last_slash = stripped.rfind("/")
        if last_slash > 0:
            parent_path = stripped[:last_slash]

        return {
            "directories": dir_list, "files": direct_files,
            "current_path": path, "parent_path": parent_path,
            "is_locked": store.is_path_locked(path, locked_folders),
            "authorized": True
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise


@router.get("/files/thumbnail")
def get_file_thumbnail(
    request: Request,
    path: str,
    size: str = "grid",
    x_privacy_token: Optional[str] = Header(default=None),
):
    safe = resolve_safe_path(path)
    require_unlocked(safe, _extract_privacy_token(request, x_privacy_token))
    if not os.path.exists(safe):
        raise HTTPException(status_code=404, detail="File not found")

    thumb_path = thumbnail_service.get_thumbnail(safe, size=size)
    if not thumb_path or not os.path.exists(thumb_path):
        # Never fall back to streaming the multi-MB original into a grid
        # <img> — that starves every other thumbnail request on screen.
        # Serve a lightweight placeholder instead; client may retry.
        return Response(
            content=PLACEHOLDER_SVG,
            media_type="image/svg+xml",
            headers={"Cache-Control": "no-cache"},
            status_code=200,
        )

    # Thumbnails are content-addressed by source mtime; treat as immutable.
    return FileResponse(
        thumb_path,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/files/content")
def get_file_content(
    request: Request,
    path: str,
    x_privacy_token: Optional[str] = Header(default=None),
):
    safe = resolve_safe_path(path)
    require_unlocked(safe, _extract_privacy_token(request, x_privacy_token))
    if not os.path.exists(safe):
        raise HTTPException(status_code=404, detail="File not found")

    # Conditional caching: originals on disk are effectively immutable;
    # an mtime+size ETag lets the gallery re-view images without
    # re-downloading them (previous behaviour was Cache-Control: no-store).
    stat = os.stat(safe)
    etag = f'"{int(stat.st_mtime)}-{stat.st_size}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    cache_headers = {"ETag": etag, "Cache-Control": "private, max-age=0, must-revalidate"}

    _, ext = os.path.splitext(safe)
    if ext.lower() in ['.heic', '.heif']:
        try:
            with Image.open(safe) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img_io = io.BytesIO()
                img.save(img_io, 'JPEG', quality=85)
                img_io.seek(0)
                return StreamingResponse(img_io, media_type="image/jpeg", headers=cache_headers)
        except Exception as e:
            print(f"[FileServer] HEIC Convert Error: {e}")
            return FileResponse(safe, headers=cache_headers)

    return FileResponse(safe, headers=cache_headers)
