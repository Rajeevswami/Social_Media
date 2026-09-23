from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app import __version__
from app.core.config import get_settings
from app.providers.factory import get_provider

router = APIRouter(tags=["health"])

_STARTED = time.monotonic()


@router.get("/health")
async def health() -> JSONResponse:
    """Unauthenticated liveness/readiness probe for the platform."""
    settings = get_settings()
    provider = get_provider()
    return JSONResponse(
        {
            "status": "ok",
            "service": settings.service_name,
            "version": __version__,
            "provider": provider.name,
            "degraded_mode": provider.name == "heuristic" and settings.provider != "heuristic",
            "environment": settings.environment,
            "uptime_seconds": round(time.monotonic() - _STARTED, 1),
        }
    )
