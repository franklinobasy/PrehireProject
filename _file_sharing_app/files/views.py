import logging
import uuid
import boto3
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from drf_yasg.utils import swagger_auto_schema
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, status
from rest_framework_simplejwt.authentication import JWTAuthentication
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.conf import settings
from botocore.exceptions import ClientError
from django.views.decorators.csrf import csrf_exempt

from teams.models import Team
from .models import File, SharedFile, TeamFilePermission, UserFilePermission
from .serializers import FileSerializer, SharedFileSerializer
from _file_sharing_app.swagger_config import swagger_auth


User = get_user_model()


class FileUploadView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    logger = logging.getLogger(__name__)

    MAX_FILE_SIZE = 50 * 1024 * 1024

    @swagger_auto_schema(
        operation_description="Upload a file to S3 and save metadata to the database.",
        request_body=FileSerializer,
        responses={201: FileSerializer, 400: 'Invalid input', 502: 'S3 upload failed'}
    )

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file type and size
        allowed_file_types = ["image/jpeg", "application/pdf"]
        max_file_size = 10 * 1024 * 1024  # 10MB

        if file.content_type not in allowed_file_types:
            return Response({"detail": "Unsupported file type."}, status=status.HTTP_400_BAD_REQUEST)
        if file.size > max_file_size:
            return Response({"detail": "File too large. Maximum size is 10MB."}, status=status.HTTP_400_BAD_REQUEST)

        # Upload to S3
        s3_client = boto3.client('s3')
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        key = f"uploads/{request.user.id}/{uuid.uuid4()}-{file.name}"

        try:
            s3_client.upload_fileobj(file, bucket_name, key)
        except ClientError as e:
            self.logger.error(f"Failed to upload file to S3: {e}")
            return Response({"detail": "Failed to upload file."}, status=status.HTTP_502_BAD_GATEWAY)

        # Save metadata to the database
        file_instance = File.objects.create(
            file_name=file.name,
            file_size=file.size,
            uploaded_by=request.user,
            key=key
        )

        # Create default permissions
        shared_file = SharedFile.objects.create(file=file_instance)
        UserFilePermission.objects.create(
            user=request.user, shared_file=shared_file, permission='view-and-download'
        )

        # Return serialized metadata
        return Response(FileSerializer(file_instance).data, status=status.HTTP_201_CREATED)


class FileRetrieveView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Retrieve file metadata and optionally a download URL based on user permissions.",
        responses={200: 'File metadata and download URL if permission granted', 404: 'File not found', 403: 'Access denied'}
    )
    def get(self, request, pk):
        try:
            file = File.objects.get(pk=pk)
        except File.DoesNotExist:
            return Response({"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND)

        # Check permissions
        shared_file = file.shared_info
        user_has_access = (
            file.uploaded_by == request.user or
            request.user in shared_file.shared_with_user.all() or
            any(team in shared_file.shared_with_team.all() for team in request.user.teams.all())
        )

        if not user_has_access:
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        # Determine permissions for the user
        user_permission = 'view'  # Default permission
        if shared_file and request.user in shared_file.shared_with_user.all():
            user_permission = shared_file.permissions  # Retrieve the permissions for the user

        # Determine download URL if the permission allows it
        download_url = None
        if user_permission == 'view-and-download' or file.uploaded_by == request.user:
            s3_client = boto3.client('s3')
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME
            try:
                download_url = s3_client.generate_presigned_url('get_object', Params={'Bucket': bucket_name, 'Key': file.key }, ExpiresIn=3600)
            except ClientError as e:
                return Response({"detail": f"Failed to generate download URL: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Return metadata and (optional) download URL
        response_data = {
            "file_name": file.file_name,
            "file_size": file.file_size,
            "uploaded_at": file.uploaded_at,
            "permissions": user_permission,
            "download_url": download_url
        }
        return Response(response_data)


class FileUpdateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_description="Update an existing file in S3 and metadata in the database.",
        request_body=FileSerializer,
        responses={200: FileSerializer, 400: 'No file provided', 403: 'Permission denied', 500: 'Internal server error'}
    )
    def put(self, request, pk):
        try:
            file = File.objects.get(pk=pk)
        except File.DoesNotExist:
            return Response({"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND)

        if file.uploaded_by != request.user:
            return Response({"detail": "You do not have permission to update this file."}, status=status.HTTP_403_FORBIDDEN)

        # Replace the file in S3
        new_file = request.FILES.get('file')
        if not new_file:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        s3_client = boto3.client('s3')
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        try:
            s3_client.upload_fileobj(new_file, bucket_name, file.key)
        except ClientError as e:
            return Response({"detail": f"Failed to update file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            204: 'File deleted',
            404: 'File not found',
            403: 'Permission denied',
            500: 'Internal server error'
        }
    )
    def delete(self, request, pk):
        try:
            # Fetch the file object
            file = File.objects.get(pk=pk)
        except File.DoesNotExist:
            return Response(
                {"detail": "File not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check permissions
        if file.uploaded_by != request.user:
            return Response(
                {"detail": "You do not have permission to delete this file."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Delete the file from S3
        s3_client = boto3.client('s3')
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        try:
            s3_client.delete_object(Bucket=bucket_name, Key=file.key)
        except ClientError as e:
            return Response(
                {"detail": f"Failed to delete file: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Delete the file metadata from the database
        file.delete()
        return Response(
            {"detail": "File deleted successfully."},
            status=status.HTTP_204_NO_CONTENT
        )


class FilePermissionView(generics.ListCreateAPIView):
    """
    View for setting and updating file permissions.
    """
    queryset = SharedFile.objects.all()
    serializer_class = SharedFileSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Set or update permissions for users or teams for a specific file.",
        request_body=SharedFileSerializer,
        responses={200: 'Permissions updated', 403: 'Permission denied'}
    )
    def post(self, request, file_id):
        """
        Set or update permissions for a file (for users and teams).
        """
        # Fetch the file
        file = get_object_or_404(File, id=file_id)

        # Ensure the request user is the file's owner
        if file.uploaded_by != request.user:
            return Response(
                {"detail": "You do not have permission to manage this file."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Create or get the associated SharedFile
        shared_file, created = SharedFile.objects.get_or_create(file=file)

        # Handle permissions for users
        user_permissions = request.data.get('user_permissions', [])
        for user_id, permission in user_permissions:
            user = get_object_or_404(User, id=user_id)
            # Check if permission exists for the user and update or create new
            user_permission, created = UserFilePermission.objects.update_or_create(
                user=user,
                shared_file=shared_file,
                defaults={'permission': permission}
            )
        
        # Handle permissions for teams
        team_permissions = request.data.get('team_permissions', [])
        for team_id, permission in team_permissions:
            team = get_object_or_404(Team, id=team_id)
            # Check if permission exists for the team and update or create new
            team_permission, created = TeamFilePermission.objects.update_or_create(
                team=team,
                shared_file=shared_file,
                defaults={'permission': permission}
            )