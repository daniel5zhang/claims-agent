"""Root URL configuration — /api/v1/ prefix for all API endpoints"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    # API v1
    path("api/v1/", include("apps.cases.urls")),
    path("api/v1/", include("apps.rules.urls")),
    path("api/v1/", include("apps.organizations.urls")),
    # Health check
    path("health/", include("apps.cases.urls_health")),
    # API docs (dev only)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema")),
]
