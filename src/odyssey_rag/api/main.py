"""FastAPI application entry point.

Creates and configures the Odyssey RAG API application with all routers,
exception handlers, and the /health endpoint.

Usage:
    uvicorn odyssey_rag.api.main:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from odyssey_rag.api.errors import http_exception_handler, validation_exception_handler
from odyssey_rag.api.routes import (
    admin,
    audit,
    auth,
    categories,
    chunks,
    feedback,
    gc,
    ingest,
    jobs,
    search,
    sources,
    stats,
    tokens,
    upload,
)
from odyssey_rag.config import get_settings
from odyssey_rag.db.session import close_engine, get_engine

logger = structlog.get_logger(__name__)

APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — warm up on startup, clean up on shutdown."""
    from odyssey_rag.job_resilience import (
        IngestTaskRegistry,
        recover_interrupted_jobs,
        start_watchdog,
        stop_watchdog,
    )

    logger.info("startup", version=APP_VERSION)
    get_engine()  # initialise connection pool

    # S10: Warm up the source type categorizer cache
    try:
        from odyssey_rag.ingestion.categorizer import init_categorizer_cache

        await init_categorizer_cache()
    except Exception:
        logger.warning("startup.categorizer_cache_failed", exc_info=True)

    # S7: Recover jobs left in "running" state by a previous crash
    await recover_interrupted_jobs()
    start_watchdog()

    yield

    # S7: Graceful shutdown — cancel in-flight tasks, stop watchdog
    logger.info("shutdown", active_tasks=IngestTaskRegistry.active_count())
    await IngestTaskRegistry.cancel_all()
    await stop_watchdog()
    await close_engine()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Odyssey RAG API",
        version=APP_VERSION,
        description=(
            "RAG system for Odyssey project knowledge — ISO 20022 / Bimpay domain"
        ),
        lifespan=lifespan,
    )

    # ── Exception handlers ────────────────────────────────────────────────────
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # ── API routers ───────────────────────────────────────────────────────────
    app.include_router(search.router, prefix="/api/v1", tags=["search"])
    app.include_router(ingest.router, prefix="/api/v1", tags=["ingest"])
    app.include_router(sources.router, prefix="/api/v1", tags=["sources"])
    app.include_router(chunks.router, prefix="/api/v1", tags=["chunks"])
    app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])
    app.include_router(stats.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(tokens.router, prefix="/api/v1")
    app.include_router(upload.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(audit.router, prefix="/api/v1")
    app.include_router(gc.router, prefix="/api/v1")
    app.include_router(categories.router, prefix="/api/v1", tags=["categories"])

    # ── Health endpoint ───────────────────────────────────────────────────────

    @app.get("/health", tags=["health"], summary="Service health check")
    async def health():
        """Return the health status of all dependent services.

        Always public — no API key required.
        """
        from sqlalchemy import text

        from odyssey_rag.db.session import get_session_factory
        from odyssey_rag.embeddings.factory import create_embedding_provider

        service_status: dict[str, str] = {
            "database": "ok",
            "embedding_model": "ok",
            "reranker": "ok",
        }
        degraded = False

        # ── Database ping ─────────────────────────────────────────────────
        try:
            factory = get_session_factory()
            async with factory() as sess:
                await sess.execute(text("SELECT 1"))
        except Exception as exc:
            service_status["database"] = "error"
            degraded = True
            logger.warning("health.db_error", error=str(exc))

        # ── Embedding model ───────────────────────────────────────────────
        try:
            create_embedding_provider(settings)
        except Exception as exc:
            service_status["embedding_model"] = "error"
            degraded = True
            logger.warning("health.embedding_error", error=str(exc))

        # ── Reranker ──────────────────────────────────────────────────────
        try:
            if settings.reranker_enabled:
                from odyssey_rag.api.deps import get_retrieval_engine

                get_retrieval_engine()
        except Exception as exc:
            service_status["reranker"] = "error"
            degraded = True
            logger.warning("health.reranker_error", error=str(exc))

        overall = "degraded" if degraded else "ok"
        payload = {
            "status": overall,
            "version": APP_VERSION,
            "services": service_status,
        }

        if degraded:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=503, content=payload)

        return payload

    # ── Prometheus metrics endpoint ───────────────────────────────────────────

    @app.get("/metrics", tags=["observability"], summary="Prometheus metrics")
    async def metrics():
        """Expose Prometheus-format metrics. No auth required."""
        from fastapi.responses import Response
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
