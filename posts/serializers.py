from __future__ import annotations

from rest_framework import serializers

from accounts.serializers import UserSerializer
from posts.models import Post
from posts.services import create_post


class PostAuthorSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        fields = ("id", "username", "display_name", "avatar_url", "is_verified", "is_private")


class PostSerializer(serializers.ModelSerializer):
    author = PostAuthorSerializer(read_only=True)
    image_url = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    hashtags = serializers.SerializerMethodField()
    moderation_reason = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id", "author", "content", "image_url", "location", "created_at", "edited_at",
            "like_count", "comment_count", "is_liked", "hashtags",
            "moderation_status", "moderation_reason", "moderation_flags", "is_hidden",
        )
        read_only_fields = fields

    def get_image_url(self, obj) -> str | None:
        return obj.image.url if obj.image else None

    def get_like_count(self, obj) -> int:
        # `likes` is prefetched on list endpoints — avoids an N+1 count query.
        return len(obj.likes.all()) if self._prefetched(obj, "likes") else obj.likes.count()

    def get_comment_count(self, obj) -> int:
        return len(obj.comments.all()) if self._prefetched(obj, "comments") else obj.comments.count()

    def get_is_liked(self, obj) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if self._prefetched(obj, "likes"):
            return any(like.user_id == user.id for like in obj.likes.all())
        return obj.likes.filter(user=user).exists()

    def get_hashtags(self, obj) -> list[str]:
        return obj.hashtags()

    def get_moderation_reason(self, obj) -> str:
        """Only the author and staff see the moderation detail."""
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and (user == obj.author or user.is_staff):
            return obj.moderation_reason
        return ""

    @staticmethod
    def _prefetched(obj, relation: str) -> bool:
        return relation in getattr(obj, "_prefetched_objects_cache", {})


class PostCreateSerializer(serializers.Serializer):
    content = serializers.CharField(
        max_length=Post.MAX_CONTENT_LENGTH, required=False, allow_blank=True, trim_whitespace=True
    )
    image = serializers.ImageField(required=False, allow_null=True)
    location = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def validate(self, attrs: dict) -> dict:
        if not (attrs.get("content") or "").strip() and not attrs.get("image"):
            raise serializers.ValidationError({"content": "Write something or attach an image."})
        return attrs

    def create(self, validated_data: dict) -> Post:
        return create_post(author=self.context["request"].user, **validated_data)


class PostUpdateSerializer(serializers.ModelSerializer):
    """Editing re-triggers moderation — an edit must not bypass the check."""

    class Meta:
        model = Post
        fields = ("content", "image", "location")

    def validate(self, attrs: dict) -> dict:
        content = attrs.get("content", self.instance.content if self.instance else "")
        image = attrs.get("image", self.instance.image if self.instance else None)
        if not (content or "").strip() and not image:
            raise serializers.ValidationError({"content": "A post needs text or an image."})
        return attrs

    def update(self, instance: Post, validated_data: dict) -> Post:
        from django.utils import timezone

        from ai_companion.tasks import moderate_post_task

        instance = super().update(instance, validated_data)
        instance.edited_at = timezone.now()
        instance.moderation_status = Post.ModerationStatus.PENDING
        instance.moderation_reason = ""
        instance.moderation_flags = []
        instance.save(update_fields=["edited_at", "moderation_status", "moderation_reason", "moderation_flags", "updated_at"])
        moderate_post_task.delay(instance.id)
        return instance
