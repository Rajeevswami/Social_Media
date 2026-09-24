from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse

from common.models import TimeStampedModel


class Notification(TimeStampedModel):
    """Single inbox row.

    Deliberately DB-backed: it survives restarts, is queryable for the unread
    badge, and can be replayed to a websocket/FCM fan-out later without
    changing producers.
    """

    class Type(models.TextChoices):
        LIKE = "like", "Like"
        COMMENT = "comment", "Comment"
        FOLLOW = "follow", "Follow"
        MENTION = "mention", "Mention"
        MODERATION = "moderation", "Moderation"
        NUDGE = "nudge", "Wellbeing nudge"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="triggered_notifications"
    )
    notification_type = models.CharField(max_length=16, choices=Type.choices, db_index=True)
    message = models.CharField(max_length=280)
    post = models.ForeignKey(
        "posts.Post", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    comment = models.ForeignKey(
        "social.Comment", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("recipient", "is_read", "-created_at"))]

    def __str__(self) -> str:
        return f"{self.notification_type} -> {self.recipient_id}"

    @property
    def link(self) -> str:
        if self.notification_type == self.Type.NUDGE:
            return reverse("ai_companion:nudge")
        if self.post_id:
            return self.post.get_absolute_url()
        if self.actor_id:
            return reverse("accounts:profile", args=[self.actor.username])
        return reverse("notifications:list")

    def mark_read(self) -> None:
        from django.utils import timezone

        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at", "updated_at"])
