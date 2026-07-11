"""People / face recognition routes."""
import os

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api.state import get_db, get_store, state
from api.models import PersonNameUpdate
from api.helpers import filter_locked_items

router = APIRouter(tags=["people"])


@router.get("/files/organize/people")
def get_people(force_refresh: bool = False, page: int = 1, page_size: int = 100):
    try:
        clusters = []
        store = get_store()

        if not force_refresh and state.people_cache is not None:
            clusters = state.people_cache
        else:
            if not force_refresh:
                clusters = store.get_clustered_people()

            if not clusters or force_refresh:
                from sklearn.cluster import DBSCAN
                import collections

                all_faces = store.get_all_faces()
                if not all_faces:
                    return {"items": [], "total": 0, "page": page, "page_size": page_size}

                clustered_faces = []
                unclustered_faces = []
                for f in all_faces:
                    emb = f['embedding']
                    if isinstance(emb, bytes):
                        emb = np.frombuffer(emb, dtype=np.float32)
                    if emb is not None and len(emb) > 0:
                        f['embedding'] = emb
                        if force_refresh or f.get('person_id', -1) == -1:
                            unclustered_faces.append(f)
                        else:
                            clustered_faces.append(f)

                updates = []
                if force_refresh:
                    store.clear_all_clusters()
                    max_pid = -1
                else:
                    max_pid = max([-1] + [f['person_id'] for f in clustered_faces])

                if unclustered_faces:
                    # Stage 1: Assign to existing clusters
                    if clustered_faces and not force_refresh:
                        cluster_embs = collections.defaultdict(list)
                        for f in clustered_faces:
                            cluster_embs[f['person_id']].append(f['embedding'])

                        centroid_ids = []
                        centroids = []
                        for pid, embs in cluster_embs.items():
                            centroid_ids.append(pid)
                            centroids.append(np.mean(embs, axis=0))

                        if centroids:
                            centroid_matrix = np.stack(centroids)
                            norms = np.linalg.norm(centroid_matrix, axis=1, keepdims=True)
                            norms[norms == 0] = 1
                            centroid_matrix = centroid_matrix / norms

                            still_unclustered = []
                            for f in unclustered_faces:
                                emb = f['embedding']
                                norm = np.linalg.norm(emb)
                                if norm == 0:
                                    continue
                                emb_norm = emb / norm
                                sims = np.dot(centroid_matrix, emb_norm)
                                best_idx = np.argmax(sims)
                                if sims[best_idx] >= 0.60:
                                    updates.append((centroid_ids[best_idx], f['id']))
                                else:
                                    still_unclustered.append(f)
                            unclustered_faces = still_unclustered

                    # Stage 2: DBSCAN on remaining
                    if unclustered_faces:
                        embeddings_np = np.stack([f['embedding'] for f in unclustered_faces])
                        db_scan = DBSCAN(eps=0.45, min_samples=3, metric='cosine')
                        db_scan.fit(embeddings_np)
                        labels = db_scan.labels_

                        new_pids = {}
                        for i, label in enumerate(labels):
                            if label != -1:
                                if label not in new_pids:
                                    max_pid += 1
                                    new_pids[label] = max_pid
                                updates.append((new_pids[label], unclustered_faces[i]['id']))

                if updates:
                    store.batch_update_face_clusters(updates)

            locked_folders = store.get_locked_folders()
            clusters = store.get_clustered_people()
            clusters = filter_locked_items(clusters, locked_folders, 'cover_file_path')
            state.people_cache = clusters

        start = (page - 1) * page_size
        items = clusters[start:start + page_size]
        return {"items": items, "total": len(clusters), "page": page, "page_size": page_size}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise


@router.get("/files/organize/people/{person_id}")
def get_person_photos(person_id: int):
    try:
        store = get_store()
        db = get_db()
        faces = store.get_faces_by_person(person_id)
        # P1a stage 2: hydrate only this person's paths instead of
        # loading the entire library into a dict.
        if store.count_photos() > 0:
            all_metadata = store.get_photos_by_paths(
                [f['file_path'] for f in faces])
        else:
            all_metadata = {f['file_path']: f for f in db.get_all_files_with_time()}

        seen_paths = set()
        photos = []
        for f in faces:
            path = f['file_path']
            if path in seen_paths:
                continue
            seen_paths.add(path)
            if path in all_metadata:
                meta = all_metadata[path]
                meta.pop('embedding', None)
                meta['basename'] = os.path.basename(path)
                photos.append(meta)

        locked_folders = store.get_locked_folders()
        photos = filter_locked_items(photos, locked_folders, 'file_path')
        photos.sort(key=lambda x: x.get('captured_time', 0), reverse=True)
        return photos
    except Exception as e:
        raise


@router.post("/files/organize/people/name")
def update_person_name(req: PersonNameUpdate):
    try:
        store = get_store()
        store.set_person_name(req.person_id, req.name)
        if req.name:
            embeddings = store.get_faces_by_person_id(req.person_id)
            if embeddings:
                mean_emb = np.mean(embeddings, axis=0)
                mean_emb = mean_emb / np.linalg.norm(mean_emb)
                store.upsert_identity(req.name, mean_emb)
        state.people_cache = None
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/files/organize/people/{person_id}")
def delete_person_cluster(person_id: int):
    try:
        store = get_store()
        store.reset_person_cluster(person_id)
        state.people_cache = None
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/files/face/thumbnail/{face_id}")
def get_face_thumbnail_img(face_id: int):
    try:
        from PIL import Image, ImageOps
        from core.thumbnails import thumbnail_service

        cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'assets', '.cache', 'faces')
        os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"face_{face_id}.jpg")

        if os.path.exists(cache_file):
            return FileResponse(cache_file, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})

        store = get_store()
        target = store.get_face(face_id)
        if not target:
            raise HTTPException(404, "Face not found")

        file_path = target['file_path']
        bbox = target['bbox']
        if not os.path.exists(file_path):
            raise HTTPException(404, "Source file not found")
        if not bbox or len(bbox) != 4:
            thumb_path = thumbnail_service.get_thumbnail(file_path)
            return FileResponse(thumb_path)

        with Image.open(file_path) as img:
            img = ImageOps.exif_transpose(img)
            w, h = img.size
            x1, y1, x2, y2 = bbox
            fw = x2 - x1
            fh = y2 - y1
            padding = 0.3
            nx1 = max(0, x1 - fw * padding)
            ny1 = max(0, y1 - fh * padding)
            nx2 = min(w, x2 + fw * padding)
            ny2 = min(h, y2 + fh * padding)
            if nx2 <= nx1 or ny2 <= ny1:
                nx1, ny1, nx2, ny2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)

            face_img = img.crop((nx1, ny1, nx2, ny2))
            face_img.thumbnail((256, 256), Image.Resampling.LANCZOS)
            if face_img.mode in ('RGBA', 'LA') or (face_img.mode == 'P' and 'transparency' in face_img.info):
                face_img = face_img.convert('RGB')
            face_img.save(cache_file, 'JPEG', quality=85)
            return FileResponse(cache_file, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise
