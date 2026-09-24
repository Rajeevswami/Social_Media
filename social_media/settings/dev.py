"""Local development settings — SQLite, DEBUG on, eager Celery by default."""
from social_media.settings.base import *  # noqa: F401,F403
from social_media.settings.base import BASE_DIR, config

DEBUG = config("DJANGO_DEBUG", default=True, cast=bool)

# Django refuses DEBUG=True with a wildcard host; the dev preview proxy needs it.
ALLOWED_HOSTS = ["*"] if DEBUG else ALLOWED_HOSTS  # noqa: F405

# Serve user uploads through the dev server.
MEDIA_ROOT = BASE_DIR / "media"  # noqa: F811

# Without a broker Celery runs tasks inline so the moderation flow is testable
# out of the box. Set CELERY_TASK_ALWAYS_EAGER=False + run Redis for the real
# async path.
CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=True, cast=bool)

# Manifest static storage hashes assets at collectstatic time; annoying locally.
STORAGES = {  # noqa: F811
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
