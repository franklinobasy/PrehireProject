from django.contrib import admin
from django.urls import include, path, re_path

from .swagger_config import schema_view


urlpatterns = [
    re_path(
        r"^swagger(?P<format>\.json|\.yaml)$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("authapp.urls")),
    path("api/files/", include("files.urls")),
    path("api/teams/", include("teams.urls")),
]
