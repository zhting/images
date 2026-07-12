"""Organization routes: places, tags, best_shots, on_this_day, documents"""
import os
import sys
import collections
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks
from PIL import Image

from core.tasks import runner
from api.helpers import compute_file_hash
from api.state import get_db, get_store, get_model, state, invalidate_all_caches
from api.helpers import filter_locked_items, cosine_similarity

import logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["organize"])


# ---------------------------------------------------------------------------
# Best Shots
# ---------------------------------------------------------------------------
@router.get("/files/organize/best_shots")
def get_best_shots(limit: int = 15, offset_index: int = 0):
    try:
        db = get_db()
        store = get_store()
        locked_folders = store.get_locked_folders()

        # P1a stage 2: burst detection only needs (path, time, score) —
        # stream two columns from SQL instead of full metadata for the
        # whole library. Algorithm below is unchanged.
        if store.count_photos() > 0:
            photos = store.get_photo_times(('photo', 'video'),
                                           locked_prefixes=locked_folders)
        else:
            all_files = db.get_all_files_with_time(include_embeddings=False)
            photos = [f for f in all_files if f.get('tag', 'photo') in ['photo', 'video']]
            photos = filter_locked_items(photos, locked_folders, 'file_path')
            photos.sort(key=lambda x: x['captured_time'])

        time_bursts = []
        current_burst = []
        for photo in photos:
            if not current_burst:
                current_burst.append(photo)
            else:
                prev = current_burst[-1]
                time_diff = abs(photo.get('captured_time', 0) - prev.get('captured_time', 0))
                if time_diff < 5.0:
                    current_burst.append(photo)
                else:
                    if len(current_burst) > 1:
                        time_bursts.append(current_burst)
                    current_burst = [photo]
        if len(current_burst) > 1:
            time_bursts.append(current_burst)

        MAX_BURST_SIZE = 40
        valid_time_bursts = [b for b in time_bursts if len(b) <= MAX_BURST_SIZE]
        valid_time_bursts.reverse()

        matched_groups = []
        next_offset = -1
        total_candidates = len(valid_time_bursts)
        BATCH_SIZE = 50
        MAX_BATCHES_PER_REQUEST = 4
        max_batches_scanned = 0
        current_offset = offset_index

        while current_offset < total_candidates:
            if max_batches_scanned >= MAX_BATCHES_PER_REQUEST:
                next_offset = current_offset
                break

            batch_end = min(current_offset + BATCH_SIZE, total_candidates)
            batch_bursts = valid_time_bursts[current_offset:batch_end]

            batch_paths = set()
            for b in batch_bursts:
                for p in b:
                    batch_paths.add(p['file_path'])
            embeddings_map = db.get_embeddings_for_files(list(batch_paths))

            for i, burst in enumerate(batch_bursts):
                current_sim_group = []
                local_groups = []

                for photo in burst:
                    p = photo.copy()
                    p['embedding'] = embeddings_map.get(p['file_path'])
                    if not current_sim_group:
                        current_sim_group.append(p)
                        continue
                    prev = current_sim_group[-1]
                    time_diff = abs(p.get('captured_time', 0) - prev.get('captured_time', 0))
                    sim = cosine_similarity(p.get('embedding'), prev.get('embedding'))
                    threshold = 0.85 if time_diff <= 2.0 else 0.92
                    if sim >= threshold:
                        current_sim_group.append(p)
                    else:
                        if len(current_sim_group) > 1:
                            local_groups.append(current_sim_group)
                        current_sim_group = [p]
                if len(current_sim_group) > 1:
                    local_groups.append(current_sim_group)

                if local_groups:
                    for grp in local_groups:
                        best_idx = max(range(len(grp)), key=lambda idx: grp[idx].get('aesthetic_score', 0.0))
                        processed = []
                        for idx, p in enumerate(grp):
                            p['is_best'] = (idx == best_idx)
                            p['basename'] = os.path.basename(p['file_path'])
                            p.pop('embedding', None)
                            processed.append(p)
                        processed.sort(key=lambda x: (not x['is_best'], x['captured_time']))
                        matched_groups.append({"items": processed, "best_score": grp[best_idx].get('aesthetic_score', 0.0)})

                if len(matched_groups) >= limit:
                    next_offset = current_offset + i + 1
                    break

            if len(matched_groups) >= limit:
                break
            current_offset += BATCH_SIZE
            max_batches_scanned += 1

        if next_offset == -1 and current_offset < total_candidates:
            next_offset = current_offset

        for idx, grp in enumerate(matched_groups):
            grp['id'] = offset_index + idx

        return {
            "groups": matched_groups,
            "next_offset": next_offset if next_offset != -1 and next_offset < total_candidates else -1,
            "has_more": next_offset != -1 and next_offset < total_candidates
        }
    except Exception:
        import traceback
        traceback.print_exc()
        raise


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
@router.get("/files/organize/documents")
def get_documents(page: int = 1, page_size: int = 30):
    try:
        store = get_store()
        # P1a stage 2: paged SQL replaces full-collection scan.
        if store.count_photos() > 0:
            locked = store.get_locked_folders()
            items, total = store.get_photos_by_tag(
                'document', page_size, (page - 1) * page_size, locked_prefixes=locked)
            return {"items": items, "total": total, "page": page, "page_size": page_size}

        db = get_db()
        all_files = db.get_all_files_with_time()
        for f in all_files:
            ct = f.get('captured_time', 0)
            if ct is None:
                ct = 0
            if hasattr(ct, 'item'):
                ct = ct.item()
            elif hasattr(ct, '__len__') and not isinstance(ct, str) and len(ct) > 0:
                ct = ct[0]
            f['captured_time'] = float(ct)

        docs = [f for f in all_files if f.get('tag') == 'document']
        docs.sort(key=lambda x: x['captured_time'], reverse=True)
        for f in docs:
            f['basename'] = os.path.basename(f['file_path'])
            f.pop('embedding', None)

        start = (page - 1) * page_size
        return {"items": docs[start:start + page_size], "total": len(docs), "page": page, "page_size": page_size}
    except Exception:
        raise


