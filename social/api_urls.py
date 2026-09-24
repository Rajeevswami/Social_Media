from django.urls import path

from social import api_views

app_name = "social"

urlpatterns = [
    path("users/<str:username>/follow/", api_views.FollowToggleView.as_view(), name="follow-toggle"),
    path("users/<str:username>/followers/", api_views.FollowerListView.as_view(), name="followers"),
    path("users/<str:username>/following/", api_views.FollowingListView.as_view(), name="following"),
    path("follow-requests/", api_views.FollowRequestListView.as_view(), name="follow-requests"),
    path(
        "follow-requests/<int:follower_id>/<str:decision>/",
        api_views.FollowRequestDecisionView.as_view(),
        name="follow-request-decision",
    ),
    path("posts/<int:pk>/like/", api_views.LikeToggleView.as_view(), name="like-toggle"),
    path("posts/<int:pk>/comments/", api_views.CommentListCreateView.as_view(), name="comments"),
    path("posts/<int:pk>/comment/", api_views.CommentCreateShortcut.as_view(), name="comment-create"),
    path("comments/<int:pk>/", api_views.CommentDestroyView.as_view(), name="comment-detail"),
]
