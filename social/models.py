from __future__ import annotations

from django.conf import settings
from django.db import models

from common.models import TimeStampedModel


class Follow(TimeStampedModel):
    """Directed follow edge.

    `is_active=False` models a *pending request* against a private account
    instead of a separate table — one index, one query for "requests I need to
    review".
    """

    follower = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following"
    )
    followee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followers"
    )
    is_active = models.BooleanField(default=True, help_text="False = pending follow request.")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("follower", "followee"), name="unique_follow_edge"),
            models.CheckConstraint(
                condition=~models.Q(follower=models.F("followee")), name="no_self_follow"
            ),
        ]
        indexes = [
            models.Index(fields=("followee", "is_active")),
            models.Index(fields=("follower", "is_active")),
        ]

    def __str__(self) -> str:
        state = "follows" if self.is_active else "requested"
        return f"{self.follower_id} {state} {self.followee_id}"


class Like(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes")
    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE, related_name="likes")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "post"), name="unique_user_like")]
        indexes = [models.Index(fields=("post", "-created_at"))]

    def __str__(self) -> str:
        return f"{self.user_id} likes post {self.post_id}"


class Comment(TimeStampedModel):
    post = models.ForeignKey("posts.Post", on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    content = models.TextField(max_length=1000)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=("post", "created_at"))]

    def __str__(self) -> str:
        return f"comment {self.pk} on post {self.post_id}"
