from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.authentication import JWTAuthentication


# Define the authorization configuration for Swagger
swagger_auth = openapi.Parameter(
    "Authorization",
    openapi.IN_HEADER,
    description="JWT Authorization header using the Bearer scheme. Example: 'Bearer <your_token>'",
    required=True,
    type=openapi.TYPE_STRING,
)


schema_view = get_schema_view(
    openapi.Info(
        title="FileShare API",
        default_version="v1",
        description="API documentation for FileShare",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="franklin.obasi@bimodalconsulting.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    authentication_classes=[JWTAuthentication],
)
