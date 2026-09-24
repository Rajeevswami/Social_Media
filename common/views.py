from __future__ import annotations

import time

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

_BOOT_TIME = time.monotonic()


def health_check(request):
    """Platform load-balancer probe: cheap, no auth, reports DB reachability."""
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # pragma: no cover - only on a real DB outage
        db_ok = False

    payload = {
        "status": "ok" if db_ok else "degraded",
        "service": "social-media-django",
        "database": "ok" if db_ok else "unavailable",
        "uptime_seconds": round(time.monotonic() - _BOOT_TIME, 1),
        "env": settings.DJANGO_ENV,
    }
    return JsonResponse(payload, status=200 if db_ok else 503)


def page_not_found(request, exception=None):
    return render(request, "errors/404.html", status=404)


def server_error(request):
    return render(request, "errors/500.html", status=500)
