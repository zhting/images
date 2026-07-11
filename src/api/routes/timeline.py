"""Timeline routes: /timeline, /timeline/dates"""
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException

from api.state import get_db, get_store, state
from api.helpers import filter_locked_items, cosine_similarity

router = APIRouter(tags=["timeline"])


@router.get("/timeline/dates")
def get_timeline_dates():
    try:
        db = get_db()
        store = get_store()
        locked_folders = store.get_locked_folders()

        # P1a: indexed SQL replaces collection scans / Chroma-internals SQL.
        # Lock filtering is pushed into WHERE, so this path is also correct
        # (legacy fast path ignored locked folders entirely).
        if store.count_photos() > 0:
            return store.get_timeline_dates(locked_prefixes=locked_folders)

        fast_dates = db.get_timeline_dates_stats()
        if fast_dates is not None and not locked_folders:
            return fast_dates

        # Fallback
        photos = []
        if state.timeline_cache is not None:
            photos = state.timeline_cache
        else:
            all_files = db.get_all_files_with_time(include_embeddings=False)
            all_files = filter_locked_items(all_files, locked_folders, 'file_path')
            for f in all_files:
                ct = f.get('captured_time', 0)
                if hasattr(ct, 'item'):
                    ct = ct.item()
                elif hasattr(ct, '__len__') and not isinstance(ct, str) and len(ct) > 0:
                    ct = ct[0]
                f['captured_time'] = float(ct)
            all_files.sort(key=lambda x: x['captured_time'], reverse=True)
            photos = [f for f in all_files
                      if f.get('tag') not in ['document', 'screenshot', 'trash', 'error']]
            state.timeline_cache = photos

        dates = []
        if not photos:
            return dates

        current_ym = None
        count_in_group = 0
        group_start_index = 0

        for idx, item in enumerate(photos):
            ts = item.get('captured_time', 0)
            if ts <= 0:
                ym = "Unknown"
            else:
                dt = datetime.fromtimestamp(ts)
                ym = dt.strftime("%Y-%m")

            if ym != current_ym:
                if current_ym is not None:
                    dates.append({"key": current_ym, "index": group_start_index, "count": count_in_group})
                current_ym = ym
                group_start_index = idx
                count_in_group = 0
            count_in_group += 1

        if current_ym:
            dates.append({"key": current_ym, "index": group_start_index, "count": count_in_group})
        return dates

    except Exception as e:
        print(f"Error in get_timeline_dates: {e}")
        return []


@router.get("/timeline")
def get_timeline(page: int = 1, size: int = 50):
    try:
        db = get_db()
        store = get_store()
        locked_folders = store.get_locked_folders()
        offset = (page - 1) * size

        # P1a store-first path: paged SQL with lock filtering in WHERE.
        # Legacy path filtered locked items AFTER pagination, so locked
        # photos consumed page slots and inflated totals.
        if store.count_photos() > 0:
            page_items, total_photos = store.get_timeline_page(
                size, offset, locked_prefixes=locked_folders)
        else:
            page_items, total_photos = db.get_timeline_page(limit=size, offset=offset)

        if page_items is None:
            photos = []
            if state.timeline_cache is not None:
                photos = state.timeline_cache
            else:
                all_files = db.get_all_files_with_time(include_embeddings=False)
                for f in all_files:
                    ct = f.get('captured_time', 0)
                    if hasattr(ct, 'item'):
                        ct = ct.item()
                    elif hasattr(ct, '__len__') and not isinstance(ct, str) and len(ct) > 0:
                        ct = ct[0]
                    f['captured_time'] = float(ct)
                all_files.sort(key=lambda x: x['captured_time'], reverse=True)
                photos = [f for f in all_files
                          if f.get('tag') not in ['document', 'screenshot', 'trash', 'error']]
                store = get_store()
                locked_folders = store.get_locked_folders()
                photos = filter_locked_items(photos, locked_folders, 'file_path')
                state.timeline_cache = photos

            total_photos = len(photos)
            start_idx = offset
            page_items = photos[start_idx:start_idx + size] if start_idx < total_photos else []

        if not page_items:
            return {"items": [], "total": total_photos, "page": page, "size": size}

        # Fetch embeddings for burst detection
        page_paths = [p['file_path'] for p in page_items]
        embeddings_map = db.get_embeddings_for_files(page_paths)
        for p in page_items:
            p['embedding'] = embeddings_map.get(p['file_path'])

        grouped_results = []
        current_group = [page_items[0]]

        for i in range(1, len(page_items)):
            curr = page_items[i]
            prev = page_items[i - 1]
            t_curr = float(curr.get('captured_time', 0))
            t_prev = float(prev.get('captured_time', 0))
            time_diff = abs(t_curr - t_prev)

            is_burst = False
            if time_diff < 5.0:
                sim = cosine_similarity(curr.get('embedding'), prev.get('embedding'))
                threshold = 0.85
                if time_diff > 2.0:
                    threshold = 0.92
                if sim >= threshold:
                    is_burst = True

            if is_burst:
                current_group.append(curr)
            else:
                best_shot = max(current_group, key=lambda p: float(p.get('aesthetic_score', 0.0)))
                best_shot['similar_count'] = len(current_group) - 1
                best_shot['basename'] = os.path.basename(best_shot['file_path'])
                best_shot.pop('embedding', None)
                grouped_results.append(best_shot)
                current_group = [curr]

        # Last group
        if current_group:
            best_shot = max(current_group, key=lambda p: float(p.get('aesthetic_score', 0.0)))
            best_shot['similar_count'] = len(current_group) - 1
            best_shot['basename'] = os.path.basename(best_shot['file_path'])
            best_shot.pop('embedding', None)
            grouped_results.append(best_shot)

        # Final privacy filter
        store = get_store()
        locked_folders = store.get_locked_folders()
        grouped_results = filter_locked_items(grouped_results, locked_folders)

        return {"items": grouped_results, "total": total_photos, "page": page, "size": size}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise
