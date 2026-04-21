from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

from django_api.views import docs, docs_oauth2_redirect, health_check, openapi_schema, redoc, root_index


def api_route_pattern() -> str:
    prefix = settings.API_V1_PREFIX.strip("/")
    return f"{prefix}/" if prefix else ""


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", root_index, name="root"),
    path("health", health_check, name="health"),
    path("openapi.json", openapi_schema, name="schema"),
    path("docs", docs, name="swagger-ui"),
    path("docs/oauth2-redirect", docs_oauth2_redirect, name="swagger-ui-oauth2-redirect"),
    path("redoc", redoc, name="redoc"),
    path(api_route_pattern(), include("django_api.urls")),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
