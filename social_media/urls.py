"""Root URL configuration.

Versioned JSON API under /api/v1/, server-rendered UI at /, health probe for
platform load balancers at /healthz.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from common.views import health_check

api_v1 = [
    path("auth/", include("accounts.api_urls")),
    path("", include("posts.api_urls")),
    path("", include("social.api_urls")),
    path("", include("notifications.api_urls")),
    path("", include("ai_companion.api_urls")),
]

urlpatterns = [
    path("healthz", health_check, name="health_check"),
    path("admin/", admin.site.urls),
    # JSON API
    path("api/v1/", include((api_v1, "api"), namespace="api")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # Server-rendered UI (Django templates + Bootstrap 5)
    path("accounts/", include("accounts.urls")),
    path("", include("posts.urls")),
    path("", include("social.urls")),
    path("notifications/", include("notifications.urls")),
    path("ai/", include("ai_companion.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Friendly error pages (404/500) instead of the default Django ones.
handler404 = "common.views.page_not_found"
handler500 = "common.views.server_error"

_ = TemplateView  # imported for future use by UI landing pages
