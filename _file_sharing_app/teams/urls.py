# _file_sharing_app/teams/urls.py

from django.urls import path

from .views import TeamViewSet


urlpatterns = [
    path("", TeamViewSet.as_view({"get": "list", "post": "create"}), name="team-list"),
    path(
        "<int:pk>/",
        TeamViewSet.as_view({"get": "retrieve", "put": "update", "delete": "destroy"}),
        name="team-detail",
    ),
    path(
        "<int:pk>/add_member/",
        TeamViewSet.as_view({"post": "add_member"}),
        name="add-member",
    ),
    path(
        "<int:pk>/remove_member/",
        TeamViewSet.as_view({"post": "remove_member"}),
        name="remove-member",
    ),
    path(
        "<int:pk>/update_team/",
        TeamViewSet.as_view({"post": "update_team"}),
        name="update-team",
    ),
    path(
        "<int:pk>/delete_team/",
        TeamViewSet.as_view({"delete": "delete_team"}),
        name="delete-team",
    ),
]
