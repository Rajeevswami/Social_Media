"""DRF views for posts: feed, CRUD, explore."""
from __future__ import annotations

from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from common.permissions import IsOwnerOrReadOnly
from posts.models import Post
from posts.serializers import PostCreateSerializer, PostSerializer, PostUpdateSerializer
from social.models import Like


def with_counts(qs):
    """Every feed query needs author + like/comment counts without N+1."""
    return qs.select_related("author").prefetch_related(
        Prefetch("likes", queryset=Like.objects.select_related("user")),
        "comments",
    )


@extend_schema_view(
    list=extend_schema(
        summary="Home feed: your posts + posts from accounts you follow",
        responses=PostSerializer(many=True),
    ),
)
class FeedView(generics.ListAPIView):
    serializer_class = PostSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        # drf-spectacular instantiates the view with an AnonymousUser while
        # building the schema; degrade instead of blowing up generation.
        if getattr(self, "swagger_fake_view", False):
            return Post.objects.none()
        return with_counts(Post.objects.feed_for(self.request.user))


@extend_schema_view(
    list=extend_schema(summary="Explore: public posts from everyone"),
    create=extend_schema(summary="Create a post (queued for AI moderation)"),
)
class PostViewSet(viewsets.ModelViewSet):
    """Create/read/update/delete posts.

    Delete is a soft delete (`is_hidden=True`) so moderation history and
    notifications stay consistent.
    """

    serializer_class = PostSerializer
    permission_classes = (IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly)
    lookup_field = "pk"

    def get_queryset(self):
        qs = with_counts(Post.objects.visible_to(self.request.user))
        author = self.request.query_params.get("author")
        if author:
            qs = qs.filter(author__username=author)
        tag = self.request.query_params.get("hashtag")
        if tag:
            qs = qs.filter(content__icontains=f"#{tag.lstrip('#')}")
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return PostCreateSerializer
        if self.action in ("update", "partial_update"):
            return PostUpdateSerializer
        return PostSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedOrReadOnly()]
        # Mutations need BOTH: authentication *and* ownership. Overriding
        # get_permissions replaces the class-level list, so the owner check
        # must be repeated here — otherwise any user could edit any post.
        return [IsAuthenticated(), IsOwnerOrReadOnly()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        post = serializer.save()
        return Response(
            PostSerializer(post, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        post = self.get_object()
        post.is_hidden = True
        post.save(update_fields=["is_hidden", "updated_at"])
        return Response({"detail": "Post deleted."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        post = self.get_object()
        post.is_hidden = False
        post.save(update_fields=["is_hidden", "updated_at"])
        return Response(PostSerializer(post, context={"request": request}).data)

    @action(detail=True, methods=["get"], url_path="moderation", permission_classes=[IsAuthenticated])
    def moderation(self, request, pk=None):
        """Moderation audit trail for a post (author/staff only)."""
        post = self.get_object()
        if request.user != post.author and not request.user.is_staff:
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            {
                "status": post.moderation_status,
                "reason": post.moderation_reason,
                "flags": post.moderation_flags,
                "confidence": post.moderation_confidence,
                "provider": post.moderation_provider,
                "checked_at": post.moderation_checked_at,
            }
        )
