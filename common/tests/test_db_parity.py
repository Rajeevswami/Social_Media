"""Database parity tests.

These exist because SQLite and PostgreSQL disagree in ways that only show up
under load: JSONField lookups, CHECK constraint enforcement, `distinct()` on a
joined queryset and query counts for prefetched relations. Every test here is
engine-agnostic on purpose — the suite is run twice (SQLite and Postgres) and
must produce identical results.

    pytest                                             # SQLite
    TEST_DATABASE_URL=postgres://... pytest            # Postgres
"""
from __future__ import annotations

import pytest
from django.db import connection, transaction
from django.db.utils import NotSupportedError
from django.test.utils import CaptureQueriesContext

from posts.api_views import with_counts
from posts.models import Post
from social.models import Follow, Like

ENGINE = None  # filled per-test via connection.vendor


@pytest.fixture
def engine():
    return connection.vendor


@pytest.fixture
def populated(db, user_factory):
    """3 authors, a follow graph, likes and comments — enough to exercise joins."""
    alice = user_factory("alice_pg")
    bob = user_factory("bob_pg")
    carol = user_factory("carol_pg", is_private=True)

    Follow.objects.create(follower=alice, followee=bob, is_active=True)
    Follow.objects.create(follower=alice, followee=carol, is_active=True)

    posts = [
        Post.objects.create(author=bob, content="bob post one", moderation_status="approved"),
        Post.objects.create(author=carol, content="carol private", moderation_status="approved"),
        Post.objects.create(author=alice, content="alice own", moderation_status="approved"),
        Post.objects.create(author=bob, content="bob held", moderation_status="held"),
        Post.objects.create(author=carol, content="carol hidden", moderation_status="approved", is_hidden=True),
    ]
    for post in posts[:3]:
        Like.objects.create(user=alice, post=post)
        Like.objects.create(user=bob, post=post)
        post.comments.create(author=bob, content="nice")
    return {"alice": alice, "bob": bob, "carol": carol, "posts": posts}


@pytest.mark.django_db
class TestFeedQuery:
    def test_feed_is_a_constant_number_of_queries(self, populated):
        """The N+1 guard must hold on Postgres too, not just SQLite."""
        alice = populated["alice"]
        with CaptureQueriesContext(connection) as ctx:
            rows = list(with_counts(Post.objects.feed_for(alice)))
            for row in rows:
                _ = row.like_count, row.comment_count, row.author.username
        # 1 (posts) + 1 (likes prefetch) + 1 (comments prefetch); author is joined.
        assert len(ctx.captured_queries) == 3, [q["sql"] for q in ctx.captured_queries]
        assert len(rows) == 3  # bob's approved, carol's private, alice's own

    def test_feed_excludes_held_and_hidden_on_both_engines(self, populated):
        alice = populated["alice"]
        contents = {p.content for p in with_counts(Post.objects.feed_for(alice))}
        assert contents == {"bob post one", "carol private", "alice own"}

    def test_feed_counts_match_the_database(self, populated):
        alice = populated["alice"]
        for post in with_counts(Post.objects.feed_for(alice)):
            assert post.like_count == Like.objects.filter(post=post).count()
            assert post.comment_count == post.comments.count()

    def test_private_visibility_join_has_no_duplicate_rows(self, populated, user_factory):
        """`visible_to` ORs a join onto followers, so a row could appear once
        per matching edge. The (follower, followee) unique constraint bounds
        that to one edge per viewer, and distinct() is the belt-and-braces."""
        carol = populated["carol"]
        alice = populated["alice"]
        # Extra followers widen the join without touching alice's visibility.
        for name in ("dave_pg", "erin_pg"):
            other = user_factory(name)
            Follow.objects.create(follower=other, followee=carol, is_active=True)

        ids = [p.id for p in Post.objects.visible_to(alice)]
        assert len(ids) == len(set(ids)), "visible_to leaked duplicate rows"
        assert carol.posts.filter(content="carol private").first().id in ids
        assert "DISTINCT" in str(Post.objects.visible_to(alice).query).upper()


