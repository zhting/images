"""
Indexing pipeline (core.sync) — batching, worker threads, ordering, errors.

core.sync imports the real model/face/video/geocoder stacks at module level,
none of which exist in CI, so this module installs light stand-ins in
sys.modules before importing it (and removes them afterwards). The fakes
are deterministic functions of the pixels, which lets the tests assert that
the batched, multi-threaded pipeline produces exactly what indexing each
file on its own produces.
"""
import datetime
import importlib
import os
import sys
import threading
import types

import numpy as np
import pytest
from PIL import Image

DIM = 8


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class FakeModel:
    device = "cpu"

    def __init__(self):
        self.batch_sizes = []
        self.encode_calls = 0
        self.fail_batches = False
        self.poison = set()   # mean-brightness values that make analyze raise

    def preprocess(self, img):
        small = np.asarray(img.convert("RGB").resize((4, 4)), dtype=np.float32)
        return small

    def _embed(self, px):
        vec = np.concatenate([px.mean(axis=(0, 1)), px.std(axis=(0, 1)), [px.max(), px.min()]])
        vec = vec.astype(np.float32) + 1.0
        return vec / np.linalg.norm(vec)

    def _analyze_px(self, px):
        if round(float(px.mean())) in self.poison:
            raise RuntimeError("bad pixels")
        mean = float(px.mean())
        return {"embedding": self._embed(px).tolist(),
                "aesthetic_score": mean / 255.0,
                "tag": "document" if mean > 200 else "photo"}

    def analyze(self, img):
        return self._analyze_px(self.preprocess(img))

    def analyze_batch(self, pixels):
        self.batch_sizes.append(len(pixels))
        if self.fail_batches and len(pixels) > 1:
            raise RuntimeError("OOM")
        return [self._analyze_px(px) for px in pixels]

    def encode(self, img):
        self.encode_calls += 1
        return self._embed(self.preprocess(img)).tolist()

    def encode_text_batch(self, texts):
        rng = np.random.default_rng(0)
        feats = rng.random((len(texts), DIM)).astype(np.float32)
        return (feats / np.linalg.norm(feats, axis=1, keepdims=True)).tolist()


class FakeLocationProcessor:
    def get_lat_lon(self, image):
        # Even widths "have GPS".
        return (float(image.width), float(image.height)) if image.width % 2 == 0 else None

    def location_from_coords(self, lat, lon):
        return {"latitude": lat, "longitude": lon, "city": f"c{int(lat)}",
                "province": "p", "country_code": "CN"}

    def infer_from_path(self, path):
        return {"city": "from-path"} if "trip" in path else None


class FakeFaceProcessor:
    threads = set()

    def detect_faces(self, img):
        FakeFaceProcessor.threads.add(threading.current_thread().name)
        r, g, b = np.asarray(img).reshape(-1, 3).mean(axis=0)
        if r > g + 50 and r > b + 50:
            return [{"bbox": [0, 0, 40, 40], "embedding": np.ones(4), "det_score": 0.9}]
        return []


class FakeVideoProcessor:
    def process_video(self, path):
        if "broken" in path:
            return []
        return [(Image.new("RGB", (32, 32), (10, 20, 30)), 0.5),
                (Image.new("RGB", (32, 32), (90, 90, 90)), 1.5)]


class FakeDB:
    def __init__(self):
        self.records = []
        self.deleted = []
        self.calls = 0

    def insert_many(self, records):
        self.calls += 1
        self.records.extend(records)

    def insert(self, vector, file_path, file_hash, last_modified, **kw):
        self.records.append({"vector": vector, "file_path": file_path,
                             "file_hash": file_hash, "last_modified": last_modified, **kw})

    def delete_by_path(self, path):
        self.deleted.append(path)


