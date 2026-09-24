"""Celery tasks that talk to the AI microservice.

Nothing on the request path ever waits on the model provider: post creation
queues `moderate_post_task` and returns, the nightly beat schedule fans out
`check_user_mood_task`.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.conf import settings
from django.utils import timezone

from ai_companion.client import get_client
from ai_companion.errors import AIServiceError
from ai_companion.models import MoodCheck, WellbeingNudge

logger = logging.getLogger("ai_companion.tasks")

# Gentle, explicitly non-diagnostic wording. It offers a conversation and a
# resource link; it never labels the person or claims to know how they feel.
NUDGE_MESSAGE = (
    "Kaise ho? Pichle kuch din se aapke posts thode heavy lag rahe the — bas itna hi humne notice kiya. "
    "Agar baat karni ho to hum yahan hain, aur agar kisi professional se baat karni ho to "
    "https://findahelpline.com par free, confidential options mil jaate hain. "
    "No pressure — this is just a check-in, not a diagnosis."
)


@shared_task(
    bind=True,
    name="ai_companion.tasks.moderate_post",
    autoretry_for=(),
    max_retries=3,
    acks_late=True,
)
def moderate_post_task(self, post_id: int) -> dict:
    """POST /moderate -> apply the verdict to the post."""
    from posts.models import Post
    from posts.services import apply_moderation_verdict

    post = Post.objects.filter(pk=post_id).first()
    if post is None:
        logger.warning("moderation skipped: post missing", extra={"event": "ai.moderate.missing_post", "post_id": post_id})
        return {"post_id": post_id, "status": "missing"}

    if not post.content:
        # Image-only posts: nothing textual to moderate.
        apply_moderation_verdict(post, {"is_safe": True, "flags": [], "confidence": 1.0, "reason": "No text to review."}, provider="none")
        return {"post_id": post_id, "status": "skipped_no_text"}

    client = get_client()
    try:
        verdict = client.moderate(post.content, post_id=post.id)
    except AIServiceError as exc:
        return _handle_moderation_failure(self, post, exc)

    apply_moderation_verdict(post, verdict, provider=str(verdict.get("provider", "")))
    return {"post_id": post_id, "status": post.moderation_status, "flags": verdict.get("flags", [])}


def _handle_moderation_failure(task, post, exc: AIServiceError) -> dict:
    """Retry with backoff; on final failure apply the configured fallback.

    `fail_open`  -> publish but keep the post flagged, reason recorded, and the
                    task rescheduled for a later re-check.
    `fail_closed`-> hold the post for review.
    """
    from posts.models import Post
    from posts.services import apply_moderation_verdict

    try:
        countdown = min(2 ** task.request.retries * 5, 120)
        raise task.retry(exc=exc, countdown=countdown)
    except (MaxRetriesExceededError, AIServiceError):
        # Celery re-raises the *original* exception (not MaxRetriesExceededError)
        # once retries are exhausted, and also when the task is invoked directly
        # outside a worker. Either way: no retries left, apply the fallback.
        logger.warning(
            "moderation retries exhausted",
            extra={"event": "ai.moderate.retries_exhausted", "post_id": post.id, "error": str(exc)},
        )

    policy = getattr(settings, "MODERATION_FAILURE_POLICY", "fail_open")
    logger.error(
        "moderation unavailable — applying fallback",
        extra={
            "event": "ai.moderate.fallback", "post_id": post.id, "policy": policy, "error": str(exc),
        },
    )
    if policy == "fail_closed":
        apply_moderation_verdict(
            post,
            {
                "is_safe": False,
                "flags": ["review_required"],
                "confidence": None,
                "reason": "Our safety check is temporarily unavailable, so the post is held for review. "
                          "It will be published once the check completes.",
            },
            provider="unavailable",
            force_status=Post.ModerationStatus.HELD,
        )
        return {"post_id": post.id, "status": Post.ModerationStatus.HELD}

    apply_moderation_verdict(
        post,
        {
            "is_safe": False,
            "flags": ["safety_check_unavailable"],
            "confidence": None,
            "reason": "Published, but our automated safety check could not run. It will be retried automatically.",
        },
        provider="unavailable",
        force_status=Post.ModerationStatus.FLAGGED,
    )
    # Re-check later without blocking the author. Skipped when Celery runs
    # eagerly (tests / no broker), where a delayed call would recurse inline.
    if not settings.CELERY_TASK_ALWAYS_EAGER:
        moderate_post_task.apply_async(args=[post.id], countdown=600, queue="ai")
    return {"post_id": post.id, "status": Post.ModerationStatus.FLAGGED}


@shared_task(name="ai_companion.tasks.check_user_mood", acks_late=True)
def check_user_mood_task(user_id: int) -> dict:
    """POST /mood-check with the user's recent post texts, store the signal."""
    from accounts.models import User
    from posts.models import Post

    user = User.objects.filter(pk=user_id).first()
    if user is None:
        return {"user_id": user_id, "status": "missing"}

    sample_size = getattr(settings, "AI_MOOD_POST_SAMPLE", 20)
    posts = list(
        Post.objects.published()
        .filter(author=user, content__gt="")
        .order_by("-created_at")
        .values_list("content", flat=True)[:sample_size]
    )
    if len(posts) < 3:
        logger.info(
            "mood check skipped: not enough posts",
            extra={"event": "ai.mood.skipped", "user_id": user_id, "posts": len(posts)},
        )
        return {"user_id": user_id, "status": "skipped_insufficient_posts"}

    client = get_client()
    try:
        result = client.mood_check(posts, user_id=user.id)
    except AIServiceError as exc:
        logger.warning(
            "mood check failed", extra={"event": "ai.mood.failed", "user_id": user_id, "error": str(exc)}
        )
        return {"user_id": user_id, "status": "error", "error": exc.code}

    streak = _negative_streak_after(user, result.get("mood_signal"))
    check = MoodCheck.objects.create(
        user=user,
        signal=_normalise_signal(result.get("mood_signal")),
        suggestion=str(result.get("suggestion", ""))[:1000],
        posts_analyzed=len(posts),
        negative_streak=streak,
        provider=str(result.get("provider", "")),
        raw=result,
    )
    logger.info(
        "mood check stored",
        extra={
            "event": "ai.mood.stored", "user_id": user.id, "signal": check.signal,
            "streak": streak, "provider": check.provider,
        },
    )
    maybe_nudge(user, check)
    return {"user_id": user.id, "status": check.signal, "streak": streak}


