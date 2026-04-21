from django.urls import path, re_path

from django_api.views import api_proxy


urlpatterns = [
    path("", api_proxy),
    re_path(r"^(?P<subpath>.*)$", api_proxy),
]
