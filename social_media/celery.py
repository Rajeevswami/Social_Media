"""Celery application for the Django project.

Run locally:

    celery -A social_media worker -l info
    celery -A social_media beat   -l info   # nightly mood-check schedule
"""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "social_media.settings")

app = Celery("social_media")

# `namespace="CELERY"` means every setting must be prefixed with CELERY_ in
# Django settings (CELERY_BROKER_URL, CELERY_TASK_ALWAYS_EAGER, ...).
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@setup_logging.connect
def configure_celery_logging(**_kwargs: object) -> None:
    """Reuse Django's (structured) logging config inside Celery workers."""
    import logging.config

    from django.conf import settings

    logging.config.dictConfig(settings.LOGGING)


def _mood_schedule() -> crontab:
    """When the nightly wellbeing sweep runs.

    Configurable because "nightly" is relative to the deployment's timezone:
    Celery interprets `crontab` in CELERY_TIMEZONE, so an operator in IST can
    keep 02:30 local while a US-hosted worker shifts it. Defaults to 02:30.
    """
    from django.conf import settings

    return crontab(
        hour=getattr(settings, "MOOD_CHECK_HOUR", 2),
        minute=getattr(settings, "MOOD_CHECK_MINUTE", 30),
    )


app.conf.beat_schedule = {
    # Nightly wellbeing sweep: never diagnoses, only nudges. See
    # ai_companion.tasks.run_mood_check_for_active_users.
    "mood-check-nightly": {
        "task": "ai_companion.tasks.run_mood_check_for_active_users",
        "schedule": _mood_schedule(),
    },
}


@app.task(bind=True, name="social_media.debug_task")
def debug_task(self) -> str:  # pragma: no cover - smoke task
    return f"request: {self.request!r}"
