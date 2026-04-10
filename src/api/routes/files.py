"""File serving routes: /files/thumbnail, /files/content, /files/browse_dir"""
import os
import io
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image, ImageOps

from api.state import get_db, get_store
from core.thumbnails import thumbnail_service

router = APIRouter(tags=["files"])


@router.get("/files/browse_dir")
def browse_directory(path: str = "", password: Optional[str] = None):
    try:
        store = get_store()
        db = get_db()
        locked_folders = store.get_locked_folders()

        if path and store.is_path_locked(path, locked_folders):
            if not password or not store.verify_privacy_password(password):
                return {
                    "is_locked": True, "authorized": False,
                    "current_path": path, "directories": [], "files": []
                }

        if not path:
            asset_paths = store.get_asset_paths()
            roots = []
            all_files = db.get_all_files_with_time(include_embeddings=False)
            for p in asset_paths:
                p_normalized = p.replace("\\", "/").rstrip("/") + "/"
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
        all_files = db.get_all_files_with_time(include_embeddings=False)
        direct_files = []
        subdirs = {}

        for f in all_files:
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
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/thumbnail")
def get_file_thumbnail(path: str):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    thumb_path = thumbnail_service.get_thumbnail(path)
    if not thumb_path or not os.path.exists(thumb_path):
        return FileResponse(path)
    return FileResponse(thumb_path, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/files/content")
def get_file_content(path: str):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    _, ext = os.path.splitext(path)
    if ext.lower() in ['.heic', '.heif']:
        try:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img_io = io.BytesIO()
                img.save(img_io, 'JPEG', quality=85)
                img_io.seek(0)
                return StreamingResponse(img_io, media_type="image/jpeg")
        except Exception as e:
            print(f"[FileServer] HEIC Convert Error: {e}")
            return FileResponse(path, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})

    return FileResponse(path, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})
