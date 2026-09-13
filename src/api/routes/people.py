"""People / face recognition routes."""
import os

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api.state import get_db, get_store, state
from api.models import PersonNameUpdate
from api.helpers import filter_locked_items
from core.tasks import runner

router = APIRouter(tags=["people"])

import logging
logger = logging.getLogger(__name__)


def _cluster_faces(store, force_refresh: bool, should_stop=None):
    """Assign person_ids to unclustered faces.

    CPU-bound and O(minutes) on a large library, so this never runs on a
    request thread — see get_people below. ``should_stop`` is polled between
    stages so a cancelled task stops without leaving half-written clusters.
    """
    from sklearn.cluster import DBSCAN
    import collections

    all_faces = store.get_all_faces()
    if not all_faces:
        return 0

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

        if should_stop and should_stop():
            return 0

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

    if should_stop and should_stop():
        return 0
    if updates:
        store.batch_update_face_clusters(updates)
    return len(updates)


def _read_clusters(store):
    """Current clusters, locked folders filtered out, cached in process."""
    clusters = store.get_clustered_people()
    clusters = filter_locked_items(clusters, store.get_locked_folders(),
                                   'cover_file_path')
    state.people_cache = clusters
    return clusters


def _submit_clustering(force_refresh: bool):
    """Queue a clustering pass on the shared serial task runner.

    The runner dedupes by name, so repeated refreshes while one is in
    flight join the running task instead of starting a second DBSCAN over
    the same embeddings.
    """
    def _job(task):
        task.report(0.05, "读取人脸特征...")
        changed = _cluster_faces(store=get_store(), force_refresh=force_refresh,
                                 should_stop=lambda: task.cancelled)
        task.report(0.9, "整理人物分组...")
        _read_clusters(get_store())
        task.report(1.0, f"完成，更新 {changed} 张人脸")

    return runner.submit("face_cluster", _job)


@router.get("/files/organize/people")
def get_people(force_refresh: bool = False, page: int = 1, page_size: int = 100):
    """Return known people, paged.

    Clustering itself is a background task: DBSCAN over every face
    embedding in the library takes minutes on a large collection, and
    running it inline held a request thread for the whole time (and let
    two concurrent refreshes duplicate the work). This endpoint returns
    whatever clusters exist right now, plus a task_id to poll when a pass
    was started.
    """
    try:
        store = get_store()

        if force_refresh:
            state.people_cache = None
            task = _submit_clustering(force_refresh=True)
            return {"items": [], "total": 0, "page": page, "page_size": page_size,
                    "task_id": task.id, "clustering": True}

        # An empty list is deliberately treated as "no cache": caching it
        # would pin the view to "no people" for the rest of the process if a
        # clustering pass were still in flight or had failed. Re-reading is a
        # single GROUP BY over the faces table.
        clusters = state.people_cache or _read_clusters(store)

        task_id = None
        clustering = False
        if not clusters and store.count_unclustered_faces() > 0:
            # Nothing grouped yet but faces are indexed — kick off a pass and
            # let the client poll instead of blocking a request thread on it.
            # submit() dedupes by name, so concurrent polls join the running
            # task rather than starting a second DBSCAN.
            task = _submit_clustering(force_refresh=False)
            task_id, clustering = task.id, True

        start = (page - 1) * page_size
        items = clusters[start:start + page_size]
        return {"items": items, "total": len(clusters), "page": page,
                "page_size": page_size, "task_id": task_id, "clustering": clustering}
    except Exception:
        logger.exception("unhandled error")
        raise


@router.get("/files/organize/people/{person_id}")
def get_person_photos(person_id: int):
    try:
        store = get_store()
        db = get_db()
        faces = store.get_faces_by_person(person_id)
        # P1a stage 2: hydrate only this person's paths instead of
        # loading the entire library into a dict.
        if store.has_photos():
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
    except Exception:
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
    except Exception:
        raise


@router.post("/files/organize/people/merge")
def merge_people(req: dict):
    """Merge one detected person cluster into another."""
    source_id = req.get("source_id")
    target_id = req.get("target_id")
    if source_id is None or target_id is None or source_id == target_id:
        raise HTTPException(status_code=422, detail="need distinct source_id and target_id")
    store = get_store()
    moved = store.merge_persons(int(source_id), int(target_id))
    if moved == 0:
        raise HTTPException(status_code=404, detail="source person has no faces")
    return {"status": "ok", "moved_faces": moved, "target_id": target_id}


@router.delete("/files/organize/people/{person_id}")
def delete_person_cluster(person_id: int):
    try:
        store = get_store()
        store.reset_person_cluster(person_id)
        state.people_cache = None
        return {"status": "ok"}
    except Exception:
        raise


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
    except Exception:
        logger.exception("unhandled error")
        raise
