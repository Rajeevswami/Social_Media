"""UI endpoints for the AI companion (caption helper + wellbeing nudges)."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from ai_companion.api_views import CaptionView
from ai_companion.models import MoodCheck, WellbeingNudge

# Reuses the DRF view (session auth + `ai` throttle) so the browser and API
# clients share one code path and one rate limit.
caption_view = CaptionView.as_view()


@login_required
def nudge_view(request):
    nudges = WellbeingNudge.objects.filter(user=request.user).select_related("mood_check")
    checks = MoodCheck.objects.filter(user=request.user)[:14]
    active = nudges.filter(dismissed_at__isnull=True).first()
    return render(
        request,
        "ai_companion/nudge.html",
        {"nudges": nudges, "checks": checks, "active_nudge": active, "active_tab": "profile"},
    )


@login_required
@require_http_methods(["POST"])
def nudge_dismiss_view(request, pk: int):
    from django.utils import timezone

    nudge = get_object_or_404(WellbeingNudge, pk=pk, user=request.user)
    nudge.dismissed_at = timezone.now()
    nudge.save(update_fields=["dismissed_at", "updated_at"])
    return redirect("posts:feed")
