"""POST /moderate — text safety classification."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.core.dependencies import rate_limited_api_key
from app.providers.base import ProviderError
from app.providers.factory import get_provider, init_fallback_active, run_with_fallback
from app.providers.heuristic import HeuristicProvider
from app.schemas.moderation import ModerationFlag, ModerationRequest, ModerationResponse

logger = logging.getLogger("ai.moderate")

router = APIRouter(tags=["moderation"], dependencies=[Depends(rate_limited_api_key)])


def _heuristic() -> HeuristicProvider:
    settings = get_settings()
    return HeuristicProvider(
        toxicity_threshold=settings.toxicity_threshold, spam_threshold=settings.spam_threshold
    )


@router.post("/moderate", response_model=ModerationResponse)
async def moderate(payload: ModerationRequest) -> ModerationResponse:
    """Classify one post.

    Never raises on model failure when fallback is enabled: an unavailable
    provider must not break publishing. `degraded=True` tells the caller the
    answer came from the local heuristic.
    """
    settings = get_settings()
    if len(payload.text) > settings.max_text_length:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"text exceeds {settings.max_text_length} characters",
        )

    provider = get_provider()
    try:
        verdict, degraded = await run_with_fallback(
            lambda: provider.moderate(payload.text),
            lambda: _heuristic().moderate(payload.text),
            event="moderate",
        )
    except ProviderError as exc:
        logger.error("moderation failed", extra={"event": "moderate.failed", "error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Moderation provider unavailable.",
        ) from exc

    # A provider that could not even be built is degraded too.
    degraded = degraded or init_fallback_active()
    # Report who actually answered, so the audit trail is honest.
    answered_by = "heuristic" if degraded else provider.name

    logger.info(
        "moderation complete",
        extra={
            "event": "moderate.done",
            "post_id": payload.post_id,
            "is_safe": verdict.is_safe,
            "flags": verdict.flags,
            "provider": answered_by,
            "degraded": degraded,
        },
    )
    return ModerationResponse(
        is_safe=verdict.is_safe,
        flags=verdict.flags,
        scores=[ModerationFlag(category=category, score=score) for category, score in verdict.scores.items()],
        confidence=verdict.confidence,
        reason=verdict.reason,
        provider=answered_by,
        degraded=degraded,
        post_id=payload.post_id,
    )
