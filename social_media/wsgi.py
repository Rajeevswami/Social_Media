"""WSGI entrypoint (gunicorn social_media.wsgi:application)."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "social_media.settings")

application = get_wsgi_application()