# ---------------------------------------------------------------------------
# Places
# ---------------------------------------------------------------------------
@router.get("/files/organize/places")
def get_places():
    try:
        db = get_db()
        store = get_store()
        locked_folders = store.get_locked_folders()

        # P1a stage 2: GROUP BY replaces scan + Python aggregation; the
        # query is fast enough that the cache layer is bypassed entirely.
        if store.count_photos() > 0:
            return store.get_places_summary(locked_prefixes=locked_folders)

        if locked_folders:
            state.places_cache = None
        if state.places_cache is not None:
            return state.places_cache

        all_files = db.get_all_files_with_time()
        all_files = filter_locked_items(all_files, locked_folders)

        places = {}
        for f in all_files:
            tag = f.get("tag", "photo")
            if tag in ('document', 'screenshot'):
                continue
            loc = f.get("location_info", {})
            city = loc.get("city", "")
            province = loc.get("province", "")
            if not city and not province:
                continue
            key = f"{city}, {province}" if city and province else (city or province)
            lat = loc.get("latitude")
            lon = loc.get("longitude")
            captured_time = f.get("captured_time", f.get("last_modified", 0))
            file_path = f.get("file_path", "")

            if key not in places:
                places[key] = {
                    "lat_sum": 0.0, "lon_sum": 0.0, "count_gps": 0,
                    "best_file": None, "best_time": 0, "count": 0,
                    "city": city, "province": province
                }
            p = places[key]
            p["count"] += 1
            if lat is not None and lon is not None:
                p["lat_sum"] += lat
                p["lon_sum"] += lon
                p["count_gps"] += 1
            if captured_time and captured_time > p["best_time"]:
                p["best_time"] = captured_time
                p["best_file"] = file_path

        result = []
        for loc_name, p in places.items():
            if p["count"] == 0:
                continue
            avg_lat = p["lat_sum"] / p["count_gps"] if p["count_gps"] > 0 else None
            avg_lon = p["lon_sum"] / p["count_gps"] if p["count_gps"] > 0 else None
            result.append({
                "name": str(loc_name), "count": p["count"],
                "cover": {"file_path": p["best_file"] or "", "basename": os.path.basename(p["best_file"]) if p["best_file"] else ""},
                "latitude": avg_lat, "longitude": avg_lon,
                "province": p["province"], "city": p["city"], "items": []
            })
        result.sort(key=lambda x: x['count'], reverse=True)
        state.places_cache = result
        return result
    except Exception:
        raise


