import chromadb
import os

import logging
logger = logging.getLogger(__name__)

class VectorDB:
    # P1a: optional SQLiteStore mirror; metadata writes are duplicated into
    # the photos table so reads can move to indexed SQL queries.
    metadata_sink = None

    def __init__(self, db_path="./search.db", collection_name="LocalPhotoGallery"):
        # ChromaDB creates a folder, not a single file usually, unless using sqlite mode extensively.
        # But allow passing path.
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection_name = collection_name
        self._all_files_cache = None
        self._all_files_with_embeddings_cache = None
        self._cache_time = 0
        self._timeline_total_cache = None
        self._timeline_total_cache_time = 0
        self._init_collection()

    def is_path_locked(self, path: str, locked_folders: list) -> bool:
        """
        Duplicate logic from SQLiteStore to avoid circular imports if needed,
        or just keep it here as a utility.
        """
        if not locked_folders:
            return False
            
        norm_path = path.replace("\\", "/").rstrip("/")
        for lp in locked_folders:
            if norm_path == lp or norm_path.startswith(lp + "/"):
                return True
        return False

    def invalidate_cache(self):
        self._all_files_cache = None
        self._all_files_with_embeddings_cache = None
        self._cache_time = 0
        self._timeline_total_cache = None
        self._timeline_total_cache_time = 0

    def _init_collection(self):
        # get_or_create_collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"} # Use cosine similarity
        )

    def reset_collection(self):
        """
        Deletes and re-initializes the collection.
        This effectively clears all data.
        """
        try:
            self.client.delete_collection(self.collection_name)
        except Exception as e:
            logger.warning(f"[VectorDB] Warning deleting collection: {e}")
        self._init_collection()

    def delete_by_path(self, file_path: str):
        # Delete all vectors where metadata file_path matches
        # This covers both single images (id=path) and video segments (id=path#1, metadata.file_path=path)
        self.invalidate_cache()
        self.collection.delete(where={"file_path": file_path})
        if self.metadata_sink:
            try:
                self.metadata_sink.delete_photo(file_path)
            except Exception as e:
                logger.error(f"[VectorDB] metadata mirror failed (delete {file_path}): {e}")

    def create_collection_with_schema(self):
        # Chroma handles schema dynamically
        pass

    def insert(self, vector: list[float], file_path: str, file_hash: str, last_modified: int, captured_time: int = 0, aesthetic_score: float = 0.0, tag: str = "photo", location_info: dict = None, auto_tags: list = None, custom_id: str = None):
        # Chroma requires ID. We can use file_path or a hash as ID if unique.
        # Using file_path as ID allows easy deduplication/updates.
        
        # metadata
        meta = {
            "file_path": file_path,
            "file_hash": file_hash,
            "last_modified": last_modified,
            "captured_time": captured_time,
            "aesthetic_score": aesthetic_score,
            "tag": tag
        }
        
        if location_info:
            meta["city"] = location_info.get("city", "")
            meta["province"] = location_info.get("province", "")
            meta["country"] = location_info.get("country_code", "")
            # Store coordinates as float in metadata (Chroma supports int/float/str/bool)
            if location_info.get("latitude") is not None:
                meta["latitude"] = float(location_info.get("latitude"))
            if location_info.get("longitude") is not None:
                meta["longitude"] = float(location_info.get("longitude"))
            
        if auto_tags:
            meta["auto_tags"] = ",".join(auto_tags) # store as comma separated string
        
        # Use custom_id if provided (e.g. for video segments "path#0"), else file_path
        doc_id = custom_id if custom_id else file_path

        self.invalidate_cache()
        self.collection.upsert(
            embeddings=[vector],
            metadatas=[meta],
            ids=[doc_id] 
        )
        if self.metadata_sink:
            try:
                self.metadata_sink.upsert_photos([{
                    "file_path": file_path, "file_hash": file_hash,
                    "last_modified": last_modified, "captured_time": captured_time,
                    "aesthetic_score": aesthetic_score, "tag": tag,
                    "location_info": location_info, "auto_tags": auto_tags,
                }])
            except Exception as e:
                logger.error(f"[VectorDB] metadata mirror failed for {file_path}: {e}")

    def insert_batch(self, vectors: list[list[float]], file_paths: list[str], last_modifieds: list[int], captured_times: list[int] = None, aesthetic_scores: list[float] = None, tags: list[str] = None):
        """
        Batch insertion for efficiency.
        Note: Smart analysis (tags, location) usually happens per-image, so batch insert might not be used heavily yet.
        """
        if captured_times is None:
             captured_times = [0] * len(file_paths)
        if aesthetic_scores is None:
             aesthetic_scores = [0.0] * len(file_paths)
        if tags is None:
             tags = ["photo"] * len(file_paths)
             
        metadatas = [{
            "file_path": fp, 
            "file_hash": "hash", 
            "last_modified": lm,
            "captured_time": ct,
            "aesthetic_score": sc,
            "tag": tg
        } for fp, lm, ct, sc, tg in zip(file_paths, last_modifieds, captured_times, aesthetic_scores, tags, strict=False)]
        
        self.invalidate_cache()
        self.collection.upsert(
            embeddings=vectors,
            metadatas=metadatas,
            ids=file_paths
        )
        if self.metadata_sink:
            try:
                self.metadata_sink.upsert_photos(metadatas)
            except Exception as e:
                logger.error(f"[VectorDB] metadata mirror failed (batch): {e}")

    def search(self, vector: list[float], top_k: int = 50):
        logger.info(f"[VectorDB] Searching with top_k={top_k}")
        results = self.collection.query(
            query_embeddings=[vector],
            n_results=top_k,
            include=["metadatas", "distances", "documents"]
        )
        
        # Debug print
        # print(f"[VectorDB] Raw results keys: {results.keys()}")
        
        formatted = []
        
        # Check if we have ids
        if not results or not results.get('ids'):
            logger.info("[VectorDB] No ids returned.")
            return formatted
            
        ids_list = results['ids']
        if not ids_list or ids_list[0] is None:
             logger.info("[VectorDB] Empty ids list.")
             return formatted
             
        ids = ids_list[0]
        distances = results.get('distances', [[]])[0] if results.get('distances') else [0.0] * len(ids)
        
        # Handle metadatas safely
        metadatas_list = results.get('metadatas')
        if metadatas_list and metadatas_list[0] is not None:
            metadatas = metadatas_list[0]
        else:
            logger.warning("[VectorDB] Warning: No metadatas found, using empty dicts.")
            metadatas = [{}] * len(ids)
        
        for i, _id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            if meta is None: 
                meta = {}
                
            # P1a stage 3: flat result list. The historical [formatted]
            # single-element nesting (Milvus-era API shape) forced every
            # caller to unwrap results[0].
            formatted.append({
                "id": _id,
                "distance": distances[i] if i < len(distances) else 0.0,
                "file_path": meta.get("file_path", _id),
                "tag": meta.get("tag", "photo"),
            })
            
        return formatted
    


    def count(self):
        return self.collection.count()

    def get_stats(self):
        """
        Returns dictionary with counts by tag.
        Optimized to avoid fetching all metadatas locally, and caches the result for 15 minutes.
        Uses direct SQLite queries for large collections where ChromaDB SDK is too slow.
        """
        import time
        current_time = time.time()
        
        # Initialize cache attributes if they don't exist
        if not hasattr(self, '_stats_cache'):
            self._stats_cache = None
        if not hasattr(self, '_stats_cache_time'):
            self._stats_cache_time = 0
            
        # Return cached stats if valid (15 minutes = 900 seconds)
        if self._stats_cache and (current_time - self._stats_cache_time < 900):
            return self._stats_cache
            
        try:
            total_count = self.collection.count()
            stats = {
                "total": total_count,
                "photo": 0,
                "video": 0,
                "screenshot": 0,
                "document": 0,
                "error": 0
            }
            
            # Since Chroma uses SQLite internally, we can fast path the tag counts via sqlite directly
            # to avoid the heavy SDK overhead on 200k+ rows
            try:
                import sqlite3
                chroma_db_dir = self.client.get_settings().persist_directory
                if chroma_db_dir:
                    sqlite_path = os.path.join(chroma_db_dir, "chroma.sqlite3")
                    if os.path.exists(sqlite_path):
                        conn = sqlite3.connect(sqlite_path)
                        cursor = conn.cursor()
                        # Join embedding_metadata with segments and collections to filter correctly
                        # In latest Chroma, embedding_metadata.id links to segments.id
                        cursor.execute('''
                            SELECT m.string_value, count(*)
                            FROM embedding_metadata m
                            JOIN embeddings e ON m.id = e.id
                            JOIN segments s ON e.segment_id = s.id
                            JOIN collections c ON s.collection = c.id
                            WHERE c.name = ? AND m.key = 'tag'
                            GROUP BY m.string_value
                        ''', (self.collection_name,))
                        
                        rows = cursor.fetchall()
                        # If no rows via join (schema mismatch), try direct tag count as fallback
                        if not rows:
                             cursor.execute("SELECT string_value, count(*) FROM embedding_metadata WHERE key = 'tag' GROUP BY string_value")
                             rows = cursor.fetchall()

                        for tag_name, count in rows:
                            if tag_name in stats:
                                stats[tag_name] = count
                            else:
                                stats["other"] = stats.get("other", 0) + count
                        conn.close()
            except Exception as sql_e:
                logger.error(f"[VectorDB] Fast path SQL stats failed: {sql_e}, falling back to SDK")
                # Fallback to single count if direct SQL fails 
                # (We skip the SDK where clause since it takes 10s+, just return total)
                pass
                    
            # Calculate 'other' if needed (fallback case)
            known_total = sum(stats[t] for t in ["photo", "video", "screenshot", "document", "error"])
            if known_total < total_count and stats.get("other", 0) == 0:
                stats["other"] = total_count - known_total
                
            self._stats_cache = stats
            self._stats_cache_time = current_time
                
            return stats
        except Exception as e:
            logger.error(f"Stats Error: {e}")
            return {"total": 0}

    def get_all_files(self):
        """
        Returns a dictionary {file_path: last_modified} of all indexed files.
        """
        file_map = {}
        try:
            total_count = self.collection.count()
            if total_count == 0:
                return {}
                
            chunk_size = 10000 
            offset = 0
            
            while offset < total_count:
                results = self.collection.get(
                    limit=chunk_size,
                    offset=offset,
                    include=["metadatas"]
                )
                
                if results and results.get("ids"):
                    ids = results["ids"]
                    metadatas = results["metadatas"]
                    for i, _id in enumerate(ids):
                        meta = metadatas[i]
                        if meta:
                             # Default to 0 if not present
                             last_mod = meta.get("last_modified", 0) 
                             file_path = meta.get("file_path", _id)
                             file_map[file_path] = last_mod
                             
                offset += chunk_size
                
        except Exception as e:
            logger.error(f"[VectorDB] Error in get_all_files: {e}")
            
        return file_map

    def get_all_files_with_time(self, include_embeddings: bool = False):
        """
        Returns a list of dicts {file_path, captured_time, last_modified}.
        Modified to use chunking to avoid SQLite 'too many SQL variables' error
        when dealing with large datasets (>32k).
        """
        import time as _time
        CACHE_TTL = 60  # seconds
        current = _time.time()
        if not include_embeddings and self._all_files_cache and (current - self._cache_time) < CACHE_TTL:
            return self._all_files_cache
        if include_embeddings and self._all_files_with_embeddings_cache and (current - self._cache_time) < CACHE_TTL:
            return self._all_files_with_embeddings_cache

        file_list = []
        try:
            total_count = self.collection.count()
            if total_count == 0:
                return []
                
            chunk_size = 10000 
            offset = 0
            
            includes = ["metadatas"]
            if include_embeddings:
                includes.append("embeddings")
                
            while offset < total_count:
                # print(f"[VectorDB] Fetching chunk offset {offset} (limit {chunk_size})...")
                results = self.collection.get(
                    include=includes,
                    limit=chunk_size,
                    offset=offset
                )
                
                if results and results.get("ids"):
                    ids = results["ids"]
                    metadatas = results["metadatas"]
                    embeddings = results.get("embeddings") # might be None
                    
                    for i, _id in enumerate(ids):
                        meta = metadatas[i]
                        if not meta: continue
                        
                        file_path = meta.get("file_path", _id)
                        last_mod = meta.get("last_modified", 0) 
                        captured_time = meta.get("captured_time", last_mod) 
                        score = meta.get("aesthetic_score", 0.0)
                        tag = meta.get("tag", "photo")
                        
                        city = meta.get("city", "")
                        province = meta.get("province", "")
                        country = meta.get("country", "")
                        lat = meta.get("latitude")
                        lon = meta.get("longitude")
                        
                        location_obj = {
                            "city": city,
                            "province": province,
                            "country_code": country,
                            "latitude": lat,
                            "longitude": lon
                        }
                        
                        # Handle auto_tags specifically for compatibility
                        auto_tags_raw = meta.get("auto_tags", "")
                        auto_tags_list = []
                        if isinstance(auto_tags_raw, list):
                            auto_tags_list = auto_tags_raw
                        elif isinstance(auto_tags_raw, str) and auto_tags_raw:
                            auto_tags_list = [t.strip() for t in auto_tags_raw.split(',')]
                            
                        # Extract embeddings safely
                        e = None
                        if include_embeddings and embeddings is not None and len(embeddings) > i:
                            e = embeddings[i]
                            
                        item = {
                             "file_path": file_path,
                             "captured_time": captured_time,
                             "last_modified": last_mod,
                             "aesthetic_score": score,
                             "tag": tag,
                             "location_info": location_obj,
                             "auto_tags": auto_tags_list
                        }
                        if e is not None:
                            item["embedding"] = e
                            
                        file_list.append(item)
                
                offset += chunk_size
        except Exception as e:
            logger.error(f"[VectorDB] Fetch error (fallback to chunking): {e}")

        import time 
        current_time = time.time()
        self._cache_time = current_time
        if include_embeddings:
            self._all_files_with_embeddings_cache = file_list
            self._all_files_cache = [{k: v for k, v in f.items() if k != 'embedding'} for f in file_list]
            return self._all_files_with_embeddings_cache
        else:
            self._all_files_cache = file_list
             
        return self._all_files_cache

    def get_embeddings_for_files(self, file_paths: list[str]):
        """
        Returns a dict {file_path: embedding} for specific files.
        """
        if not file_paths: return {}
        try:
             # Chroma requires query by IDs (which are file_paths in our case)
             results = self.collection.get(ids=file_paths, include=["embeddings"])
             
             mapping = {}
             if results and results.get("ids"):
                 ids = results["ids"]
                 embeddings = results.get("embeddings")
                 for i, _id in enumerate(ids):
                     if embeddings is not None and len(embeddings) > i:
                         mapping[_id] = embeddings[i]
             return mapping
        except Exception as e:
            logger.error(f"[VectorDB] Error fetching embeddings subset: {e}")
            return {}

    def get_timeline_dates_stats(self):
        """
        Returns an array of {key: 'YYYY-MM', index: int, count: int} using Fast SQL.
        """
        import sqlite3
        try:
            chroma_db_dir = self.client.get_settings().persist_directory
            if not chroma_db_dir: return None
            sqlite_path = os.path.join(chroma_db_dir, "chroma.sqlite3")
            if not os.path.exists(sqlite_path): return None
            
            conn = sqlite3.connect(sqlite_path)
            cursor = conn.cursor()
            
            q_dates = '''
            WITH Photos AS (
                SELECT 
                    MAX(CASE WHEN m.key = 'captured_time' THEN COALESCE(m.int_value, m.float_value) END) as captured_time,
                    MAX(CASE WHEN m.key = 'tag' THEN m.string_value END) as tag
                FROM embedding_metadata m
                JOIN embeddings e ON m.id = e.id
                JOIN segments s ON e.segment_id = s.id
                JOIN collections c ON s.collection = c.id
                WHERE c.name = ?
                GROUP BY m.id
                HAVING COALESCE(MAX(CASE WHEN m.key = 'tag' THEN m.string_value END), 'photo') NOT IN ('document', 'screenshot', 'trash', 'error')
            )
            SELECT 
                CASE 
                    WHEN captured_time > 0 THEN strftime('%Y-%m', datetime(CAST(captured_time AS INTEGER), 'unixepoch'))
                    ELSE 'Unknown'
                END as ym,
                COUNT(*) as cnt
            FROM Photos
            GROUP BY ym
            ORDER BY ym DESC
            '''
            cursor.execute(q_dates, (self.collection_name,))
            rows = cursor.fetchall()
            # Cache total count for get_timeline_page
            import time as _time
            total = sum(r[1] for r in rows)
            self._timeline_total_cache = total
            self._timeline_total_cache_time = _time.time()
            conn.close()
            
            dates = []
            idx = 0
            for row in rows:
                dates.append({
                    "key": row[0],
                    "index": idx,
                    "count": row[1]
                })
                idx += row[1]
            return dates
        except Exception as e:
            logger.error(f"[VectorDB] Fast SQL timeline dates failed: {e}")
            return None

    def get_timeline_page(self, limit: int = 50, offset: int = 0):
        """
        Returns a sorted page of files for the timeline using Fast SQL.
        """
        import sqlite3
        try:
            chroma_db_dir = self.client.get_settings().persist_directory
            if not chroma_db_dir: return None, 0
            sqlite_path = os.path.join(chroma_db_dir, "chroma.sqlite3")
            if not os.path.exists(sqlite_path): return None, 0
            
            conn = sqlite3.connect(sqlite_path)
            cursor = conn.cursor()
            
            query = '''
            SELECT 
                MAX(CASE WHEN m.key = 'file_path' THEN m.string_value END) as file_path,
                MAX(CASE WHEN m.key = 'captured_time' THEN COALESCE(m.int_value, m.float_value) END) as captured_time,
                MAX(CASE WHEN m.key = 'tag' THEN m.string_value END) as tag,
                MAX(CASE WHEN m.key = 'aesthetic_score' THEN m.float_value END) as aesthetic_score
            FROM embedding_metadata m
            JOIN embeddings e ON m.id = e.id
            JOIN segments s ON e.segment_id = s.id
            JOIN collections c ON s.collection = c.id
            WHERE c.name = ?
            GROUP BY m.id
            HAVING COALESCE(MAX(CASE WHEN m.key = 'tag' THEN m.string_value END), 'photo') NOT IN ('document', 'screenshot', 'trash', 'error')
            ORDER BY captured_time DESC
            LIMIT ? OFFSET ?
            '''
            
            cursor.execute(query, (self.collection_name, limit, offset))
            rows = cursor.fetchall()
            
            # Use cached total if available (from get_timeline_dates_stats)
            import time as _time
            if self._timeline_total_cache is not None and (_time.time() - self._timeline_total_cache_time) < 120:
                total = self._timeline_total_cache
            else:
                cursor.execute('''
                SELECT COUNT(*) FROM (
                    SELECT 1
                    FROM embedding_metadata m
                    JOIN embeddings e ON m.id = e.id
                    JOIN segments s ON e.segment_id = s.id
                    JOIN collections c ON s.collection = c.id
                    WHERE c.name = ?
                    GROUP BY m.id
                    HAVING COALESCE(MAX(CASE WHEN m.key = 'tag' THEN m.string_value END), 'photo') NOT IN ('document', 'screenshot', 'trash', 'error')
                )
                ''', (self.collection_name,))
                total = cursor.fetchone()[0]
                self._timeline_total_cache = total
                self._timeline_total_cache_time = _time.time()
            
            conn.close()
            
            items = []
            for row in rows:
                items.append({
                    "file_path": row[0],
                    "captured_time": float(row[1] or 0),
                    "tag": row[2] or "photo",
                    "aesthetic_score": float(row[3] or 0.0),
                    "basename": os.path.basename(row[0]) if row[0] else ""
                })
            return items, total
        except Exception as e:
            logger.error(f"[VectorDB] Fast SQL timeline page failed: {e}")
            return None, 0

    def update_location(self, file_path: str, location_info: dict):
        """
        Updates the location metadata for a given file path.
        Handles both single images (ID=path) and video segments (metadata.file_path=path).
        """
        try:
            # 1. Find IDs by file_path
            # This covers both images and video segments
            results = self.collection.get(where={"file_path": file_path}, include=["metadatas"])
            if not results or not results['ids']:
                return
                
            ids = results['ids']
            metadatas = results['metadatas']
            
            # 2. Iterate and Update
            # In theory all segments of one file should get the same location
            for i, _id in enumerate(ids):
                meta = metadatas[i]
                
                # Update fields
                meta["city"] = location_info.get("city", "")
                meta["province"] = location_info.get("province", "")
                meta["country"] = location_info.get("country_code", "")
                meta["source"] = location_info.get("source", "manual")
                
                if location_info.get("latitude") is not None:
                     meta["latitude"] = float(location_info["latitude"])
                if location_info.get("longitude") is not None:
                     meta["longitude"] = float(location_info["longitude"])
                
                # 3. Write back
                self.invalidate_cache()
                self.collection.update(ids=[_id], metadatas=[meta])

            if self.metadata_sink:
                self.metadata_sink.update_photo_location(file_path, location_info)

        except Exception as e:
            logger.error(f"[VectorDB] Error updating location for {file_path}: {e}")

    def soft_delete_file(self, file_path: str):
        """
        Marks a file as trash. Stores original tag for restoration.
        """
        try:
            results = self.collection.get(where={"file_path": file_path}, include=["metadatas"])
            if not results or not results['ids']: return
            
            ids = results['ids']
            metadatas = results['metadatas']
            
            for i, _id in enumerate(ids):
                meta = metadatas[i]
                if meta.get('tag') == 'trash': continue
                
                # Save original tag
                meta['original_tag'] = meta.get('tag', 'photo')
                meta['tag'] = 'trash'
                
                self.invalidate_cache()
                self.collection.update(ids=[_id], metadatas=[meta])
            if self.metadata_sink:
                self.metadata_sink.trash_photo(file_path)
        except Exception as e:
            logger.error(f"[VectorDB] Error soft deleting {file_path}: {e}")

    def restore_file(self, file_path: str):
        """
        Restores a file from trash to its original tag.
        """
        try:
            results = self.collection.get(where={"file_path": file_path}, include=["metadatas"])
            if not results or not results['ids']: return
            
            ids = results['ids']
            metadatas = results['metadatas']
            
            for i, _id in enumerate(ids):
                meta = metadatas[i]
                if meta.get('tag') != 'trash': continue
                
                # Restore tag
                meta['tag'] = meta.get('original_tag', 'photo')
                # Optional: clean up original_tag key? Not strictly necessary.
                
                self.invalidate_cache()
                self.collection.update(ids=[_id], metadatas=[meta])
            if self.metadata_sink:
                self.metadata_sink.restore_photo(file_path)
        except Exception as e:
            logger.error(f"[VectorDB] Error restoring {file_path}: {e}")

    def get_trash_files(self):
        """
        Returns all files tagged as trash.
        """
        try:
            # We need to fetch everything filtered by tag=trash
            # Chroma 'where' is good for this.
            results = self.collection.get(where={"tag": "trash"}, include=["metadatas"])
            
            files = []
            if results and results.get("ids"):
                ids = results["ids"]
                metadatas = results["metadatas"]
                for i, _id in enumerate(ids):
                     meta = metadatas[i]
                     files.append({
                         "file_path": meta.get("file_path", _id),
                         "captured_time": meta.get("captured_time", 0),
                         "basename": os.path.basename(meta.get("file_path", _id)),
                         # Add size/etc if needed later
                     })
            return files
        except Exception as e:
            logger.error(f"[VectorDB] Error fetching trash: {e}")
            return []
