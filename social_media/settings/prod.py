"""Production settings — hardened defaults, Postgres, real Celery broker."""
from social_media.settings.base import *  # noqa: F401,F403
from social_media.settings.base import config, csv_list

DEBUG = False

# A missing SECRET_KEY must fail the boot, not fall back to a dev default.
SECRET_KEY = config("DJANGO_SECRET_KEY")

# Behind Render's proxy TLS terminates at the edge; trust the forwarded header
# so is_secure()/redirects are correct.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=15768000, cast=int)  # 6 months
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Never render the Django debug page in prod.
LOG_LEVEL = config("LOG_LEVEL", default="INFO")

# Celery must talk to a real broker here.
CELERY_TASK_ALWAYS_EAGER = False

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:8000",
    cast=csv_list,
)
