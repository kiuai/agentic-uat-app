"""
KAATS FastAPI application factory.

Startup order:
1. structlog configured
2. CORS middleware applied (origins from settings)
3. Tenant resolution middleware attached
4. Request timing + correlation ID middleware attached
5. Application Insights middleware attached (if connection string present)
6. Database engine warmed up
7. Cosmos client verified
8. All routers mounted under /api/v1
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.cosmos import check_cosmos_connection, close_cosmos_client
from app.database import check_db_connection, dispose_engine
from app.logging_config import configure_logging
from app.middleware.tenant import TenantMiddleware
from app.routers import (
    ai_generation,
    auth,
    crawler,
    projects,
    reports,
    requirements,
    tenants,
    test_cycles,
    test_scripts,
    users,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Manage application lifecycle — startup and shutdown."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info(
        "kaats_starting",
        environment=settings.environment,
        openapi_enabled=settings.openapi_enabled,
    )

    if not await check_db_connection():
        logger.warning("database_unavailable_on_startup")
    else:
        logger.info("database_connected")

    if not await check_cosmos_connection():
        logger.warning("cosmos_unavailable_on_startup")
    else:
        logger.info("cosmos_connected")

    yield

    logger.info("kaats_shutting_down")
    await dispose_engine()
    await close_cosmos_client()
    logger.info("kaats_stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="KIU AI Automated Test System",
        description=(
            "KAATS API — AI-powered automated test generation and execution tracking. "
            "Multi-tenant SaaS on Azure."
        ),
        version="1.0.0",
        docs_url="/docs" if settings.openapi_enabled else None,
        redoc_url="/redoc" if settings.openapi_enabled else None,
        openapi_url="/api/v1/openapi.json" if settings.openapi_enabled else None,
        lifespan=lifespan,
    )

    _add_middleware(app, settings)
    _add_exception_handlers(app)
    _add_routers(app)
    _add_health_endpoints(app)

    return app


def _add_middleware(app: FastAPI, settings: Any) -> None:
    # CORS — must be outermost so pre-flight OPTIONS requests are handled
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-Id",
            "X-Tenant-Slug",
        ],
        expose_headers=["X-Request-Id", "X-Response-Time-Ms"],
    )

    # Tenant slug resolution
    app.add_middleware(TenantMiddleware)

    # Request timing, correlation ID, and structured log context
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next: Any) -> Any:
        # Assign a correlation ID — use client-provided header or generate one
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        start = time.perf_counter()

        with structlog.contextvars.bound_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        ):
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 1)

            response.headers["X-Request-Id"] = request_id
            response.headers["X-Response-Time-Ms"] = str(duration_ms)
            # Security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            logger.info(
                "http_request",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            return response

    # Application Insights integration
    if settings.applicationinsights_connection_string:
        try:
            from opencensus.ext.azure.trace_exporter import AzureExporter
            from opencensus.ext.fastapi.fastapi_middleware import FastAPIMiddleware

            app.add_middleware(
                FastAPIMiddleware,
                exporter=AzureExporter(
                    connection_string=settings.applicationinsights_connection_string
                ),
            )
            logger.info("application_insights_middleware_enabled")
        except ImportError:
            logger.warning("opencensus_not_installed_skipping_app_insights")


def _add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("request_validation_error", errors=exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "type": "https://kaats.example.com/errors/validation-error",
                "title": "Request Validation Error",
                "status": 422,
                "detail": exc.errors(),
                "instance": str(request.url.path),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("unhandled_exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "type": "https://kaats.example.com/errors/internal-error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred. Check application logs.",
                "instance": str(request.url.path),
            },
        )


def _add_routers(app: FastAPI) -> None:
    prefix = "/api/v1"
    app.include_router(auth.router, prefix=prefix, tags=["Auth"])
    app.include_router(tenants.router, prefix=prefix, tags=["Tenants"])
    app.include_router(users.router, prefix=prefix, tags=["Users"])
    app.include_router(projects.router, prefix=prefix, tags=["Projects"])
    app.include_router(requirements.router, prefix=prefix, tags=["Requirements"])
    app.include_router(test_scripts.router, prefix=prefix, tags=["Test Scripts"])
    app.include_router(test_cycles.router, prefix=prefix, tags=["Test Cycles"])
    app.include_router(ai_generation.router, prefix=prefix, tags=["AI Generation"])
    app.include_router(crawler.router, prefix=prefix, tags=["Crawler"])
    app.include_router(reports.router, prefix=prefix, tags=["Reports"])


def _add_health_endpoints(app: FastAPI) -> None:
    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", include_in_schema=False)
    async def readiness() -> JSONResponse:
        db_ok = await check_db_connection()
        cosmos_ok = await check_cosmos_connection()
        healthy = db_ok and cosmos_ok
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={
                "status": "ready" if healthy else "not_ready",
                "database": "ok" if db_ok else "error",
                "cosmos": "ok" if cosmos_ok else "error",
            },
        )


app = create_app()
