"""POST /caption — 1-3 caption suggestions from a short idea."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import rate_limited_api_key
from app.providers.base import ProviderError
from app.providers.factory import get_provider, init_fallback_active, run_with_fallback
from app.providers.heuristic import HeuristicProvider
from app.schemas.caption import CaptionRequest, CaptionResponse

logger = logging.getLogger("ai.caption")

router = APIRouter(tags=["caption"], dependencies=[Depends(rate_limited_api_key)])


@router.post("/caption", response_model=CaptionResponse)
async def caption(payload: CaptionRequest) -> CaptionResponse:
    provider = get_provider()
    try:
        result, degraded = await run_with_fallback(
            lambda: provider.captions(payload.idea, payload.tone, payload.count),
            lambda: HeuristicProvider().captions(payload.idea, payload.tone, payload.count),
            event="caption",
        )
    except ProviderError as exc:
        logger.error("caption generation failed", extra={"event": "caption.failed", "error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Caption provider unavailable.",
        ) from exc

    degraded = degraded or init_fallback_active()
    answered_by = "heuristic" if degraded else provider.name

    logger.info(
        "captions generated",
        extra={
            "event": "caption.done",
            "count": len(result.suggestions),
            "tone": payload.tone,
            "provider": answered_by,
            "degraded": degraded,
        },
    )
    return CaptionResponse(suggestions=result.suggestions[:3], provider=answered_by, degraded=degraded)