@pytest.mark.django_db
class TestJSONField:
    def test_flags_round_trip_exactly(self, populated):
        post = populated["posts"][0]
        post.moderation_flags = ["toxicity", "hate"]
        post.moderation_confidence = 0.7331
        post.save(update_fields=["moderation_flags", "moderation_confidence"])

        fresh = Post.objects.get(pk=post.pk)
        assert fresh.moderation_flags == ["toxicity", "hate"]
        assert isinstance(fresh.moderation_flags, list)
        assert fresh.moderation_confidence == 0.7331

    def test_empty_flags_default_is_a_list_not_a_string(self, populated):
        post = Post.objects.create(author=populated["alice"], content="plain", moderation_status="approved")
        assert Post.objects.get(pk=post.pk).moderation_flags == []

    def test_contains_lookup_is_postgres_only(self, populated):
        """Documented engine difference.

        `__contains` on a JSONField is supported by PostgreSQL but raises
        NotSupportedError on SQLite. No production code path uses it (moderation
        flags are only read back and rendered), so this pins the contract: if
        someone adds such a filter, this test tells them it breaks local dev.
        """
        post = populated["posts"][0]
        post.moderation_flags = ["toxicity"]
        post.save(update_fields=["moderation_flags"])

        if connection.vendor == "postgresql":
            assert Post.objects.filter(moderation_flags__contains=["toxicity"]).count() == 1
            assert Post.objects.filter(moderation_flags__contains=["spam"]).count() == 0
        else:
            with pytest.raises(NotSupportedError):
                Post.objects.filter(moderation_flags__contains=["toxicity"]).count()

    def test_moodcheck_raw_json_round_trip(self, populated):
        from ai_companion.models import MoodCheck

        check = MoodCheck.objects.create(
            user=populated["alice"],
            signal="negative",
            posts_analyzed=7,
            raw={"mood_signal": "negative", "nested": {"a": [1, 2, 3]}, "unicode": "कैसे हो"},
        )
        fresh = MoodCheck.objects.get(pk=check.pk)
        assert fresh.raw["nested"]["a"] == [1, 2, 3]
        assert fresh.raw["unicode"] == "कैसे हो"


@pytest.mark.django_db
class TestConstraints:
    def test_post_requires_text_or_image(self, populated):
        """CheckConstraint must be enforced by the database, not just Python."""
        with pytest.raises(Exception) as exc_info, transaction.atomic():
            Post.objects.create(author=populated["alice"], content="", moderation_status="approved")
        assert "post_requires_text_or_image" in str(exc_info.value) or "CHECK" in str(exc_info.value)

    def test_no_self_follow(self, populated):
        alice = populated["alice"]
        with pytest.raises(Exception) as exc_info, transaction.atomic():
            Follow.objects.create(follower=alice, followee=alice)
        assert "no_self_follow" in str(exc_info.value) or "CHECK" in str(exc_info.value)

    def test_unique_like(self, populated):
        alice, post = populated["alice"], populated["posts"][0]
        with pytest.raises(Exception) as exc_info, transaction.atomic():
            Like.objects.create(user=alice, post=post)  # already liked in the fixture
        assert "unique_user_like" in str(exc_info.value) or "UNIQUE" in str(exc_info.value)

    def test_unique_follow_edge(self, populated):
        alice, bob = populated["alice"], populated["bob"]
        with pytest.raises(Exception) as exc_info, transaction.atomic():
            Follow.objects.create(follower=alice, followee=bob)
        assert "unique_follow_edge" in str(exc_info.value) or "UNIQUE" in str(exc_info.value)


@pytest.mark.django_db
class TestOrderingAndText:
    def test_feed_is_newest_first(self, populated):
        alice = populated["alice"]
        created = [p.created_at for p in Post.objects.feed_for(alice)]
        assert created == sorted(created, reverse=True)

    def test_unicode_and_emoji_content_survives(self, populated):
        text = "कैसे हो? 🌧️ monsoon chai — done ✅"
        post = Post.objects.create(author=populated["alice"], content=text, moderation_status="approved")
        assert Post.objects.get(pk=post.pk).content == text

    def test_case_insensitive_hashtag_filter_matches_both_engines(self, populated):
        Post.objects.create(author=populated["bob"], content="hello #Django rocks", moderation_status="approved")
        assert Post.objects.filter(content__icontains="#django").count() == 1
