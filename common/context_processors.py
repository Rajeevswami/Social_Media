from django.conf import settings


def site_settings(request):
    """Expose a couple of non-secret settings to every template."""
    return {
        "SITE_NAME": settings.SITE_NAME,
        "DEBUG": settings.DEBUG,
    }