@router.post("/files/organize/places/rescan_cities")
def rescan_cities():
    try:
        from core.location_processor import LocationProcessor
        import reverse_geocoder as rg

        db = get_db()
        loc_proc = LocationProcessor()
        all_files = db.get_all_files_with_time()

        total = len(all_files)
        updated = 0
        skipped = 0
        no_gps = 0
        already_ok = 0

        for f in all_files:
            loc = f.get('location_info', {})
            lat = loc.get('latitude')
            lon = loc.get('longitude')
            current_city = loc.get('city', '')
            file_path = f.get('file_path', '')

            if lat is None or lon is None:
                path_info = loc_proc.infer_from_path(file_path)
                if path_info and path_info.get('city'):
                    new_info = {
                        "city": path_info['city'], "province": path_info.get('province', ''),
                        "country_code": "CN", "source": "path_rescan",
                        "latitude": path_info.get('latitude'), "longitude": path_info.get('longitude'),
                    }
                    db.update_location(file_path, new_info)
                    updated += 1
                else:
                    no_gps += 1
                continue

            is_china = (18.0 <= lat <= 54.0) and (73.0 <= lon <= 136.0)
            if is_china:
                match = loc_proc.match_nearest_china_city(lat, lon)
                if match:
                    if current_city == match['city']:
                        already_ok += 1
                        continue
                    db.update_location(file_path, {
                        "city": match['city'], "province": match['province'],
                        "country_code": "CN", "source": "haversine_rescan",
                        "latitude": lat, "longitude": lon,
                    })
                    updated += 1
                else:
                    try:
                        results = rg.search((lat, lon))
                        if results:
                            res = results[0]
                            city_zh = loc_proc._translate_cached(res.get("name", ""))
                            province_zh = loc_proc._translate_cached(res.get("admin1", ""))
                            city_clean = city_zh.rstrip("市区县")
                            if city_clean and city_clean != current_city:
                                db.update_location(file_path, {
                                    "city": city_clean, "province": province_zh,
                                    "country_code": "CN", "source": "rg_rescan",
                                    "latitude": lat, "longitude": lon,
                                })
                                updated += 1
                            else:
                                already_ok += 1
                        else:
                            skipped += 1
                    except Exception:
                        skipped += 1
            else:
                try:
                    results = rg.search((lat, lon))
                    if results:
                        res = results[0]
                        city_zh = loc_proc._translate_cached(res.get("name", ""))
                        province_zh = loc_proc._translate_cached(res.get("admin1", ""))
                        if city_zh and city_zh != current_city:
                            db.update_location(file_path, {
                                "city": city_zh, "province": province_zh,
                                "country_code": res.get("cc", ""), "source": "rg_world_rescan",
                                "latitude": lat, "longitude": lon,
                            })
                            updated += 1
                        else:
                            already_ok += 1
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1

        invalidate_all_caches()
        return {"total": total, "updated": updated, "already_ok": already_ok, "no_gps": no_gps, "skipped": skipped}
    except Exception:
        import traceback
        traceback.print_exc()
        raise


