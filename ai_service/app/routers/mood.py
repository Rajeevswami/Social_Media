"""POST /mood-check — aggregated tone over a user's recent posts.

Explicitly a coarse signal, never a diagnosis: the response always carries a
disclaimer, and the Django side only ever turns a sustained negative streak
into one dismissible, non-blocking nudge.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.core.dependencies import rate_limited_api_key
from app.providers.base import ProviderError
from app.providers.factory import get_provider, init_fallback_active, run_with_fallback
from app.providers.heuristic import HeuristicProvider
from app.schemas.mood import MoodCheckRequest, MoodCheckResponse

logger = logging.getLogger("ai.mood")

router = APIRouter(tags=["mood"], dependencies=[Depends(rate_limited_api_key)])


@router.post("/mood-check", response_model=MoodCheckResponse)
async def mood_check(payload: MoodCheckRequest) -> MoodCheckResponse:
    settings = get_settings()
    texts = payload.texts[: settings.max_mood_texts]

    provider = get_provider()
    try:
        verdict, degraded = await run_with_fallback(
            lambda: provider.mood(texts),
            lambda: HeuristicProvider().mood(texts),
            event="mood",
        )
    except ProviderError as exc:
        logger.error("mood analysis failed", extra={"event": "mood.failed", "error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mood provider unavailable.",
        ) from exc

    degraded = degraded or init_fallback_active()
    answered_by = "heuristic" if degraded else provider.name

    logger.info(
        "mood check complete",
        extra={
            "event": "mood.done",
            "user_id": payload.user_id,
            "signal": verdict.signal,
            "posts_analyzed": len(texts),
            "provider": answered_by,
            "degraded": degraded,
        },
    )
    return MoodCheckResponse(
        mood_signal=verdict.signal,
        suggestion=verdict.suggestion,
        posts_analyzed=len(texts),
        positive_ratio=verdict.positive_ratio,
        negative_ratio=verdict.negative_ratio,
        provider=answered_by,
        degraded=degraded,
    )
