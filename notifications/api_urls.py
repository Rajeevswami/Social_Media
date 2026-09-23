from django.urls import path

from notifications import api_views

app_name = "notifications"

urlpatterns = [
    path("notifications/", api_views.NotificationListView.as_view(), name="list"),
    path("notifications/unread-count/", api_views.unread_count_view, name="unread-count"),
    path("notifications/read-all/", api_views.mark_all_read_view, name="read-all"),
    path("notifications/<int:pk>/read/", api_views.NotificationReadView.as_view(), name="read"),
]
