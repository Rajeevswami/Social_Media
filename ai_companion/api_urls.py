from django.urls import path

from ai_companion import api_views

app_name = "ai_companion"

urlpatterns = [
    path("ai/caption/", api_views.CaptionView.as_view(), name="caption"),
    path("ai/moderate/", api_views.ModeratePreviewView.as_view(), name="moderate"),
    path("ai/mood/", api_views.MoodSummaryView.as_view(), name="mood"),
    path("ai/nudge/", api_views.ActiveNudgeView.as_view(), name="nudge"),
    path("ai/nudge/<int:pk>/dismiss/", api_views.NudgeDismissView.as_view(), name="nudge-dismiss"),
]
