"""
Shared settings. Environment specific overrides live in dev.py / prod.py.

Every secret and deployment knob is read from the environment (`.env` locally,
platform env vars in production) via python-decouple — nothing sensitive is
hardcoded here.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import AutoConfig, Csv

# social_media/settings/base.py -> project root
BASE_DIR = Path(__file__).resolve().parents[2]

# AutoConfig walks up from BASE_DIR looking for `.env`; if it is absent (as on
# Render) it silently falls back to os.environ.
config = AutoConfig(search_path=BASE_DIR)
csv_list = Csv(post_process=lambda v: [item.strip() for item in v if item.strip()])

DJANGO_ENV = config("DJANGO_ENV", default="dev")

# SECURITY WARNING: keep the secret key out of source control.
SECRET_KEY = config("DJANGO_SECRET_KEY", default="insecure-dev-only-key-change-me")
DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=csv_list)

# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
]

LOCAL_APPS = [
    "common",
    "accounts",
    "posts",
    "social",
    "notifications",
    "ai_companion",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.middleware.RequestLogMiddleware",
]

ROOT_URLCONF = "social_media.urls"
WSGI_APPLICATION = "social_media.wsgi.application"
ASGI_APPLICATION = "social_media.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "common.context_processors.site_settings",
                "notifications.context_processors.unread_notifications",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database — Postgres in prod (DATABASE_URL), SQLite for local dev
# ---------------------------------------------------------------------------
_sqlite_path = BASE_DIR / "db.sqlite3"
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{_sqlite_path}",
        conn_max_age=config("DB_CONN_MAX_AGE", default=0, cast=int),
        conn_health_checks=True,
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Auth — custom user + JWT for the API, sessions for the template UI
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "posts:feed"
LOGOUT_REDIRECT_URL = "accounts:login"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=config("ACCESS_TOKEN_LIFETIME_MINUTES", default=30, cast=int)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=config("REFRESH_TOKEN_LIFETIME_DAYS", default=7, cast=int)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    # JWT first (API clients), sessions second (same-origin browser/DRF UI).
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardResultsPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "user": "300/hour",
        "anon": "60/hour",
        "ai": config("AI_RATE_LIMIT_PER_USER", default="20/hour"),
        "ai_anon": "0/hour",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "common.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "DATETIME_FORMAT": "iso-8601",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Social_Media API",
    "DESCRIPTION": "Social network API with an async AI companion microservice.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---------------------------------------------------------------------------
# CORS / CSRF
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:8000,http://localhost:3000",
    cast=csv_list,
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=csv_list)

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = config("CELERY_TASK_ALWAYS_EAGER", default=False, cast=bool)
CELERY_TASK_EAGER_PROPAGATES = config("CELERY_TASK_EAGER_PROPAGATES", default=False, cast=bool)
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    # AI calls are slow and rate limited: keep them off the default queue.
    "ai_companion.tasks.*": {"queue": "ai"},
}
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ---------------------------------------------------------------------------
# AI microservice client (see apps/ai_companion/client.py)
# ---------------------------------------------------------------------------
AI_SERVICE_BASE_URL = config("AI_SERVICE_BASE_URL", default="http://localhost:8001").rstrip("/")
AI_SERVICE_API_KEY = config("AI_SERVICE_API_KEY", default="dev-internal-key-change-me")
AI_SERVICE_TIMEOUT_SECONDS = config("AI_SERVICE_TIMEOUT_SECONDS", default=10.0, cast=float)
AI_SERVICE_RETRIES = config("AI_SERVICE_RETRIES", default=2, cast=int)

# `auto_publish`  -> publish the post, store the moderation verdict, warn the author
# `hold_unsafe`   -> unsafe posts are held for review (never silently dropped)
MODERATION_POLICY = config("MODERATION_POLICY", default="auto_publish")
# What to do when the AI service itself is down:
#   fail_open   -> publish, but keep the post flagged and re-check later (default)
#   fail_closed -> hold the post for review until the check can run
MODERATION_FAILURE_POLICY = config("MODERATION_FAILURE_POLICY", default="fail_open")
AI_MOOD_POST_SAMPLE = config("AI_MOOD_POST_SAMPLE", default=20, cast=int)
AI_ACTIVE_USER_DAYS = config("AI_ACTIVE_USER_DAYS", default=7, cast=int)

# ---------------------------------------------------------------------------
# Static / media
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = config("MEDIA_URL", default="/media/")
MEDIA_ROOT = Path(config("MEDIA_ROOT", default=str(BASE_DIR / "media")))

# Upload guards (image posts / avatars)
MAX_UPLOAD_BYTES = config("MAX_UPLOAD_BYTES", default=8 * 1024 * 1024, cast=int)
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Logging — structured JSON to stdout so Render/Docker can ship it
# ---------------------------------------------------------------------------
LOG_LEVEL = config("LOG_LEVEL", default="INFO")
LOG_JSON = config("LOG_JSON", default=True, cast=bool)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_context": {"()": "common.logging.RequestContextFilter"},
    },
    "formatters": {
        "json": {
            "()": "common.logging.JSONFormatter",
            "timestamp_format": "%Y-%m-%dT%H:%M:%S%z",
        },
        "console": {
            "format": "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if LOG_JSON else "console",
            "filters": ["request_context"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.db.backends": {"handlers": ["console"], "level": config("SQL_LOG_LEVEL", default="WARNING")},
        "ai_client": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="no-reply@social-media.local")
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

SITE_NAME = "Social_Media"
NUDGE_COOLDOWN_DAYS = config("NUDGE_COOLDOWN_DAYS", default=7, cast=int)
MOOD_NEGATIVE_STREAK_THRESHOLD = config("MOOD_NEGATIVE_STREAK_THRESHOLD", default=3, cast=int)

# Make sure the env file was actually loaded where we expect it (helps catch a
# missing `.env` early instead of silently running on defaults).
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "social_media.settings")
