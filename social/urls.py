from django.urls import path

from social import views

app_name = "social"

urlpatterns = [
    path("connections/<str:username>/<str:kind>/", views.connection_list_view, name="connections"),
    path("follow-requests/", views.follow_requests_view, name="follow_requests"),
    path(
        "follow-requests/<int:follower_id>/<str:decision>/",
        views.follow_request_decision_view,
        name="follow_request_decision",
    ),
    path("comment/<int:pk>/delete/", views.comment_delete_view, name="comment_delete_ui"),
]
