"""Social graph operations. Writes also emit notifications (single place, so
API and UI can never drift apart)."""
from __future__ import annotations

from django.db import transaction

from social.models import Comment, Follow, Like


class FollowError(Exception):
    """Raised for invalid follow transitions (self-follow, etc.)."""


def toggle_follow(actor, target) -> tuple[Follow | None, str]:
    """Follow / unfollow / request.

    Returns (edge, status) where status is one of:
    `following`, `not_following`, `requested`, `pending`.
    """
    if actor == target:
        raise FollowError("You cannot follow yourself.")

    edge = Follow.objects.filter(follower=actor, followee=target).first()

    if edge is None:
        needs_approval = target.is_private
        edge = Follow.objects.create(follower=actor, followee=target, is_active=not needs_approval)
        if needs_approval:
            return edge, "requested"
        _notify(actor, target, "follow", message=f"{actor.username} started following you.")
        return edge, "following"

    if edge.is_active:
        edge.delete()
        return None, "not_following"

    # Pending request -> unfollow cancels the request.
    edge.delete()
    return None, "not_following"


def accept_follow_request(target, follower) -> Follow:
    edge = Follow.objects.get_or_create(follower=follower, followee=target)[0]
    edge.is_active = True
    edge.save(update_fields=["is_active", "updated_at"])
    _notify(target, follower, "follow", message=f"{target.username} accepted your follow request.")
    return edge


def reject_follow_request(target, follower) -> None:
    Follow.objects.filter(follower=follower, followee=target, is_active=False).delete()


def toggle_like(actor, post) -> tuple[bool, int]:
    """Idempotent like/unlike. Returns (is_liked, like_count).

    The count is read from the DB rather than `post.likes.count()`: list
    endpoints prefetch `likes`, and a prefetched manager returns the stale
    cached length instead of the post-write value.
    """
    with transaction.atomic():
        like = Like.objects.filter(user=actor, post=post).first()
        if like:
            like.delete()
            return False, Like.objects.filter(post=post).count()
        Like.objects.create(user=actor, post=post)
        if post.author_id != actor.id:
            _notify(
                actor, post.author, "like", post=post,
                message=f"{actor.username} liked your post.",
            )
        return True, Like.objects.filter(post=post).count()


def add_comment(actor, post, content: str, parent: Comment | None = None) -> Comment:
    content = (content or "").strip()
    if not content:
        raise ValueError("Comment cannot be empty.")
    comment = Comment.objects.create(post=post, author=actor, content=content, parent=parent)
    if post.author_id != actor.id:
        _notify(
            actor, post.author, "comment", post=post, comment=comment,
            message=f"{actor.username} commented on your post.",
        )
    return comment


def _notify(actor, recipient, notification_type: str, *, post=None, comment=None, message: str) -> None:
    if recipient == actor:
        return
    from notifications.services import notify

    notify(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        message=message,
        post=post,
        comment=comment,
    )
