import logging
import uuid
import boto3
from django.forms import ValidationError
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db import IntegrityError, transaction
from drf_yasg.utils import swagger_auto_schema
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, status
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from drf_yasg import openapi
from django.conf import settings
from botocore.exceptions import ClientError

from teams.models import Team
from .models import (
    PERMISSION_CHOICES,
    File,
    SharedFile,
    TeamFilePermission,
    UserFilePermission,
)
from .serializers import FileSerializer, SharedFileSerializer


User = get_user_model()


class FileUploadView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    logger = logging.getLogger(__name__)

    @swagger_auto_schema(
        operation_description="Upload a file to S3 and save metadata to the database.",
        request_body=FileSerializer,
        responses={201: FileSerializer, 400: "Invalid input", 502: "S3 upload failed"},
    )
    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        # Upload to S3
        s3_client = boto3.client("s3")
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        key = f"uploads/{request.user.id}/{uuid.uuid4()}-{file.name}"

        try:
            s3_client.upload_fileobj(file, bucket_name, key)
        except ClientError as e:
            self.logger.error(f"Failed to upload file to S3: {e}")
            return Response(
                {"detail": "Failed to upload file."}, status=status.HTTP_502_BAD_GATEWAY
            )

        # Save metadata to the database
        file_instance = File.objects.create(
            file_name=file.name, file_size=file.size, uploaded_by=request.user, key=key
        )

        # Create default permissions
        SharedFile.objects.create(file=file_instance)

        # Return serialized metadata
        return Response(
            FileSerializer(file_instance).data, status=status.HTTP_201_CREATED
        )


