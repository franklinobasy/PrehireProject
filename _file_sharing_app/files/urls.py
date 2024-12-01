from django.urls import path
from .views import (
    FileUploadView,
    FileRetrieveView,
    FileUpdateView,
    FileDeleteView,
    FilePermissionView,
    AvailablePermissionsView,
    FilesSharedWithTeamView,
    FilesSharedWithUserView,
    FilesSharedWithUserTeamsView,
    ShareFileView,
)

urlpatterns = [
    path("upload/", FileUploadView.as_view(), name="file-upload"),
    path("retrieve/", FileRetrieveView.as_view(), name="file-retrieve"),
    path("<uuid:uuid>/update/", FileUpdateView.as_view(), name="file-update"),
    path("<uuid:uuid>/delete/", FileDeleteView.as_view(), name="file-delete"),
    path(
        "<uuid:uuid>/permissions/", FilePermissionView.as_view(), name="file-permission"
    ),
    path(
        "available-permissions/",
        AvailablePermissionsView.as_view(),
        name="available-permissions",
    ),
    path("share/<uuid:uuid>", ShareFileView.as_view(), name="share-file"),
    path(
        "shared-with-team/<int:team_id>/",
        FilesSharedWithTeamView.as_view(),
        name="files-shared-with-team",
    ),
    path(
        "shared-with-user/",
        FilesSharedWithUserView.as_view(),
        name="files-shared-with-user",
    ),
    path(
        "shared-with-user-teams/",
        FilesSharedWithUserTeamsView.as_view(),
        name="files-shared-with-user-teams",
    ),
]