class FakeStore:
    def __init__(self):
        self.faces = {}
        self.config = {}

    def create_faces_table(self):
        pass

    def delete_faces(self, path):
        self.faces.pop(path, None)

    def add_faces(self, path, faces):
        self.faces[path] = len(faces)

    def set_config(self, k, v):
        self.config[k] = v


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sync_mod(monkeypatch, tmp_path):
    def stub(name, **attrs):
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        monkeypatch.setitem(sys.modules, name, mod)

    stub("database.vector_db", VectorDB=object)
    stub("core.models", VisionModel=object)
    stub("core.location_processor", LocationProcessor=FakeLocationProcessor)
    stub("core.face_processor", FaceProcessor=FakeFaceProcessor)
    stub("core.video_processor", VideoProcessor=FakeVideoProcessor)

    import core.thumbnails as thumbs
    monkeypatch.setattr(thumbs, "thumbnail_service", thumbs.ThumbnailService(str(tmp_path / "thumbs")))

    monkeypatch.delitem(sys.modules, "core.sync", raising=False)
    mod = importlib.import_module("core.sync")
    yield mod
    sys.modules.pop("core.sync", None)


def make_manager(sync_mod, monkeypatch, batch=3, workers=2):
    monkeypatch.setenv("DEEPPHOTO_INDEX_BATCH", str(batch))
    monkeypatch.setenv("DEEPPHOTO_INDEX_WORKERS", str(workers))
    return sync_mod.SyncManager(FakeDB(), FakeModel(), FakeStore())


@pytest.fixture
def library(tmp_path):
    """A small mixed library: photos (with/without EXIF date, GPS, faces,
    'document'-bright), a corrupt file and a video."""
    root = tmp_path / "lib"
    (root / "trip").mkdir(parents=True)
    paths = []
    colors = [(200, 30, 30), (30, 200, 30), (240, 240, 240), (60, 60, 200),
              (250, 250, 250), (120, 120, 120), (220, 40, 40), (10, 10, 10)]
    for i, color in enumerate(colors):
        sub = root / "trip" if i % 3 == 0 else root
        p = sub / f"img{i}.jpg"
        img = Image.new("RGB", (64 + i, 48), color)
        exif = Image.Exif()
        if i % 2 == 0:
            exif[306] = f"2020:0{i + 1}:15 10:00:00"
        img.save(p, exif=exif)
        paths.append(str(p))
    bad = root / "corrupt.jpg"
    bad.write_bytes(b"not an image")
    paths.insert(3, str(bad))
    vid = root / "clip.mp4"
    vid.write_bytes(b"\x00" * 64)
    paths.insert(6, str(vid))
    return paths


def by_path(records):
    out = {}
    for r in records:
        out.setdefault(r.get("custom_id") or r["file_path"], r)
    return out


def run(mgr, paths, **kw):
    progress = []
    mgr.sync_changes({"to_add": paths, "to_update": [], "to_delete": []},
                     progress_callback=lambda c, t, m, is_video=False: progress.append((c, t, m, is_video)),
                     **kw)
    return progress


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_pipeline_matches_one_file_at_a_time(sync_mod, monkeypatch, library):
    piped = make_manager(sync_mod, monkeypatch, batch=3, workers=3)
    run(piped, library)

    # Reference: every still image through _index_image on its own.
    ref = make_manager(sync_mod, monkeypatch)
    for p in library:
        if p.endswith(".mp4"):
            ref._index_video(p, {})
            continue
        try:
            with Image.open(p) as im:
                im.load()
                ref._index_image(p, im, {})
        except Exception as e:
            ref._fail(p, e, {})

    a, b = by_path(piped.db.records), by_path(ref.db.records)
    assert a.keys() == b.keys()
    for k in a:
        assert a[k] == b[k], k
    assert piped.store.faces == ref.store.faces


def test_expected_metadata(sync_mod, monkeypatch, library):
    FakeFaceProcessor.threads.clear()
    mgr = make_manager(sync_mod, monkeypatch)
    run(mgr, library)
    recs = by_path(mgr.db.records)

    img0 = recs[library[0]]  # red, trip/, even width, EXIF date
    assert img0["captured_time"] == int(datetime.datetime(2020, 1, 15, 10).timestamp())
    assert img0["location_info"]["city"] == "c64"
    assert mgr.store.faces[library[0]] == 1

    bright = recs[library[2]]  # (240,240,240) -> 'document', no faces
    assert bright["tag"] == "document"
    assert library[2] not in mgr.store.faces

    no_gps = recs[library[1]]  # odd width, not under trip/ -> no location at all
    assert no_gps["location_info"] is None
    assert no_gps["captured_time"] == int(os.path.getmtime(library[1]))
    from_path = recs[library[4]]  # trip/img3.jpg, odd width -> inferred from path
    assert from_path["location_info"] == {"city": "from-path"}

    corrupt = recs[library[3]]
    assert corrupt["tag"] == "error"
    assert "corrupt" in corrupt["auto_tags"][0]

    video = [r for r in mgr.db.records if r.get("custom_id", "").startswith(library[6])]
    assert [r["custom_id"] for r in video] == [f"{library[6]}#0", f"{library[6]}#1"]
    assert all(r["tag"] == "video" for r in video)

    # Face detection ran on prep workers, not the main thread.
    assert FakeFaceProcessor.threads and all(t.startswith("index-prep") for t in FakeFaceProcessor.threads)


