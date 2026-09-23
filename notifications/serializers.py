from rest_framework import serializers

from accounts.serializers import UserSerializer
from notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)
    link = serializers.CharField(read_only=True)
    post_id = serializers.IntegerField(source="post.id", read_only=True, default=None)

    class Meta:
        model = Notification
        fields = (
            "id", "notification_type", "message", "actor", "post_id",
            "is_read", "read_at", "created_at", "link",
        )
        read_only_fields = fields
