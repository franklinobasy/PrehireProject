from django.db import models
from django.contrib.auth.models import User

from teams.models import Team

class File(models.Model):
    PERMISSION_CHOICES = [
        ('view', 'View Only'),
        ('view_download', 'View and Download'),
    ]

    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_files')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_path = models.FileField(upload_to='uploads/')
    owner_team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL, related_name='team_files')
    permissions = models.CharField(max_length=20, choices=PERMISSION_CHOICES, default='view')

    def __str__(self):
        return self.file_name


class SharedFile(models.Model):
    PERMISSION_CHOICES = [
        ('view', 'View Only'),
        ('view_download', 'View and Download'),
    ]

    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='shared_files')
    shared_with_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='shared_files')
    shared_with_team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.CASCADE, related_name='shared_files')
    permissions = models.CharField(max_length=20, choices=PERMISSION_CHOICES, default='view')

    def __str__(self):
        return f"{self.file.file_name} shared"
