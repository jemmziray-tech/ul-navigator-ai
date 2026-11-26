"""FastAPI application entrypoint for UL Navigator AI."""
from __future__ import annotations

import asyncio
import logging
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import delete, select

# make the sibling `ingestion/` package importable when running from backend/
_ING = Path(__file__).resolve().parents[2] / "ingestion"
if _ING.exists() and str(_ING) not in sys.path:
    sys.path.insert(0, str(_ING))

from .api import admin, chat, public, exams  # noqa: E402
from .config import get_settings  # noqa: E402
from .db import Conversation, Message, QueryLog, init_db, session_scope  # noqa: E402
from .logging_conf import request_id_var, setup_logging  # noqa: E402
from .security import limiter  # noqa: E402

log = logging.getLogger("app")


def purge_expired() -> dict:
    """Data-retention job: delete conversations and query logs older than RETENTION_DAYS."""
    s = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=s.retention_days)
    with session_scope() as db:
        ids = list(db.scalars(select(Conversation.id).where(Conversation.updated_at < cutoff)))
        if ids:
            db.execute(delete(Message).where(Message.conversation_id.in_(ids)))
            db.execute(delete(Conversation).where(Conversation.id.in_(ids)))
        logs = db.execute(delete(QueryLog).where(QueryLog.created_at < cutoff)).rowcount
    return {"conversations": len(ids), "query_logs": logs or 0}


async def _retention_loop():
    while True:
        try:
            removed = await asyncio.to_thread(purge_expired)
            log.info("retention purge", extra={"extra_fields": removed})
        except Exception:  # noqa: BLE001
            log.exception("retention purge failed")
        await asyncio.sleep(24 * 3600)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level, s.log_json, s.logs_dir / "api.log")
    if s.sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=s.sentry_dsn.get_secret_value(), traces_sample_rate=0.1,
                            send_default_pii=False)
        except ImportError:
            log.warning("SENTRY_DSN set but sentry-sdk is not installed")
    init_db()
    from .rag.knowledge_index import get_index
    try:
        await asyncio.to_thread(get_index)  # warm embedder + index
    except Exception:  # noqa: BLE001
        log.exception("knowledge index failed to load; /health/ready will report it")
    task = asyncio.create_task(_retention_loop())
    log.info("startup complete", extra={"extra_fields": {"env": s.app_env,
                                                        "gemini": s.gemini_enabled}})
    yield
    task.cancel()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="UL Navigator AI API", version="1.0.0", lifespan=lifespan,
                  docs_url="/docs" if s.app_env != "production" else None, redoc_url=None)
    app.state.limiter = limiter
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origin_list, allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH", "DELETE"],
                       allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id", uuid.uuid4().hex[:16])[:64]
        token = request_id_var.set(rid)
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path not in ("/health",):
            log.info("request", extra={"extra_fields": {
                "method": request.method, "path": request.url.path,
                "status": response.status_code,
                "ms": round((time.perf_counter() - t0) * 1000, 1)}})
        return response

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limited(request: Request, exc: RateLimitExceeded):
        return JSONResponse({"detail": "Too many requests. Please slow down and try again shortly."},
                            status_code=429)

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError):
        errors = [{"loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse({"detail": "Invalid request", "errors": errors}, status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled error")
        return JSONResponse({"detail": "Internal server error",
                             "request_id": request_id_var.get()}, status_code=500)

    app.include_router(public.router)
    app.include_router(exams.router)
    app.include_router(chat.router)
    app.include_router(admin.router)
    return app


app = create_app()
