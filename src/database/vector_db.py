import chromadb
from chromadb.config import Settings
import os

class VectorDB:
    def __init__(self, db_path="./search.db", collection_name="LocalPhotoGallery"):
        # ChromaDB creates a folder, not a single file usually, unless using sqlite mode extensively.
        # But allow passing path.
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection_name = collection_name
        self._init_collection()

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
            print(f"[VectorDB] Warning deleting collection: {e}")
        self._init_collection()

    def create_collection_with_schema(self):
        # Chroma handles schema dynamically
        pass

    def insert(self, vector: list[float], file_path: str, file_hash: str, last_modified: int, captured_time: int = 0):
        # Chroma requires ID. We can use file_path or a hash as ID if unique.
        # Using file_path as ID allows easy deduplication/updates.
        
        # metadata
        metadatas = [{
            "file_path": file_path,
            "file_hash": file_hash,
            "last_modified": last_modified,
            "captured_time": captured_time
        }]
        
        self.collection.upsert(
            embeddings=[vector],
            metadatas=metadatas,
            ids=[file_path] # Use path as ID for simplicity in local files
        )

    def insert_batch(self, vectors: list[list[float]], file_paths: list[str], last_modifieds: list[int], captured_times: list[int] = None):
        """
        Batch insertion for efficiency.
        """
        if captured_times is None:
             captured_times = [0] * len(file_paths)
             
        metadatas = [{
            "file_path": fp, 
            "file_hash": "hash", 
            "last_modified": lm,
            "captured_time": ct
        } for fp, lm, ct in zip(file_paths, last_modifieds, captured_times)]
        
        self.collection.upsert(
            embeddings=vectors,
            metadatas=metadatas,
            ids=file_paths
        )

    def search(self, vector: list[float], top_k: int = 50):
        print(f"[VectorDB] Searching with top_k={top_k}")
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
            print("[VectorDB] No ids returned.")
            return formatted
            
        ids_list = results['ids']
        if not ids_list or ids_list[0] is None:
             print("[VectorDB] Empty ids list.")
             return formatted
             
        ids = ids_list[0]
        distances = results.get('distances', [[]])[0] if results.get('distances') else [0.0] * len(ids)
        
        # Handle metadatas safely
        metadatas_list = results.get('metadatas')
        if metadatas_list and metadatas_list[0] is not None:
            metadatas = metadatas_list[0]
        else:
            print("[VectorDB] Warning: No metadatas found, using empty dicts.")
            metadatas = [{}] * len(ids)
        
        for i, _id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            if meta is None: 
                meta = {}
                
            formatted.append({
                "id": _id,
                "distance": distances[i] if i < len(distances) else 0.0,
                "entity": meta
            })
            
        return [formatted]
    
    def delete_by_path(self, file_path: str):
        self.collection.delete(ids=[file_path])

    def count(self):
        return self.collection.count()

    def get_all_files(self):
        """
        Returns a dictionary {file_path: last_modified} of all indexed files.
        """
        # Chroma's get without ids returns everything. Beware of memory for millions of items.
        # Ideally use pagination, but for local app <100k images, this might be okay.
        # We only need metadatas and ids.
        results = self.collection.get(include=["metadatas"])
        
        file_map = {}
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
        return file_map

    def get_all_files_with_time(self):
        """
        Returns a list of dicts {file_path, captured_time, last_modified}.
        """
        results = self.collection.get(include=["metadatas"])
        
        file_list = []
        if results and results.get("ids"):
            ids = results["ids"]
            metadatas = results["metadatas"]
            for i, _id in enumerate(ids):
                meta = metadatas[i]
                if meta:
                     # Default to 0 if not present
                     last_mod = meta.get("last_modified", 0) 
                     captured_time = meta.get("captured_time", last_mod) # Fallback to mtime
                     file_path = meta.get("file_path", _id)
                     file_list.append({
                         "file_path": file_path,
                         "captured_time": captured_time,
                         "last_modified": last_mod
                     })
        return file_list