@router.get("/files/organize/on_this_day")
def get_on_this_day():
    try:
        store = get_store()
        if store.count_photos() > 0:
            now = datetime.now()
            locked = store.get_locked_folders()
            photos = store.get_on_this_day(now.month, now.day, locked_prefixes=locked)
            years_group = {}
            for f in photos:
                y = datetime.fromtimestamp(f['captured_time']).year
                years_group.setdefault(y, []).append(f)
            return [{"year": y, "photos": years_group[y]}
                    for y in sorted(years_group, reverse=True)]

        if state.on_this_day_cache is not None:
            return state.on_this_day_cache

        db = get_db()
        files = db.get_all_files_with_time()
        now = datetime.now()

        years_group = {}
        for f in files:
            ts = f.get('captured_time', 0)
            if not ts:
                continue
            try:
                dt = datetime.fromtimestamp(ts)
                if dt.month == now.month and dt.day == now.day:
                    y = dt.year
                    if y not in years_group:
                        years_group[y] = []
                    f.pop('embedding', None)
                    f['basename'] = os.path.basename(f['file_path'])
                    years_group[y].append(f)
            except Exception:
                continue

        result = []
        for y in sorted(years_group.keys(), reverse=True):
            photos = years_group[y]
            photos.sort(key=lambda x: x.get('captured_time', 0), reverse=True)
            result.append({"year": y, "photos": photos})

        state.on_this_day_cache = result
        return result
    except Exception as e:
        logger.error(f"OnThisDay Error: {e}")
        return []


@router.get("/files/organize/places/{location_name}")
def get_place_photos(location_name: str):
    try:
        db = get_db()

        store = get_store()
        if store.count_photos() > 0:
            locked = store.get_locked_folders()
            if location_name == "all_map_data":
                return store.get_map_points(locked_prefixes=locked)
            return store.get_photos_by_place(location_name, locked_prefixes=locked)

        if location_name == "all_map_data":
            if state.map_data_cache is not None:
                return state.map_data_cache
            all_files = db.get_all_files_with_time()
            photos = []
            for f in all_files:
                tag = f.get("tag", "photo")
                if tag in ['document', 'screenshot']:
                    continue
                loc = f.get("location_info", {})
                lat = loc.get("latitude")
                lon = loc.get("longitude")
                if lat is not None and lon is not None:
                    file_path = f.get("file_path", "")
                    photos.append({
                        "file_path": file_path, "basename": os.path.basename(file_path),
                        "latitude": lat, "longitude": lon, "tag": tag
                    })
            state.map_data_cache = photos
            return photos

        parts = location_name.split(", ")
        target_city = parts[0] if len(parts) > 0 else location_name
        target_province = parts[1] if len(parts) > 1 else ""

        all_files = db.get_all_files_with_time()
        photos = []
        for f in all_files:
            tag = f.get("tag", "photo")
            if tag in ['document', 'screenshot']:
                continue
            loc = f.get("location_info", {})
            city = loc.get("city", "")
            province = loc.get("province", "")
            match = False
            if len(parts) == 2:
                match = city == target_city and province == target_province
            else:
                match = city == location_name or province == location_name
            if match:
                item = {
                    "file_path": f.get("file_path", ""), "captured_time": f.get("captured_time", 0),
                    "last_modified": f.get("last_modified", 0), "aesthetic_score": f.get("aesthetic_score", 0.0),
                    "tag": tag, "city": city, "province": province,
                    "country": loc.get("country_code", ""),
                    "latitude": loc.get("latitude"), "longitude": loc.get("longitude")
                }
                item['basename'] = os.path.basename(item["file_path"])
                photos.append(item)

        photos.sort(key=lambda x: x.get('captured_time', 0), reverse=True)
        return photos
    except Exception:
        import traceback
        traceback.print_exc()
        raise


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------
@router.get("/files/organize/tags")
def get_tags(page: int = 1, page_size: int = 40):
    try:
        db = get_db()
        store = get_store()
        locked_folders = store.get_locked_folders()

        if locked_folders:
            state.tags_cache = None
        if state.tags_cache is not None:
            final_list = state.tags_cache
        else:
            if store.count_photos() > 0:
                # P1a stage 2: read only the auto_tags column.
                tag_counts = store.get_auto_tag_counts(locked_prefixes=locked_folders)
            else:
                files = db.get_all_files_with_time()
                files = filter_locked_items(files, locked_folders)

                tag_counts = collections.defaultdict(int)
                for f in files:
                    t_list = f.get('auto_tags', [])
                    if isinstance(t_list, str):
                        t_list = t_list.split(',') if t_list else []
                    for t in t_list:
                        if t:
                            tag_counts[t] += 1

            # Load translation map
            import json
            zh_map = {}
            try:
                if getattr(sys, 'frozen', False):
                    from core.paths import get_app_dir
                    assets_dir = os.path.join(get_app_dir(), "assets")
                else:
                    from api.state import src_dir
                    assets_dir = os.path.join(src_dir, "..", "assets")

                map_path = os.path.join(assets_dir, "tags_zh.json")
                if os.path.exists(map_path):
                    with open(map_path, "r", encoding="utf-8") as f:
                        zh_map = json.load(f)
            except Exception:
                pass

            final_list = [{"name": t, "display_name": zh_map.get(t, t), "count": c}
                          for t, c in tag_counts.items()]
            final_list.sort(key=lambda x: x['count'], reverse=True)
            state.tags_cache = final_list

        total = len(final_list)
        start = (page - 1) * page_size
        items = final_list[start:start + page_size] if start < total else []
        return {"items": items, "total": total, "page": page, "page_size": page_size}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "error": str(e)}


