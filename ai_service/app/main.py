"""FastAPI application factory.

Wiring order matters: logging first, then middleware (request id + access log),
then routes. Every endpoint depends on `require_api_key` and the sliding-window
limiter, so nothing here is publicly reachable.
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.core.config import get_settings
from app.core.logging import configure_logging, request_id_var
from app.providers.factory import get_provider
from app.routers import caption, health, moderate, mood

logger = logging.getLogger("ai.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    provider = get_provider()
    logger.info(
        "ai service started",
        extra={
            "event": "service.start",
            "provider": provider.name,
            "environment": settings.environment,
            "rate_limit": f"{settings.rate_limit_requests}/{settings.rate_limit_window_seconds}s",
            "fallback": settings.allow_heuristic_fallback,
        },
    )
    yield
    logger.info("ai service stopped", extra={"event": "service.stop"})


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Social_Media AI service",
        version=__version__,
        description=(
            "Internal microservice for content moderation, caption suggestions and "
            "aggregated mood signals. Authenticated with an internal API key; not public."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,  # server-to-server: no browser credentials
        allow_methods=["POST", "GET"],
        allow_headers=["Content-Type", "X-API-Key", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "request completed",
                extra={
                    "event": "http.request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        """422 with a stable envelope (mirrors the Django error shape).

        Errors are projected onto an explicit shape: pydantic's raw payload can
        contain non-JSON-serialisable objects (e.g. the ValueError in `ctx`),
        which would turn a clean 422 into a 500.
        """
        errors = [
            {
                "type": error.get("type"),
                "loc": [str(part) for part in error.get("loc", ())],
                "msg": str(error.get("msg", "")),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Invalid request payload.",
                "code": "validation_error",
                "errors": errors,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        logger.exception(
            "unhandled error",
            extra={"event": "http.unhandled", "path": request.url.path, "error_type": type(exc).__name__},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error.", "code": "internal_error", "errors": {}},
        )

    app.include_router(health.router)
    app.include_router(moderate.router)
    app.include_router(caption.router)
    app.include_router(mood.router)
    return app


app = create_app()
