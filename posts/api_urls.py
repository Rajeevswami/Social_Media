from django.urls import include, path
from rest_framework.routers import SimpleRouter

from posts import api_views

app_name = "posts"

router = SimpleRouter()
# /api/v1/posts/            -> list (explore) + create
# /api/v1/posts/<pk>/       -> retrieve + update + soft delete
# /api/v1/posts/<pk>/like/  -> provided by the social app router
router.register("posts", api_views.PostViewSet, basename="post")

urlpatterns = [
    path("feed/", api_views.FeedView.as_view(), name="feed"),
    path("", include(router.urls)),
]
