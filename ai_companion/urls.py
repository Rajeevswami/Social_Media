from django.urls import path

from ai_companion import views

app_name = "ai_companion"

urlpatterns = [
    path("caption/", views.caption_view, name="caption"),
    path("check-in/", views.nudge_view, name="nudge"),
    path("check-in/<int:pk>/dismiss/", views.nudge_dismiss_view, name="nudge_dismiss"),
]
