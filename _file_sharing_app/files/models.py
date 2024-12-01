from django.db import models
from django.contrib.auth.models import User
from teams.models import Team
import uuid

PERMISSION_CHOICES = [
    ("view", "View"),
    ("view-and-download", "View and Download"),
]


class File(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    file_name = models.CharField(max_length=255)
    key = models.CharField(max_length=255)  # S3 bucket key
    file_size = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="uploaded_files"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name


class SharedFile(models.Model):
    file = models.OneToOneField(
        File, on_delete=models.CASCADE, related_name="shared_info"
    )

    def __str__(self):
        return f"{self.file.file_name} - Permissions"


class UserFilePermission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    shared_file = models.ForeignKey(SharedFile, on_delete=models.CASCADE)
    permission = models.CharField(max_length=20, choices=PERMISSION_CHOICES)

    class Meta:
        unique_together = ("user", "shared_file")

    def __str__(self):
        return f"{self.user.username} - {self.permission}"


class TeamFilePermission(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    shared_file = models.ForeignKey(SharedFile, on_delete=models.CASCADE)
    permission = models.CharField(max_length=20, choices=PERMISSION_CHOICES)

    class Meta:
        unique_together = ("team", "shared_file")

    def __str__(self):
        return f"{self.team.name} - {self.permission}"
