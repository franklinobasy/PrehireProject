import boto3
import logging

from botocore.exceptions import ClientError
from django.conf import settings

from .models import UserFilePermission, TeamFilePermission


logger = logging.getLogger(__name__)


def upload_to_s3(file, key):
    """Uploads a file to S3."""
    s3_client = boto3.client("s3")
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    try:
        s3_client.upload_fileobj(file, bucket_name, key)
        return True
    except ClientError as e:
        logger.error(f"S3 upload failed: {e}")
        return False


def generate_presigned_url(key, expires_in=3600):
    """Generates a presigned URL for accessing an S3 object."""
    s3_client = boto3.client("s3")
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    try:
        return s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": key},
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        return None


def check_file_permissions(user, file):
    """Checks if a user has access to a file."""
    shared_file = file.shared_info
    return (
        file.uploaded_by == user
        or UserFilePermission.objects.filter(
            user=user, shared_file=shared_file
        ).exists()
        or TeamFilePermission.objects.filter(
            shared_file=shared_file, team__in=user.teams.all()
        ).exists()
    )
