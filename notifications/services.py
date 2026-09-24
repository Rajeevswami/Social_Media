"""Notification producers.

Every notification in the system goes through `notify()` so a future websocket
fan-out is a one-line addition here instead of a refactor across apps.
"""
from __future__ import annotations

import logging

from notifications.models import Notification

logger = logging.getLogger("notifications")


def notify(
    *,
    recipient,
    actor,
    notification_type: str,
    message: str,
    post=None,
    comment=None,
) -> Notification:
    if recipient is None or recipient == actor:
        return None

    notification = Notification.objects.create(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        message=message[:280],
        post=post,
        comment=comment,
    )
    # Hook point for realtime delivery (Channels / websockets / push).
    logger.debug(
        "notification created",
        extra={"event": "notification.created", "notification_id": notification.id, "type": notification_type},
    )
    return notification


def mark_all_read(user) -> int:
    from django.utils import timezone

    updated = user.notifications.filter(is_read=False).update(is_read=True, read_at=timezone.now())
    return int(updated)


def unread_count(user) -> int:
    if not user or not user.is_authenticated:
        return 0
    return user.notifications.filter(is_read=False).count()
