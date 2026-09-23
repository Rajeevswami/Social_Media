from notifications.services import unread_count


def unread_notifications(request):
    """Render the badge on first paint; app.js keeps it fresh afterwards."""
    if not request.user.is_authenticated:
        return {"unread_notifications": 0}
    return {"unread_notifications": unread_count(request.user)}