class FileRetrieveView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Retrieve metadata for a specific file or all files the user has access to.",
        responses={
            200: "File metadata or list of accessible files with download URLs (if allowed)",
            404: "File not found",
            403: "Access denied",
        },
        manual_parameters=[
            openapi.Parameter(
                "uuid",
                openapi.IN_QUERY,
                description="UUID of the file to retrieve. Leave empty to retrieve all accessible files.",
                type=openapi.TYPE_STRING,
                required=False,
            )
        ],
    )
    def get(self, request):
        uuid = request.query_params.get("uuid", None)

        # If a specific file UUID is provided, retrieve it
        if uuid:
            try:
                file = File.objects.get(uuid=uuid)
            except File.DoesNotExist:
                return Response(
                    {"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND
                )

            # Check permissions for the specific file
            shared_file = file.shared_info
            user_has_access = (
                file.uploaded_by == request.user
                or UserFilePermission.objects.filter(
                    user=request.user, shared_file=shared_file
                ).exists()
                or TeamFilePermission.objects.filter(
                    shared_file=shared_file, team__in=request.user.teams.all()
                ).exists()
            )

            if not user_has_access:
                return Response(
                    {"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN
                )

            # Determine user-specific permissions
            user_permission = "view"  # Default permission
            user_permission_obj = UserFilePermission.objects.filter(
                user=request.user, shared_file=shared_file
            ).first()
            if user_permission_obj:
                user_permission = user_permission_obj.permission

            # Generate download URL if permitted
            download_url = None
            if (
                user_permission in ["view-and-download", "edit"]
                or file.uploaded_by == request.user
            ):
                s3_client = boto3.client("s3")
                bucket_name = settings.AWS_STORAGE_BUCKET_NAME
                try:
                    download_url = s3_client.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": bucket_name, "Key": file.key},
                        ExpiresIn=3600,
                    )
                except ClientError as e:
                    return Response(
                        {"detail": f"Failed to generate download URL: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

            # Prepare response for a single file
            response_data = {
                "file_uuid": file.uuid,
                "owner": file.uploaded_by.username,
                "file_name": file.file_name,
                "file_size": file.file_size,
                "uploaded_at": file.uploaded_at,
                "permissions": user_permission,
                "download_url": download_url,
            }
            return Response(response_data, status=status.HTTP_200_OK)

        # If no UUID is provided, retrieve all files the user has access to
        user_files = File.objects.filter(uploaded_by=request.user)
        shared_files = SharedFile.objects.filter(
            Q(userfilepermission__user=request.user)
            | Q(teamfilepermission__team__in=request.user.teams.all())
        ).distinct()

        # Combine user files and shared files, ensuring distinct results
        accessible_files = (
            user_files.distinct()
            | File.objects.filter(shared_info__in=shared_files).distinct()
        )

        # Build metadata for each accessible file
        file_data = []
        for file in accessible_files:
            shared_file = file.shared_info
            user_permission = "view"
            if shared_file:
                user_permission_obj = UserFilePermission.objects.filter(
                    user=request.user, shared_file=shared_file
                ).first()
                user_permission = (
                    user_permission_obj.permission if user_permission_obj else "view"
                )

            # Generate download URL if permitted
            download_url = None
            if (
                user_permission in ["view-and-download", "edit"]
                or file.uploaded_by == request.user
            ):
                s3_client = boto3.client("s3")
                bucket_name = settings.AWS_STORAGE_BUCKET_NAME
                try:
                    download_url = s3_client.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": bucket_name, "Key": file.key},
                        ExpiresIn=3600,
                    )
                except ClientError:
                    download_url = None  # Fallback in case of S3 error

            # Append file metadata
            file_data.append(
                {
                    "file_uuid": file.uuid,
                    "owner": file.uploaded_by.username,
                    "file_name": file.file_name,
                    "file_size": file.file_size,
                    "uploaded_at": file.uploaded_at,
                    "permissions": user_permission,
                    "download_url": download_url,
                }
            )

        return Response(file_data, status=status.HTTP_200_OK)


class FileUpdateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_description="Update an existing file in S3 and metadata in the database.",
        request_body=FileSerializer,
        responses={
            200: FileSerializer,
            400: "No file provided",
            403: "Permission denied",
            500: "Internal server error",
        },
    )
    def put(self, request, uuid):
        try:
            file = File.objects.get(uuid=uuid)
        except File.DoesNotExist:
            return Response(
                {"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if file.uploaded_by != request.user:
            return Response(
                {"detail": "You do not have permission to update this file."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Replace the file in S3
        new_file = request.FILES.get("file")
        if not new_file:
            return Response(
                {"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST
            )

        s3_client = boto3.client("s3")
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        try:
            s3_client.upload_fileobj(new_file, bucket_name, file.key)
        except ClientError as e:
            return Response(
                {"detail": f"Failed to update file: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Update metadata
        file.file_name = new_file.name
        file.file_size = new_file.size
        file.save()

        return Response(FileSerializer(file).data)


class FileDeleteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Delete a file from S3 and the database.",
        responses={
            204: "File deleted",
            404: "File not found",
            403: "Permission denied",
            500: "Internal server error",
        },
    )
    def delete(self, request, uuid):
        try:
            # Fetch the file object
            file = File.objects.get(uuid=uuid)
        except File.DoesNotExist:
            return Response(
                {"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Check permissions
        if file.uploaded_by != request.user:
            return Response(
                {"detail": "You do not have permission to delete this file."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Delete the file from S3
        s3_client = boto3.client("s3")
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        try:
            s3_client.delete_object(Bucket=bucket_name, Key=file.key)
        except ClientError as e:
            return Response(
                {"detail": f"Failed to delete file: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Delete the file metadata from the database
        file.delete()
        return Response(
            {"detail": "File deleted successfully."}, status=status.HTTP_204_NO_CONTENT
        )


class AvailablePermissionsView(APIView):
    """
    View to retrieve a list of available permissions for files.
    """

    @swagger_auto_schema(
        operation_description="Get a list of available permissions for files.",
        responses={
            200: "List of available permissions",
        },
    )
    def get(self, request):
        """
        Return a list of predefined permissions for files.
        """
        permissions = [
            {"code": code, "description": description}
            for code, description in PERMISSION_CHOICES
        ]
        return Response(permissions, status=status.HTTP_200_OK)


class FilePermissionView(APIView):
    """
    View to manage and retrieve file permissions.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_file_and_check_ownership(self, uuid, user):
        """
        Helper method to fetch a file and ensure the user is the owner.
        """
        file = get_object_or_404(File, uuid=uuid)
        if file.uploaded_by != user:
            raise PermissionDenied(
                "You do not have permission to view or manage this file's permissions."
            )
        return file

    @swagger_auto_schema(
        operation_description="Retrieve permissions for a specific file.",
        responses={
            200: SharedFileSerializer,
            403: "Permission denied",
            404: "File not found",
        },
    )
    def get(self, request, uuid):
        """
        Retrieve permissions for a specific file.
        """
        file = self.get_file_and_check_ownership(uuid, request.user)

        # Retrieve the shared file object
        shared_file = get_object_or_404(SharedFile, file=file)

        # Build the permissions response
        user_permissions = (
            UserFilePermission.objects.filter(shared_file=shared_file)
            .exclude(user=file.uploaded_by)
            .values("user__id", "user__username", "permission")
        )

        team_permissions = TeamFilePermission.objects.filter(
            shared_file=shared_file
        ).values("team__id", "team__name", "permission")

        response_data = {
            "file": file.uuid,
            "shared_with_user": [
                {
                    "id": perm["user__id"],
                    "username": perm["user__username"],
                }
                for perm in user_permissions
            ],
            "user_permissions": [
                {
                    "user_id": perm["user__id"],
                    "permission": perm["permission"],
                }
                for perm in user_permissions
            ],
            "shared_with_team": [
                {
                    "id": perm["team__id"],
                    "name": perm["team__name"],
                }
                for perm in team_permissions
            ],
            "team_permissions": [
                {
                    "team_id": perm["team__id"],
                    "permission": perm["permission"],
                }
                for perm in team_permissions
            ],
        }

        return Response(response_data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Update permissions for a file (users and teams).",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "user_permissions": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "user_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                            "permission": openapi.Schema(type=openapi.TYPE_STRING),
                        },
                    ),
                ),
                "team_permissions": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "team_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                            "permission": openapi.Schema(type=openapi.TYPE_STRING),
                        },
                    ),
                ),
            },
        ),
        responses={
            200: "Permissions updated successfully",
            403: "Permission denied",
            404: "File not found",
        },
    )
    def post(self, request, uuid):
        """
        Update permissions for a specific file (users and teams).
        """
        file = self.get_file_and_check_ownership(uuid, request.user)

        # Fetch or create the shared file object
        shared_file, created = SharedFile.objects.get_or_create(file=file)

        # Update user permissions
        user_permissions = request.data.get("user_permissions", [])
        for user_permission in user_permissions:
            user = get_object_or_404(User, id=user_permission.get("user_id"))
            permission = user_permission.get("permission")
            UserFilePermission.objects.update_or_create(
                user=user,
                shared_file=shared_file,
                defaults={"permission": permission},
            )

        # Update team permissions
        team_permissions = request.data.get("team_permissions", [])
        for team_permission in team_permissions:
            team = get_object_or_404(Team, id=team_permission.get("team_id"))
            permission = team_permission.get("permission")
            TeamFilePermission.objects.update_or_create(
                team=team,
                shared_file=shared_file,
                defaults={"permission": permission},
            )

        return Response(
            {"detail": "Permissions updated successfully."},
            status=status.HTTP_200_OK,
        )


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class FilesSharedWithTeamView(generics.ListAPIView):
    """
    View to list files shared with a given team.
    """

    serializer_class = SharedFileSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    @swagger_auto_schema(
        operation_description="Retrieve a list of files shared with a specific team.",
        responses={
            200: "List of files shared with the team",
            403: "Permission denied",
            404: "Team not found",
        },
    )
    def get(self, request, team_id):
        """
        Retrieve files shared with the specified team.
        """
        try:
            team = Team.objects.get(id=team_id)  # Get the team by ID
        except Team.DoesNotExist:
            return Response(
                {"detail": "Team not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # Check if the user has permission to view files for this team
        if request.user not in team.members.all():
            return Response(
                {"detail": "You do not have permission to view files for this team."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Fetch the shared files for the team
        shared_files = SharedFile.objects.filter(teamfilepermission__team=team)

        # Serialize the data and return the response
        serializer = self.serializer_class(shared_files, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FilesSharedWithUserView(generics.ListAPIView):
    """
    View to list all files shared with the authenticated user,
    including download URLs if the user has permission.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = FileSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """
        Fetches files that are shared with the authenticated user.
        """
        user = self.request.user
        return File.objects.filter(
            shared_info__userfilepermission__user=user
        ).distinct()

    def get_download_url(self, file):
        """
        Helper method to generate the pre-signed URL for downloading the file from S3.
        """
        s3_client = boto3.client("s3")
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        try:
            download_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": file.key},
                ExpiresIn=3600,  # URL expires in 1 hour
            )
            return download_url
        except ClientError:
            return None  # Return None if there is an error generating the URL

    def list(self, request, *args, **kwargs):
        """
        Lists all files shared with the authenticated user and includes download URLs if allowed.
        """
        files = self.get_queryset()
        file_data = []

        for file in files:
            shared_file = file.shared_info
            download_url = None
            most_recent_team_permission = None  # Ensure initialization

            # Check if the user is the file owner and can always download
            if file.uploaded_by == request.user:
                download_url = self.get_download_url(file)

            # Check user permissions (direct permissions first)
            user_permission_obj = UserFilePermission.objects.filter(
                user=request.user, shared_file=shared_file
            ).first()

            if user_permission_obj:
                user_permission = user_permission_obj.permission
            else:
                user_permission = None

            # If the user doesn't have direct permission, check their team permissions
            if not user_permission:
                # Get the most recent team permission (by 'updated_at')
                most_recent_team_permission = (
                    TeamFilePermission.objects.filter(
                        shared_file=shared_file, team__in=request.user.teams.all()
                    )
                    .order_by("-updated_at")
                    .first()
                )

                if most_recent_team_permission:
                    user_permission = most_recent_team_permission.permission

            # If the user has 'view-and-download' permission, generate the download URL
            if user_permission == "view-and-download" and not download_url:
                download_url = self.get_download_url(file)

            # If the user doesn't have download permission, set message
            if user_permission == "view" and not download_url:
                download_url = "not allowed to download"

            # Append file metadata including the name of the team if shared with a team
            teams_with_permission = []
            if most_recent_team_permission:
                teams_with_permission = [
                    team.name
                    for team in request.user.teams.all()
                    if most_recent_team_permission.team == team
                    and most_recent_team_permission.permission == "view-and-download"
                ]

            file_data.append(
                {
                    "file_uuid": file.uuid,
                    "owner": file.uploaded_by.username,
                    "file_name": file.file_name,
                    "file_size": file.file_size,
                    "uploaded_at": file.uploaded_at,
                    "permissions": user_permission,
                    "download_url": download_url,
                    "teams_with_permission": teams_with_permission,
                }
            )

        return Response(file_data, status=status.HTTP_200_OK)


class FilesSharedWithUserTeamsView(generics.ListAPIView):
    """
    View to list all files shared with the authenticated user's teams.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = FileSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        # Fetch user's teams
        user_teams = self.request.user.teams.all()
        # Return distinct files shared with those teams
        return (
            File.objects.filter(shared_info__teamfilepermission__team__in=user_teams)
            .distinct()
            .prefetch_related("shared_info__teamfilepermission_set__team")
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        files_data = []
        user_teams = list(request.user.teams.all())  # Cache user's teams

        for file in queryset:
            permissions = "not allowed to download"
            download_url = None

            # Owner permissions
            if file.uploaded_by == request.user:
                permissions = "view-and-download"

            # Check permissions for user's teams
            shared_info = file.shared_info
            team_permissions = TeamFilePermission.objects.filter(
                shared_file=shared_info, team__in=user_teams
            ).select_related("team")

            for permission in team_permissions:
                if permission.permission in ["view-and-download", "view"]:
                    permissions = permission.permission
                    if permissions == "view-and-download":
                        # Generate S3 presigned URL
                        try:
                            s3_client = boto3.client("s3")
                            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
                            download_url = s3_client.generate_presigned_url(
                                "get_object",
                                Params={"Bucket": bucket_name, "Key": file.key},
                                ExpiresIn=3600,
                            )
                        except ClientError as e:
                            logging.error(f"S3 ClientError: {e}")
                            download_url = None
                    break  # Use the most permissive access found

            # Prepare the response data
            team_names = [
                team_permission.team.name
                for team_permission in shared_info.teamfilepermission_set.all()
            ]

            file_data = {
                "file_uuid": file.uuid,
                "file_name": file.file_name,
                "owner": file.uploaded_by.username,
                "permissions": permissions,
                "download_url": download_url or "not allowed to download",
                "team_names": team_names,
            }

            files_data.append(file_data)

        return Response(files_data, status=status.HTTP_200_OK)


class ShareFileView(APIView):
    """
    API view to share a file with users or teams, setting permissions on the fly.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_file_and_check_ownership(self, uuid, user):
        """
        Helper method to fetch a file and ensure the user is the owner.
        """
        file = get_object_or_404(File, uuid=uuid)
        if file.uploaded_by != user:
            raise PermissionDenied("You do not have permission to share this file.")
        return file

    def validate_permissions(self, permissions, valid_choices):
        """
        Helper method to validate that all permissions in the list are valid.
        """
        invalid_permissions = [p for p in permissions if p not in valid_choices]
        if invalid_permissions:
            raise ValidationError(
                {
                    "detail": f"Invalid permissions: {', '.join(invalid_permissions)}. Valid options are: {', '.join(valid_choices)}"  # noqa: E501
                }
            )

    @swagger_auto_schema(
        operation_description="Share a file with specific users or teams, and set permissions dynamically.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "user_permissions": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    description="List of users and their permissions.",
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "user_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                            "permission": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                enum=["view", "view-and-download"],
                            ),
                        },
                    ),
                ),
                "team_permissions": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    description="List of teams and their permissions.",
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            "team_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                            "permission": openapi.Schema(
                                type=openapi.TYPE_STRING,
                                enum=["view", "view-and-download"],
                            ),
                        },
                    ),
                ),
            },
            required=[],
        ),
        responses={
            200: "File shared successfully",
            403: "Permission denied",
            404: "File not found",
            400: "Invalid permission",
        },
    )
    def post(self, request, uuid):
        """
        Share a file with specific users or teams, and set permissions dynamically.
        """
        # Fetch the file and check ownership
        file = self.get_file_and_check_ownership(uuid, request.user)

        # Prevent the owner from sharing the file with themselves
        user_permissions = request.data.get("user_permissions", [])
        team_permissions = request.data.get("team_permissions", [])

        # Check if any of the permissions are being assigned to the file owner
        owner_id = file.uploaded_by.id
        if any(up.get("user_id") == owner_id for up in user_permissions):
            raise ValidationError(
                {"detail": "The owner cannot share the file with themselves."}
            )

        # Define valid permission choices
        valid_permissions = [choice[0] for choice in PERMISSION_CHOICES]

        # Extract and validate permissions
        all_permissions = [up.get("permission") for up in user_permissions] + [
            tp.get("permission") for tp in team_permissions
        ]
        self.validate_permissions(all_permissions, valid_permissions)

        # Remove duplicates from user and team permissions
        user_permissions = {
            up["user_id"]: up["permission"] for up in user_permissions
        }.items()
        team_permissions = {
            tp["team_id"]: tp["permission"] for tp in team_permissions
        }.items()

        # Fetch or create the shared file object
        shared_file, created = SharedFile.objects.get_or_create(file=file)

        # Update permissions in a transaction to ensure atomicity
        try:
            with transaction.atomic():
                # Update user permissions
                for user_id, permission in user_permissions:
                    user = get_object_or_404(User, id=user_id)
                    UserFilePermission.objects.update_or_create(
                        user=user,
                        shared_file=shared_file,
                        defaults={"permission": permission},
                    )

                # Update team permissions
                for team_id, permission in team_permissions:
                    team = get_object_or_404(Team, id=team_id)
                    TeamFilePermission.objects.update_or_create(
                        team=team,
                        shared_file=shared_file,
                        defaults={"permission": permission},
                    )
        except IntegrityError:
            return Response(
                {"detail": "A database error occurred while updating permissions."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"detail": "File shared successfully."},
            status=status.HTTP_200_OK,
        )