def _normalise_signal(value) -> str:
    value = (value or "neutral").lower()
    return value if value in MoodCheck.Signal.values else MoodCheck.Signal.NEUTRAL


def _negative_streak_after(user, latest_signal) -> int:
    """Consecutive negative checks, newest first, including today's result."""
    threshold = settings.MOOD_NEGATIVE_STREAK_THRESHOLD
    signals = list(
        MoodCheck.objects.filter(user=user).order_by("-created_at").values_list("signal", flat=True)[:threshold]
    )
    signals.insert(0, _normalise_signal(latest_signal))
    streak = 0
    for signal in signals:
        if signal == MoodCheck.Signal.NEGATIVE:
            streak += 1
        else:
            break
    return streak


def maybe_nudge(user, check: MoodCheck) -> WellbeingNudge | None:
    """Create a nudge only after N consecutive negative checks, rate limited.

    Guardrails on purpose:
      * threshold (default 3 days) — one bad day never triggers anything;
      * cooldown (default 7 days) — we never nag;
      * dismissible, non-blocking, no diagnosis.
    """
    if check.negative_streak < settings.MOOD_NEGATIVE_STREAK_THRESHOLD:
        return None

    recent = WellbeingNudge.objects.filter(
        user=user, created_at__gte=timezone.now() - timedelta(days=settings.NUDGE_COOLDOWN_DAYS)
    ).exists()
    if recent:
        logger.info(
            "nudge suppressed by cooldown",
            extra={"event": "ai.nudge.suppressed", "user_id": user.id},
        )
        return None

    nudge = WellbeingNudge.objects.create(user=user, mood_check=check, message=NUDGE_MESSAGE)

    from notifications.services import notify

    notify(
        recipient=user,
        actor=None,
        notification_type="nudge",
        message="A gentle check-in is waiting for you.",
        post=None,
    )
    logger.info(
        "nudge created",
        extra={"event": "ai.nudge.created", "user_id": user.id, "nudge_id": nudge.id, "streak": check.negative_streak},
    )
    return nudge


@shared_task(name="ai_companion.tasks.run_mood_check_for_active_users")
def run_mood_check_for_active_users(days_back: int | None = None, limit: int | None = None) -> dict:
    """Nightly fan-out (Celery beat) — one child task per active user.

    Fanning out instead of looping keeps each unit retriable on its own and
    spreads the load on the AI service.
    """
    from accounts.models import User

    days_back = days_back or getattr(settings, "AI_ACTIVE_USER_DAYS", 7)
    cutoff = timezone.now() - timedelta(days=days_back)
    active_users = (
        User.objects.filter(is_active=True, posts__created_at__gte=cutoff)
        .distinct()
        .order_by("id")
        .values_list("id", flat=True)
    )
    if limit:
        active_users = active_users[:limit]

    queued = 0
    for user_id in active_users:
        check_user_mood_task.apply_async(args=[user_id], queue="ai")
        queued += 1

    logger.info(
        "mood sweep queued",
        extra={"event": "ai.mood.sweep", "queued": queued, "days_back": days_back},
    )
    return {"queued": queued}
