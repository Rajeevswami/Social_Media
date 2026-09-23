"""Test settings: in-memory DB, eager Celery, fast password hashing."""
from social_media.settings.base import *  # noqa: F401,F403
from social_media.settings.base import BASE_DIR

DEBUG = False
ALLOWED_HOSTS = ["*"]

# WhiteNoise serves collected static files; irrelevant in tests (and it warns
# about the missing ./staticfiles output directory).
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m]  # noqa: F405

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Run Celery tasks inline so tests exercise the real task code without a broker.
# Propagates stays False: with it True, Celery re-raises `Retry` to the caller
# instead of re-running the task eagerly, which would hide the retry-then-
# fallback behaviour these tests assert. Assertions check the resulting DB
# state, so a silently failing task still fails the test.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

STORAGES = {  # noqa: F811
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

MEDIA_ROOT = BASE_DIR / ".test-media"

# Deterministic AI client configuration; tests inject an httpx.MockTransport.
AI_SERVICE_BASE_URL = "http://ai.test"
AI_SERVICE_API_KEY = "test-api-key"
AI_SERVICE_TIMEOUT_SECONDS = 1.0
AI_SERVICE_RETRIES = 0

REST_FRAMEWORK = {  # noqa: F811
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        "user": "10000/hour",
        "anon": "10000/hour",
        "ai": "1000/hour",
        "ai_anon": "0/hour",
    },
}

LOGGING = {  # noqa: F811
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"], "level": "CRITICAL"},
}
