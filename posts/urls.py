from django.urls import path

from posts import views

app_name = "posts"

urlpatterns = [
    path("", views.feed_view, name="feed"),
    path("explore/", views.explore_view, name="explore"),
    path("compose/", views.compose_view, name="compose"),
    path("p/<int:pk>/", views.post_detail_view, name="detail"),
    path("p/<int:pk>/edit/", views.post_edit_view, name="edit"),
    path("p/<int:pk>/delete/", views.post_delete_view, name="delete"),
]
