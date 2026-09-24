"""AI-facing API endpoints.

Rate limited by `AIRateThrottle` (scope `ai`, default 20/hour/user) because
every call costs money at the model provider. The FastAPI service enforces a
second limit keyed on the internal API key.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_companion.client import get_client
from ai_companion.errors import AIServiceRejected, AIServiceError
from ai_companion.models import MoodCheck, WellbeingNudge
from ai_companion.serializers import (
    CaptionRequestSerializer,
    CaptionResponseSerializer,
    MoodCheckSerializer,
    ModeratePreviewSerializer,
    NudgeSerializer,
)
from common.throttles import AIRateThrottle


class _AIBaseView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (AIRateThrottle,)

    def _service_error_response(self, exc: AIServiceError):
        """Translate AI failures into honest, non-leaky HTTP responses."""
        if isinstance(exc, AIServiceRejected) and exc.status_code == 429:
            return Response(
                {"detail": "AI rate limit reached. Please try again shortly.", "code": "ai_rate_limited"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return Response(
            {"detail": "The AI service is unavailable right now. Nothing was blocked.", "code": exc.code},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@extend_schema(request=CaptionRequestSerializer, responses={200: CaptionResponseSerializer})
class CaptionView(_AIBaseView):
    """POST /api/v1/ai/caption/ — 2-3 caption suggestions for an idea."""

    def post(self, request, *args, **kwargs):
        serializer = CaptionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = get_client().caption(
                serializer.validated_data["idea"],
                tone=serializer.validated_data.get("tone"),
                count=serializer.validated_data.get("count", 3),
            )
        except AIServiceError as exc:
            return self._service_error_response(exc)

        suggestions = [s for s in (result.get("suggestions") or []) if isinstance(s, str) and s.strip()]
        return Response(
            {
                "suggestions": suggestions[:3],
                "provider": result.get("provider", ""),
                "idea": serializer.validated_data["idea"],
            }
        )


@extend_schema(
    request=ModeratePreviewSerializer,
    responses={200: OpenApiResponse(description="Verdict preview (no post is created)")},
)
class ModeratePreviewView(_AIBaseView):
    """POST /api/v1/ai/moderate/ — dry-run check, does NOT create a post."""

    def post(self, request, *args, **kwargs):
        serializer = ModeratePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = get_client().moderate(serializer.validated_data["text"])
        except AIServiceError as exc:
            return self._service_error_response(exc)
        return Response(
            {
                "is_safe": bool(result.get("is_safe", True)),
                "flags": result.get("flags", []),
                "confidence": result.get("confidence"),
                "reason": result.get("reason", ""),
                "provider": result.get("provider", ""),
            }
        )


@extend_schema(request=None, responses={200: OpenApiResponse(description="Own mood history + active nudge")})
class MoodSummaryView(APIView):
    """GET /api/v1/ai/mood/ — the user's own mood history (never shared)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        checks = MoodCheck.objects.filter(user=request.user)[:30]
        latest = checks[0] if checks else None
        active_nudge = (
            WellbeingNudge.objects.filter(user=request.user, dismissed_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        return Response(
            {
                "checks": MoodCheckSerializer(checks, many=True).data,
                "latest": MoodCheckSerializer(latest).data if latest else None,
                "active_nudge": NudgeSerializer(active_nudge).data if active_nudge else None,
                "disclaimer": "Coarse text-signal only. Not a diagnosis or medical advice.",
            }
        )


@extend_schema(request=None, responses={200: OpenApiResponse(description="Active nudge, if any")})
class ActiveNudgeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        nudge = (
            WellbeingNudge.objects.filter(user=request.user, dismissed_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if nudge is None:
            return Response({"nudge": None})
        return Response({"nudge": NudgeSerializer(nudge).data})


@extend_schema(request=None, responses={200: NudgeSerializer})
class NudgeDismissView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, pk: int, *args, **kwargs):
        from django.utils import timezone

        nudge = WellbeingNudge.objects.filter(pk=pk, user=request.user).first()
        if nudge is None:
            return Response({"detail": "Nudge not found."}, status=status.HTTP_404_NOT_FOUND)
        nudge.dismissed_at = timezone.now()
        nudge.save(update_fields=["dismissed_at", "updated_at"])
        return Response(NudgeSerializer(nudge).data)
