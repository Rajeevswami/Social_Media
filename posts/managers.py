from django.db import models


class PostQuerySet(models.QuerySet):
    def published(self):
        """Posts that are allowed on a feed (not held, not hidden)."""
        return self.exclude(moderation_status="held").filter(is_hidden=False)

    def public_only(self):
        return self.published().filter(author__is_private=False)

    def visible_to(self, user):
        """Posts a given user is allowed to see."""
        qs = self.published()
        if not (user and user.is_authenticated):
            return qs.filter(author__is_private=False)
        return qs.filter(
            models.Q(author__is_private=False)
            | models.Q(author__followers__follower=user, author__followers__is_active=True)
            | models.Q(author=user)
        ).distinct()

    def feed_for(self, user):
        """Home feed: own posts + posts from accounts the user follows."""
        following_ids = user.following.filter(is_active=True).values_list("followee_id", flat=True)
        return (
            self.published()
            .filter(models.Q(author_id__in=following_ids) | models.Q(author=user))
            .order_by("-created_at")
        )


class PostManager(models.Manager):
    def get_queryset(self) -> PostQuerySet:
        return PostQuerySet(self.model, using=self._db)

    def published(self):
        return self.get_queryset().published()

    def public_only(self):
        return self.get_queryset().public_only()

    def visible_to(self, user):
        return self.get_queryset().visible_to(user)

    def feed_for(self, user):
        return self.get_queryset().feed_for(user)
