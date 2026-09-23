from __future__ import annotations

from django.conf import settings
from django.db import models

from common.models import TimeStampedModel


class MoodCheck(TimeStampedModel):
    """One nightly mood sweep for one user.

    This is a *signal log*, not a medical record: it stores the model's coarse
    label and the suggestion text, never a diagnosis.
    """

    class Signal(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEUTRAL = "neutral", "Neutral"
        NEGATIVE = "negative", "Negative"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mood_checks")
    signal = models.CharField(max_length=10, choices=Signal.choices, db_index=True)
    suggestion = models.TextField(blank=True, default="")
    posts_analyzed = models.PositiveSmallIntegerField(default=0)
    negative_streak = models.PositiveSmallIntegerField(default=0)
    provider = models.CharField(max_length=40, blank=True, default="")
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("user", "-created_at"))]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.signal}@{self.created_at:%Y-%m-%d}"


class WellbeingNudge(TimeStampedModel):
    """A gentle, dismissible in-app nudge — never a diagnosis, never blocking."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="nudges")
    mood_check = models.ForeignKey(MoodCheck, on_delete=models.SET_NULL, null=True, blank=True, related_name="nudges")
    message = models.TextField()
    dismissed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("user", "dismissed_at"))]

    def __str__(self) -> str:
        return f"nudge for {self.user_id} ({self.created_at:%Y-%m-%d})"

    @property
    def is_active(self) -> bool:
        return self.dismissed_at is None
