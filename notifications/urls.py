from django.urls import path

from notifications import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list_view, name="list"),
    path("read-all/", views.mark_all_read_view, name="read_all"),
]