def test_batches_and_progress(sync_mod, monkeypatch, library):
    mgr = make_manager(sync_mod, monkeypatch, batch=3)
    progress = run(mgr, library)

    assert [c for c, *_ in progress] == list(range(1, len(library) + 1))
    assert all(t == len(library) for _, t, *_ in progress)
    # Every file reported exactly once, in input order.
    assert [m.removeprefix("Indexing ") for _, _, m, _ in progress] == [os.path.basename(p) for p in library]
    assert [v for *_, v in progress] == [p.endswith(".mp4") for p in library]
    assert max(mgr.model.batch_sizes) == 3
    assert "last_indexed_time" in mgr.store.config


def test_stop_midway(sync_mod, monkeypatch, library):
    mgr = make_manager(sync_mod, monkeypatch, batch=2)
    seen = []
    mgr.sync_changes({"to_add": library, "to_update": [], "to_delete": []},
                     progress_callback=lambda c, t, m, is_video=False: seen.append(c),
                     stop_check=lambda: len(seen) >= 4)
    assert 4 <= len(seen) < len(library)
    assert "last_indexed_time" not in mgr.store.config
    written = {r["file_path"] for r in mgr.db.records}
    assert written <= set(library[:len(seen) + 2])


def test_batch_failure_falls_back_per_item(sync_mod, monkeypatch, library):
    mgr = make_manager(sync_mod, monkeypatch, batch=4)
    mgr.model.fail_batches = True
    mgr.model.poison = {120}  # library[6+1] -> (120,120,120)
    run(mgr, library)
    recs = by_path(mgr.db.records)
    stills = [p for p in library if p.endswith(".jpg")]
    assert set(stills) <= recs.keys()
    poisoned = [p for p in stills if recs[p]["tag"] == "error"]
    assert library[3] in poisoned and len(poisoned) == 2
    assert "unexpected error" in recs[[p for p in poisoned if p != library[3]][0]]["auto_tags"][0]


def test_error_placeholder_vector_computed_once(sync_mod, monkeypatch, tmp_path):
    paths = []
    for i in range(3):
        p = tmp_path / f"bad{i}.jpg"
        p.write_bytes(b"junk")
        paths.append(str(p))
    mgr = make_manager(sync_mod, monkeypatch)
    run(mgr, paths)
    assert len(mgr.db.records) == 3
    assert mgr.model.encode_calls == 1


def test_video_without_frames_is_marked(sync_mod, monkeypatch, tmp_path):
    p = tmp_path / "broken.mp4"
    p.write_bytes(b"\x00")
    mgr = make_manager(sync_mod, monkeypatch)
    progress = run(mgr, [str(p)])
    assert mgr.db.records[0]["tag"] == "error"
    assert progress == [(1, 1, "Indexing broken.mp4", True)]


def test_get_image_timestamp_closes_file(sync_mod, tmp_path):
    p = tmp_path / "x.jpg"
    Image.new("RGB", (8, 8)).save(p)
    import gc
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error", ResourceWarning)
        assert sync_mod.get_image_timestamp(str(p)) == int(os.path.getmtime(p))
        gc.collect()


# ---------------------------------------------------------------------------
# Thumbnails: grid is derived from the preview, sizes unchanged
# ---------------------------------------------------------------------------
def test_thumbnail_sizes(tmp_path):
    from core.thumbnails import ThumbnailService
    svc = ThumbnailService(str(tmp_path / "t"))
    src = tmp_path / "big.jpg"
    Image.new("RGB", (4000, 3000), (1, 2, 3)).save(src)
    with Image.open(src) as im:
        im.load()
        svc.generate_from_image(str(src), im)
    with Image.open(svc.get_thumbnail_path(str(src), "preview")) as p:
        assert p.size == (1600, 1200)
    with Image.open(svc.get_thumbnail_path(str(src), "grid")) as g:
        assert g.size == (360, 270)