@router.get("/debug/recover_tags")
def debug_recover_tags(background_tasks: BackgroundTasks):
    def run_recovery():
        try:
            db = get_db()
            model = get_model()
            from core.tag_generator import TagGenerator
            tag_gen = TagGenerator(model)
            files = db.get_all_files_with_time()
            for f in files:
                path = f.get('file_path')
                if not path or not os.path.exists(path):
                    continue
                try:
                    img = Image.open(path).convert('RGB')
                    tags = tag_gen.generate_tags(img)
                    if tags:
                        res = db.collection.get(ids=[path], include=["metadatas"])
                        if res and res['metadatas']:
                            meta = res['metadatas'][0]
                            meta['auto_tags'] = ",".join(tags)
                            db.collection.update(ids=[path], metadatas=[meta])
                except Exception:
                    pass
            state.tags_cache = None
        except Exception as e:
            logger.error(f"[RECOVERY] Global Error: {e}")

    background_tasks.add_task(run_recovery)
    return {"status": "Recovery started in background"}


@router.get("/files/organize/tags/{tag_name}")
def get_tag_photos(tag_name: str):
    try:
        store = get_store()
        if store.count_photos() > 0:
            return store.get_photos_by_auto_tag(
                tag_name, locked_prefixes=store.get_locked_folders())

        db = get_db()
        files = db.get_all_files_with_time()
        result = []
        for f in files:
            tags = f.get('auto_tags', [])
            if tag_name in tags:
                f.pop('embedding', None)
                f['basename'] = os.path.basename(f['file_path'])
                result.append(f)
        result.sort(key=lambda x: x.get('captured_time', 0), reverse=True)
        return result
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------
def _hash_backfill(task):
    """Fill in content hashes for photos indexed before hashing existed
    (every pre-existing row carries the legacy 'hash' placeholder)."""
    store = get_store()
    total = store.count_unhashed_photos()
    done = 0
    while not task.cancelled:
        batch = store.get_unhashed_photo_paths(limit=200)
        if not batch:
            break
        for path in batch:
            if task.cancelled:
                return
            try:
                h = compute_file_hash(path) if os.path.exists(path) else ""
            except Exception:
                h = ""
            store.set_photo_hash(path, h)
            done += 1
        if total:
            task.report(done / total, f"已计算 {done}/{total}")


@router.get("/files/organize/duplicates")
def get_duplicates():
    """Duplicate groups by exact content hash. If legacy rows still lack
    real hashes, kick off (or report) the backfill task instead."""
    store = get_store()
    pending = store.count_unhashed_photos()
    if pending > 0:
        task = runner.submit("hash_backfill", _hash_backfill)
        return {"ready": False, "pending": pending,
                "task": task.to_dict()}
    locked = store.get_locked_folders()
    groups = store.get_duplicate_groups(locked_prefixes=locked)
    return {"ready": True, "groups": groups,
            "total_groups": len(groups),
            "reclaimable": sum(g["count"] - 1 for g in groups)}
