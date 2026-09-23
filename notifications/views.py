from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from notifications.services import mark_all_read


@login_required
def notification_list_view(request):
    items = (
        request.user.notifications.select_related("actor", "post")
        .order_by("-created_at")[:100]
    )
    # Opening the inbox marks them seen — same contract as most social apps.
    mark_all_read(request.user)
    return render(
        request, "notifications/list.html", {"notifications": items, "active_tab": "notifications"}
    )


@login_required
@require_http_methods(["POST"])
def mark_all_read_view(request):
    mark_all_read(request.user)
    return redirect("notifications:list")
