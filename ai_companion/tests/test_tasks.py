"""Mood-check task, negative-streak logic and nudge guardrails."""
from __future__ import annotations

from datetime import timedelta
from unittest import mock

import pytest
from django.test import override_settings
from django.utils import timezone

from ai_companion.models import MoodCheck, WellbeingNudge
from ai_companion.tasks import check_user_mood_task, maybe_nudge, run_mood_check_for_active_users
from posts.models import Post


def _seed_posts(user, count=5, prefix="rough day"):
    for i in range(count):
        Post.objects.create(
            author=user, content=f"{prefix} {i}", moderation_status=Post.ModerationStatus.APPROVED
        )


@pytest.mark.django_db
class TestMoodCheckTask:
    def test_stores_signal_and_post_count(self, user, negative_mood_client):
        _seed_posts(user, 6)
        result = check_user_mood_task(user.id)
        assert result["status"] == "negative"

        check = MoodCheck.objects.get(user=user)
        assert check.signal == MoodCheck.Signal.NEGATIVE
        assert check.posts_analyzed == 6
        assert check.provider == "mock"
        assert check.negative_streak == 1

    def test_skips_users_without_enough_posts(self, user, negative_mood_client):
        _seed_posts(user, 2)
        assert check_user_mood_task(user.id)["status"] == "skipped_insufficient_posts"
        assert MoodCheck.objects.count() == 0

    def test_missing_user_is_handled(self, negative_mood_client):
        assert check_user_mood_task(999999)["status"] == "missing"

    def test_service_failure_is_logged_not_raised(self, user):
        from ai_companion.errors import AIServiceUnavailable

        _seed_posts(user)
        with mock.patch(
            "ai_companion.tasks.get_client",
            return_value=mock.Mock(mood_check=mock.Mock(side_effect=AIServiceUnavailable())),
        ):
            result = check_user_mood_task(user.id)
        assert result["status"] == "error"
        assert result["error"] == "ai_service_unavailable"
        assert MoodCheck.objects.count() == 0


@pytest.mark.django_db
class TestNudgeGuardrails:
    def test_no_nudge_before_threshold(self, user, negative_mood_client):
        _seed_posts(user)
        check_user_mood_task(user.id)
        check_user_mood_task(user.id)
        assert WellbeingNudge.objects.count() == 0

    @override_settings(MOOD_NEGATIVE_STREAK_THRESHOLD=3)
    def test_nudge_after_three_consecutive_negatives(self, user, negative_mood_client):
        _seed_posts(user)
        for _ in range(3):
            check_user_mood_task(user.id)

        nudge = WellbeingNudge.objects.get(user=user)
        assert nudge.mood_check.signal == "negative"
        assert nudge.dismissed_at is None
        # Non-diagnostic wording guardrail.
        assert "not a diagnosis" in nudge.message
        assert user.notifications.filter(notification_type="nudge").exists()

    @override_settings(MOOD_NEGATIVE_STREAK_THRESHOLD=3)
    def test_streak_resets_on_a_neutral_day(self, user, mock_ai_client):
        """Two bad days followed by a neutral one must reset the counter."""
        _seed_posts(user)
        MoodCheck.objects.create(user=user, signal=MoodCheck.Signal.NEGATIVE, posts_analyzed=5)
        MoodCheck.objects.create(user=user, signal=MoodCheck.Signal.NEGATIVE, posts_analyzed=5)
        MoodCheck.objects.create(user=user, signal=MoodCheck.Signal.NEUTRAL, posts_analyzed=5)

        check_user_mood_task(user.id)  # mock client returns "neutral"

        latest = MoodCheck.objects.filter(user=user).first()
        assert latest.signal == MoodCheck.Signal.NEUTRAL
        assert latest.negative_streak == 0
        assert WellbeingNudge.objects.count() == 0

    @override_settings(MOOD_NEGATIVE_STREAK_THRESHOLD=3, NUDGE_COOLDOWN_DAYS=7)
    def test_cooldown_prevents_repeat_nudges(self, user, negative_mood_client):
        _seed_posts(user)
        for _ in range(3):
            check_user_mood_task(user.id)
        assert WellbeingNudge.objects.count() == 1

        for _ in range(3):
            check_user_mood_task(user.id)
        assert WellbeingNudge.objects.count() == 1  # never nags

    @override_settings(MOOD_NEGATIVE_STREAK_THRESHOLD=3, NUDGE_COOLDOWN_DAYS=7)
    def test_new_nudge_allowed_after_cooldown(self, user, negative_mood_client):
        _seed_posts(user)
        for _ in range(3):
            check_user_mood_task(user.id)
        WellbeingNudge.objects.filter(user=user).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        for _ in range(3):
            check_user_mood_task(user.id)
        assert WellbeingNudge.objects.count() == 2

    def test_maybe_nudge_is_a_noop_below_threshold(self, user):
        check = MoodCheck.objects.create(user=user, signal="negative", negative_streak=1)
        assert maybe_nudge(user, check) is None


@pytest.mark.django_db
class TestNightlySweep:
    def test_only_active_users_with_recent_posts_are_queued(self, user, user_factory, negative_mood_client):
        inactive = user_factory(username="inactive", is_active=False)
        stale = user_factory(username="stale")
        _seed_posts(user, 5)
        Post.objects.create(
            author=stale, content="old", moderation_status=Post.ModerationStatus.APPROVED,
        )
        Post.objects.filter(author=stale).update(created_at=timezone.now() - timedelta(days=60))
        _seed_posts(inactive, 5)

        result = run_mood_check_for_active_users()
        assert result["queued"] == 1
        assert MoodCheck.objects.filter(user=user).exists()
        assert not MoodCheck.objects.filter(user__in=[stale, inactive]).exists()
