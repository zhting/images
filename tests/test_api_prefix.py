"""All API routes live under /api, so page routes (/timeline, /travel, ...)
can never collide with them, and /index/run accepts an empty body."""
from fastapi.testclient import TestClient


def raw_client():
    from api.server import app
    return TestClient(app)


def test_version_check_under_api_and_legacy_alias():
    c = raw_client()
    assert c.get("/api/version_check").json() == {"status": "READY"}
    # start.bat / older launchers still poll the unprefixed path.
    assert c.get("/version_check").json() == {"status": "READY"}


def test_api_routes_are_prefixed(app_client):
    # app_client's base_url already ends in /api.
    assert app_client.get("/timeline", params={"page": 1, "size": 5}).status_code == 200
    # The bare page path is no longer an API endpoint: it is either the app
    # shell (when web/dist is built) or a plain 404 — never timeline JSON.
    r = raw_client().get("/timeline", params={"page": 1, "size": 5})
    if r.status_code == 200:
        assert r.headers["content-type"].startswith("text/html")
    else:
        assert r.status_code == 404


def test_unknown_api_path_is_json_404():
    r = raw_client().get("/api/definitely-not-a-route")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


def test_index_run_accepts_missing_body(app_client):
    """The onboarding used to POST without a body and got a 422, which left
    first-time users stuck. A missing body now means {"force": false}."""
    from api.state import state
    prev = state.progress.state
    state.progress.state = "indexing"   # short-circuit before any work starts
    try:
        r = app_client.post("/index/run")
    finally:
        state.progress.state = prev
    assert r.status_code == 400, r.text           # "already in progress", not 422
    assert "already in progress" in r.text


def test_spa_serves_root_files_and_pages(tmp_path, monkeypatch):
    """Built frontend: root files come back as themselves (not index.html),
    page routes get the app shell, and nothing escapes the dist folder."""
    import importlib
    import sys
    dist = tmp_path / "web" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>shell</title>", encoding="utf-8")
    (dist / "sw.js").write_text("self.addEventListener('fetch', () => {})", encoding="utf-8")
    (dist / "china.json").write_text('{"type": "FeatureCollection"}', encoding="utf-8")
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")

    import core.paths
    monkeypatch.setattr(core.paths, "get_internal_data_dir", lambda: str(tmp_path))
    sys.modules.pop("api.server", None)
    server = importlib.import_module("api.server")
    try:
        c = TestClient(server.app)
        r = c.get("/sw.js")
        assert r.status_code == 200 and "addEventListener" in r.text
        assert "javascript" in r.headers["content-type"]
        assert c.get("/china.json").json() == {"type": "FeatureCollection"}
        for page in ("/", "/timeline", "/travel", "/people"):
            r = c.get(page)
            assert r.status_code == 200 and "shell" in r.text, page
        assert "nope" not in c.get("/../secret.txt").text
        assert "nope" not in c.get("/%2e%2e/secret.txt").text
        assert c.get("/api/nope").status_code == 404
    finally:
        sys.modules.pop("api.server", None)
