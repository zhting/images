"""Unified API error handling.

Routes raise domain exceptions (or plain HTTPException for simple
cases); the handlers below convert them into structured JSON.  The
generic-Exception handler replaces the previous per-route pattern

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

which had two problems: it leaked internal error details (paths, stack
messages) to the client, and — because HTTPException is itself an
Exception — it silently converted deliberate 404/403 responses raised
inside the try block into 500s.
"""
import logging
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("api")


class AppError(Exception):
    status = 500
    code = "internal_error"

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message


class NotFound(AppError):
    status, code = 404, "not_found"


class Forbidden(AppError):
    status, code = 403, "forbidden"


class Conflict(AppError):
    status, code = 409, "conflict"


def register_handlers(app):
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status,
                            content={"code": exc.code, "message": exc.message})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        trace_id = uuid.uuid4().hex[:8]
        logger.exception("unhandled error [%s] %s %s",
                         trace_id, request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"code": "internal_error", "trace_id": trace_id,
                     "message": "Internal error; see server log for details."})
