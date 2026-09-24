"""Settings package.

`DJANGO_ENV` picks the concrete module:

* unset / `dev`  -> social_media.settings.dev   (SQLite, DEBUG, eager Celery)
* `prod`         -> social_media.settings.prod  (Postgres, hardened security)

Everything shared lives in `base.py`; the environment modules only override.
"""
import os

_env = os.environ.get("DJANGO_ENV", "dev").lower()

if _env == "prod":
    from social_media.settings.prod import *  # noqa: F401,F403
else:
    from social_media.settings.dev import *  # noqa: F401,F403