# ---------------------------------------------------------------------------
# Geocoder: always the single-process KD-tree
# ---------------------------------------------------------------------------
def test_reverse_geocode_is_single_process(monkeypatch):
    calls = {}

    class FakeRG:
        def __init__(self, mode=2, verbose=True):
            calls["mode"] = mode

        def query(self, coords):
            calls["coords"] = coords
            return [{"name": "Hangzhou", "admin1": "Zhejiang", "cc": "CN"}]

    rg = types.ModuleType("reverse_geocoder")
    rg.RGeocoder = FakeRG
    rg.search = lambda *a, **k: pytest.fail("rg.search defaults to a process pool per call")
    monkeypatch.setitem(sys.modules, "reverse_geocoder", rg)
    monkeypatch.delitem(sys.modules, "core.location_processor", raising=False)
    lp = importlib.import_module("core.location_processor")
    try:
        assert lp.reverse_geocode(30.2, 120.1)[0]["name"] == "Hangzhou"
        assert calls == {"mode": 1, "coords": [(30.2, 120.1)]}
    finally:
        sys.modules.pop("core.location_processor", None)


# ---------------------------------------------------------------------------
# Translator: a failed 7B load is not retried for every place name
# ---------------------------------------------------------------------------
def test_large_translator_load_failure_not_retried(monkeypatch):
    attempts = []

    class Boom:
        @staticmethod
        def from_pretrained(name, **kw):
            attempts.append(name)
            raise OSError("no such model")

    tf = types.ModuleType("transformers")
    tf.AutoModelForCausalLM = Boom
    tf.AutoTokenizer = Boom
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    monkeypatch.setitem(sys.modules, "transformers", tf)
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.delitem(sys.modules, "core.translator", raising=False)
    tr = importlib.import_module("core.translator")
    try:
        t = tr.LocalTranslator()
        for _ in range(5):
            t._ensure_large_model()
        assert attempts == ["Qwen/Qwen2.5-7B-Instruct"]
    finally:
        sys.modules.pop("core.translator", None)


# ---------------------------------------------------------------------------
# VisionModel: batched analysis == per-image analysis (needs torch)
# ---------------------------------------------------------------------------
def test_vision_model_batch_matches_single():
    torch = pytest.importorskip("torch")
    pytest.importorskip("transformers")
    from transformers import SiglipConfig, SiglipImageProcessor, SiglipModel

    sys.modules.pop("core.models", None)
    models = importlib.import_module("core.models")

    cfg = SiglipConfig(
        text_config={"hidden_size": 32, "intermediate_size": 64, "num_hidden_layers": 2,
                     "num_attention_heads": 2, "vocab_size": 100},
        vision_config={"hidden_size": 32, "intermediate_size": 64, "num_hidden_layers": 2,
                       "num_attention_heads": 2, "image_size": 32, "patch_size": 8})
    torch.manual_seed(0)
    vm = models.VisionModel.__new__(models.VisionModel)
    vm.device, vm.dtype = "cpu", torch.float32
    vm.model = SiglipModel(cfg).eval()
    vm.processor = SiglipImageProcessor(size={"height": 32, "width": 32})
    vm._bank_lock = threading.Lock()
    bank = lambda n: torch.nn.functional.normalize(torch.randn(n, 32), dim=-1)  # noqa: E731
    vm._text_bank_cache = {"aesthetic": bank(2), "type": bank(3)}

    rng = np.random.default_rng(1)
    imgs = [Image.fromarray(rng.integers(0, 255, (40 + i, 50, 3), dtype=np.uint8)) for i in range(5)]
    single = [vm.analyze(im) for im in imgs]
    batched = vm.analyze_batch([vm.preprocess(im) for im in imgs])
    for s, b in zip(single, batched, strict=True):
        assert s["tag"] == b["tag"]
        assert abs(s["aesthetic_score"] - b["aesthetic_score"]) < 1e-5
        assert np.allclose(s["embedding"], b["embedding"], atol=1e-5)
    assert np.allclose(vm.encode_batch(imgs), [s["embedding"] for s in single], atol=1e-5)
