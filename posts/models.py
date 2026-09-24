from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse

from common.models import TimeStampedModel
from common.validators import validate_image
from posts.managers import PostManager


def post_upload_path(instance: Post, filename: str) -> str:
    return f"posts/{instance.author_id}/{instance.id or 'new'}/{filename}"


class Post(TimeStampedModel):
    """A feed item.

    Moderation state machine::

        pending ──(AI verdict safe)──▶ approved
        pending ──(AI verdict unsafe + policy=hold_unsafe)──▶ held
        pending ──(AI verdict unsafe + policy=auto_publish)──▶ flagged

    Nothing is ever deleted silently: `moderation_reason` always explains the
    verdict, and `held`/`flagged` posts stay visible to their author with the
    reason shown, so they can appeal or edit.
    """

    class ModerationStatus(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        FLAGGED = "flagged", "Flagged"
        HELD = "held", "Held for review"

    MAX_CONTENT_LENGTH = 2000

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    content = models.TextField(max_length=MAX_CONTENT_LENGTH, blank=True)
    image = models.ImageField(
        upload_to=post_upload_path, blank=True, null=True, validators=[validate_image]
    )
    location = models.CharField(max_length=120, blank=True)

    moderation_status = models.CharField(
        max_length=16, choices=ModerationStatus.choices, default=ModerationStatus.PENDING, db_index=True
    )
    moderation_reason = models.TextField(blank=True, default="")
    moderation_flags = models.JSONField(default=list, blank=True)
    moderation_confidence = models.FloatField(null=True, blank=True)
    moderation_checked_at = models.DateTimeField(null=True, blank=True)
    moderation_provider = models.CharField(max_length=40, blank=True, default="")

    is_hidden = models.BooleanField(default=False, help_text="Soft-deleted by the author.")
    edited_at = models.DateTimeField(null=True, blank=True)

    objects = PostManager()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("-created_at", "is_hidden")),
            models.Index(fields=("author", "-created_at")),
            models.Index(fields=("moderation_status",)),
        ]
        constraints = [
            # An unset ImageField stores '' rather than NULL, so testing
            # `image__isnull=False` alone would make this constraint always
            # true and therefore useless. Both the NULL and '' cases must be
            # excluded for the "has an image" branch to mean anything.
            models.CheckConstraint(
                name="post_requires_text_or_image",
                condition=models.Q(content__gt="")
                | (models.Q(image__isnull=False) & ~models.Q(image="")),
            )
        ]

    def __str__(self) -> str:
        return f"Post {self.pk} by {self.author_id}"

    def get_absolute_url(self) -> str:
        return reverse("posts:detail", args=[self.pk])

    # -- visibility ------------------------------------------------------
    @property
    def is_published(self) -> bool:
        """A post is on the feed unless it was held back or hidden."""
        return self.moderation_status != self.ModerationStatus.HELD and not self.is_hidden

    @property
    def is_public(self) -> bool:
        return self.is_published and not self.author.is_private

    @property
    def like_count(self) -> int:
        return self.likes.count()

    @property
    def comment_count(self) -> int:
        return self.comments.count()

    def visible_to(self, user) -> bool:
        if self.is_hidden or self.moderation_status == self.ModerationStatus.HELD:
            return bool(user.is_authenticated and (user == self.author or user.is_staff))
        if not self.author.is_private:
            return True
        return self.author.is_followed_by(user)

    def hashtags(self) -> list[str]:
        import re

        return sorted({m.group(1).lower() for m in re.finditer(r"#(\w{2,30})", self.content or "")})
