from __future__ import annotations

from rest_framework import serializers

from accounts.serializers import UserSerializer
from social.models import Comment, Follow


class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    parent_id = serializers.PrimaryKeyRelatedField(
        source="parent", queryset=Comment.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Comment
        fields = ("id", "author", "content", "created_at", "parent_id")
        read_only_fields = ("id", "author", "created_at")

    def validate_content(self, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Comment cannot be empty.")
        return value

    def create(self, validated_data: dict) -> Comment:
        from social.services import add_comment

        post = self.context["post"]
        parent = validated_data.pop("parent", None)
        if parent is not None and parent.post_id != post.id:
            raise serializers.ValidationError({"parent_id": "Reply must belong to the same post."})
        return add_comment(
            actor=self.context["request"].user,
            post=post,
            content=validated_data["content"],
            parent=parent,
        )


class FollowSerializer(serializers.ModelSerializer):
    follower = UserSerializer(read_only=True)
    followee = UserSerializer(read_only=True)

    class Meta:
        model = Follow
        fields = ("id", "follower", "followee", "is_active", "created_at")
        read_only_fields = fields
