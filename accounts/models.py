from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse

from accounts.managers import UserManager
from common.validators import validate_image


def avatar_upload_path(instance: User, filename: str) -> str:
    return f"avatars/{instance.id}/{filename}"


class User(AbstractUser):
    """Custom user: email unique, profile fields live here (no 1:1 profile table).

    Keeping profile data on the user model avoids a join on every feed query —
    the feed already touches users heavily.
    """

    email = models.EmailField("email address", unique=True)
    display_name = models.CharField(max_length=80, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True, validators=[validate_image])
    location = models.CharField(max_length=80, blank=True)
    website = models.URLField(max_length=200, blank=True)
    is_private = models.BooleanField(
        default=False,
        help_text="Only approved followers can see this account's posts.",
    )
    is_verified = models.BooleanField(default=False)

    objects = UserManager()

    REQUIRED_FIELDS = ["email"]

    class Meta(AbstractUser.Meta):
        ordering = ("username",)
        indexes = [models.Index(fields=("username",)), models.Index(fields=("is_private",))]

    def __str__(self) -> str:
        return self.username

    def get_absolute_url(self) -> str:
        return reverse("accounts:profile", args=[self.username])

    @property
    def profile_name(self) -> str:
        return self.display_name or self.username

    @property
    def initials(self) -> str:
        return (self.profile_name[:1] or "?").upper()

    @property
    def avatar_url(self) -> str | None:
        return self.avatar.url if self.avatar else None

    @property
    def followers_count(self) -> int:
        return self.followers.filter(is_active=True).count()

    @property
    def following_count(self) -> int:
        return self.following.filter(is_active=True).count()

    def is_followed_by(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        return self.followers.filter(follower=user, is_active=True).exists()
