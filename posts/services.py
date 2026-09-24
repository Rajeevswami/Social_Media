"""Post domain logic.

Kept out of views so the same rules apply to the API, the template UI, tests
and management commands.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from posts.models import Post

logger = logging.getLogger("posts.moderation")


def create_post(author, content: str = "", image=None, location: str = "") -> Post:
    """Persist a post and queue it for AI moderation.

    The request returns immediately; moderation runs in Celery. The post is
    `pending` until a verdict lands, which keeps the UX responsive while still
    guaranteeing every post is reviewed.
    """
    content = (content or "").strip()
    if not content and not image:
        raise ValueError("A post needs text or an image.")
    if len(content) > Post.MAX_CONTENT_LENGTH:
        raise ValueError(f"Post is too long (max {Post.MAX_CONTENT_LENGTH} characters).")

    with transaction.atomic():
        post = Post.objects.create(
            author=author,
            content=content,
            image=image,
            location=(location or "").strip(),
            moderation_status=Post.ModerationStatus.PENDING,
        )

    # Imported lazily: keeps the module importable without a Celery app and
    # avoids a circular import at app-loading time.
    from ai_companion.tasks import moderate_post_task

    moderate_post_task.delay(post.id)
    logger.info(
        "post queued for moderation",
        extra={"event": "post.moderation.queued", "post_id": post.id, "author": author.username},
    )

    if settings.CELERY_TASK_ALWAYS_EAGER:
        # The task ran inline and saved its own instance; refresh ours so the
        # API/UI render the real verdict instead of a stale "pending".
        post.refresh_from_db()
    return post


def apply_moderation_verdict(post: Post, verdict: dict, provider: str = "", force_status: str | None = None) -> Post:
    """Translate an AI moderation verdict into a post state.

    Failure-safe by design: a verdict that says "safe" approves; anything else
    follows MODERATION_POLICY, and the reason is always recorded so the author
    (and moderators) can see why.

    `force_status` lets outage handling bypass the policy mapping (a held post
    must stay held even when MODERATION_POLICY=auto_publish).
    """
    is_safe = bool(verdict.get("is_safe", True))
    flags = verdict.get("flags") or []
    reason = verdict.get("reason") or ""

    if force_status is not None:
        status = force_status
    elif is_safe:
        status = Post.ModerationStatus.APPROVED
    elif settings.MODERATION_POLICY == "hold_unsafe":
        status = Post.ModerationStatus.HELD
    else:
        status = Post.ModerationStatus.FLAGGED

    post.moderation_status = status
    post.moderation_flags = flags
    post.moderation_confidence = verdict.get("confidence")
    post.moderation_reason = reason or (
        "Looks good — automated check passed."
        if is_safe
        else f"Automated check flagged: {', '.join(flags) if flags else 'policy violation'}."
    )
    post.moderation_provider = provider
    post.moderation_checked_at = timezone.now()
    post.save(
        update_fields=[
            "moderation_status", "moderation_flags", "moderation_confidence",
            "moderation_reason", "moderation_provider", "moderation_checked_at", "updated_at",
        ]
    )

    if status in (Post.ModerationStatus.FLAGGED, Post.ModerationStatus.HELD):
        _notify_author_of_flag(post, status)

    logger.info(
        "moderation verdict applied",
        extra={
            "event": "post.moderation.verdict",
            "post_id": post.id,
            "status": status,
            "flags": flags,
            "confidence": post.moderation_confidence,
            "provider": provider,
        },
    )
    return post


def _notify_author_of_flag(post: Post, status: str) -> None:
    """Tell the author what happened — never a silent block."""
    from notifications.services import notify

    if status == Post.ModerationStatus.HELD:
        message = (
            "Your post is temporarily held for review. "
            f"Reason: {post.moderation_reason} You can edit or delete it from your profile."
        )
    else:
        message = (
            "Your post was published but flagged by our automated safety check. "
            f"Reason: {post.moderation_reason}"
        )
    notify(
        recipient=post.author,
        actor=None,
        notification_type="moderation",
        message=message,
        post=post,
    )
