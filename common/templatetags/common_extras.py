from django import template

register = template.Library()


@register.filter
def liked_by(post, user) -> bool:
    """Has this user liked this post? Uses the prefetched cache when present."""
    if not user or not user.is_authenticated:
        return False
    prefetched = getattr(post, "_prefetched_objects_cache", {}).get("likes")
    if prefetched is not None:
        return any(like.user_id == user.id for like in prefetched)
    return post.likes.filter(user=user).exists()


@register.filter
def is_following(profile, user) -> bool:
    return profile.is_followed_by(user)
