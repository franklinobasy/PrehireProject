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
