"""Social graph + engagement API."""
from __future__ import annotations

from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, mixins, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from posts.api_views import with_counts
from posts.models import Post
from social.models import Comment, Follow
from social.serializers import CommentSerializer, FollowSerializer
from social.services import FollowError, accept_follow_request, add_comment, reject_follow_request, toggle_follow, toggle_like


@extend_schema(request=None, responses={200: OpenApiResponse(description="New follow state")})
class FollowToggleView(APIView):
    """POST /api/v1/users/<username>/follow/ — idempotent follow/unfollow."""

    permission_classes = (IsAuthenticated,)

    def post(self, request, username: str):
        target = get_object_or_404(User, username=username)
        try:
            edge, follow_status = toggle_follow(request.user, target)
        except FollowError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "status": follow_status,
                "username": target.username,
                "followers_count": target.followers_count,
                "edge_id": edge.id if edge else None,
            }
        )


class FollowerListView(generics.ListAPIView):
    serializer_class = FollowSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Follow.objects.none()
        user = self._visible_profile()
        return (
            Follow.objects.filter(followee=user, is_active=True)
            .select_related("follower", "followee")
            .order_by("-created_at")
        )

    def _visible_profile(self):
        """404 rather than leak a private account's social graph."""
        user = get_object_or_404(User, username=self.kwargs["username"])
        if not user.can_view(self.request.user):
            raise Http404
        return user


class FollowingListView(generics.ListAPIView):
    serializer_class = FollowSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Follow.objects.none()
        user = self._visible_profile()
        return (
            Follow.objects.filter(follower=user, is_active=True)
            .select_related("follower", "followee")
            .order_by("-created_at")
        )

    def _visible_profile(self):
        user = get_object_or_404(User, username=self.kwargs["username"])
        if not user.can_view(self.request.user):
            raise Http404
        return user


class FollowRequestListView(generics.ListAPIView):
    """Pending follow requests for the authenticated user's private account."""

    serializer_class = FollowSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Follow.objects.none()
        return (
            Follow.objects.filter(followee=self.request.user, is_active=False)
            .select_related("follower", "followee")
            .order_by("-created_at")
        )


@extend_schema(request=None, responses={200: OpenApiResponse(description="Request accepted or rejected")})
class FollowRequestDecisionView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, follower_id: int, decision: str):
        if decision not in ("accept", "reject"):
            return Response({"detail": "decision must be 'accept' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)
        follower = get_object_or_404(User, pk=follower_id)
        if decision == "accept":
            accept_follow_request(request.user, follower)
        else:
            reject_follow_request(request.user, follower)
        return Response({"detail": f"Request {decision}ed.", "status": decision})


@extend_schema(request=None, responses={200: OpenApiResponse(description="Like state and count")})
class LikeToggleView(APIView):
    """POST /api/v1/posts/<pk>/like/ — idempotent like/unlike."""

    permission_classes = (IsAuthenticated,)

    def post(self, request, pk: int):
        post = get_object_or_404(with_counts(Post.objects.visible_to(request.user)), pk=pk)
        is_liked, like_count = toggle_like(request.user, post)
        return Response({"is_liked": is_liked, "like_count": like_count, "post_id": post.id})


class CommentListCreateView(mixins.ListModelMixin, generics.GenericAPIView):
    serializer_class = CommentSerializer
    permission_classes = (IsAuthenticated,)

    def get_post(self):
        """Comments inherit the post's visibility - enforced here explicitly.

        Reading a private account's comments used to be blocked only as a side
        effect of `get_serializer_context()` raising 404, which is far too
        indirect to rely on: any future refactor that stops calling the
        serializer context would silently open the hole.
        """
        if not hasattr(self, "_post"):
            self._post = get_object_or_404(Post.objects.visible_to(self.request.user), pk=self.kwargs["pk"])
        return self._post

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Comment.objects.none()
        return (
            Comment.objects.filter(post=self.get_post(), parent__isnull=True)
            .select_related("author")
            .prefetch_related("replies__author")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["post"] = self.get_post()
        return context

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save()
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class CommentDestroyView(generics.DestroyAPIView):
    """Author of the comment or of the post may delete it."""

    serializer_class = CommentSerializer
    permission_classes = (IsAuthenticated,)
    queryset = Comment.objects.all()

    def perform_destroy(self, instance: Comment) -> None:
        user = self.request.user
        if user not in (instance.author, instance.post.author) and not user.is_staff:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You cannot delete this comment.")
        instance.delete()


@extend_schema(request=CommentSerializer, responses={201: CommentSerializer})
class CommentCreateShortcut(APIView):
    """Convenience endpoint used by the detail page form via fetch."""

    permission_classes = (IsAuthenticated,)

    def post(self, request, pk: int):
        post = get_object_or_404(Post.objects.visible_to(request.user), pk=pk)
        try:
            comment = add_comment(request.user, post, request.data.get("content", ""))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)
