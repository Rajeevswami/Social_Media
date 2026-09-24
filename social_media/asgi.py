"""ASGI entrypoint.

Plain Django over ASGI today; the routing is split so a Channels
`ProtocolTypeRouter` can be dropped in for websocket notifications without
touching the rest of the app (notifications already exposes a polling
endpoint, so the UI works either way).
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "social_media.settings")

application = get_asgi_application()
