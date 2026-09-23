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


app.conf.beat_schedule = {
    # Nightly wellbeing sweep: never diagnoses, only nudges. See
    # ai_companion.tasks.run_mood_check_for_active_users.
    "mood-check-nightly": {
        "task": "ai_companion.tasks.run_mood_check_for_active_users",
        "schedule": crontab(hour=2, minute=30),
    },
}


@app.task(bind=True, name="social_media.debug_task")
def debug_task(self) -> str:  # pragma: no cover - smoke task
    return f"request: {self.request!r}"
