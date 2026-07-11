"""Unified error handling: structured responses, no internal leaks,
HTTPException passthrough restored."""
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.errors import register_handlers, NotFound


def make_app():
    app = FastAPI()
    register_handlers(app)

    @app.get("/boom")
    def boom():
        raise ValueError("secret internal path C:/users/x/.ssh")

    @app.get("/missing")
    def missing():
        raise NotFound("photo not found")

    @app.get("/legacy-404")
    def legacy():
        # Old pattern converted deliberate HTTPExceptions inside try
        # blocks into 500s; bare re-raise must preserve them.
        try:
            raise HTTPException(status_code=404, detail="gone")
        except Exception:
            raise

    return app


class TestErrorHandlers:
    def setup_method(self):
        self.client = TestClient(make_app(), raise_server_exceptions=False)

    def test_unhandled_returns_trace_id_without_leaking(self):
        r = self.client.get("/boom")
        assert r.status_code == 500
        body = r.json()
        assert body["code"] == "internal_error" and body["trace_id"]
        assert "secret" not in r.text and ".ssh" not in r.text

    def test_domain_error_maps_to_status(self):
        r = self.client.get("/missing")
        assert r.status_code == 404
        assert r.json() == {"code": "not_found", "message": "photo not found"}

    def test_http_exception_passthrough(self):
        r = self.client.get("/legacy-404")
        assert r.status_code == 404
        assert r.json()["detail"] == "gone"
