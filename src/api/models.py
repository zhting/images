"""
Pydantic request / response models used across API routes.
"""
from pydantic import BaseModel
from typing import List, Optional


# --- Search ---
class TextSearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = None
    use_translation: bool = True


class AISearchRequest(BaseModel):
    prompt: str
    provider: str = "config"
    top_k: Optional[int] = None


class SearchResultItem(BaseModel):
    file_path: str
    score: float
    basename: str
    timestamp: float = 0
    date_str: str = ""


# --- Config ---
class ConfigUpdate(BaseModel):
    key: str
    value: str


class PathRequest(BaseModel):
    path: str


class WishlistUpdate(BaseModel):
    wishlist: list


# --- People ---
class PersonNameUpdate(BaseModel):
    person_id: int
    name: str


# --- Privacy ---
class PrivacyPasswordRequest(BaseModel):
    password: str
    old_password: Optional[str] = None


class PrivacyVerifyRequest(BaseModel):
    password: str


class PrivacyLockRequest(BaseModel):
    path: str


# --- Files / Trash ---
class TrashActionRequest(BaseModel):
    file_paths: List[str]


# --- System / Indexing ---
class IndexRunRequest(BaseModel):
    force: bool = False


class IndexingProgress(BaseModel):
    state: str = "idle"
    phase: str = ""
    current: int = 0
    total: int = 0
    current_file: str = ""
    processed_photos: int = 0
    processed_videos: int = 0
    scan_result: Optional[dict] = None
    start_time: float = 0
    last_updated: str = ""
    stop_requested: bool = False
    total_photos: int = 0
    total_videos: int = 0


# --- Generate ---
class GenerateRequest(BaseModel):
    prompt: str
    provider: str = "config"


# --- Travel ---
class PostcardFinalizeRequest(BaseModel):
    integrated_path: str
    original_path: str
    scene: str = ""
    outfit: str = ""


# --- Filesystem ---
class FSListRequest(BaseModel):
    path: str
    only_dir: bool = False


class ExplorerRequest(BaseModel):
    path: str
