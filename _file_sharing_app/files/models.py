from django.db import models
from django.contrib.auth.models import User
from teams.models import Team


class File(models.Model):
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="uploaded_files")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    permissions = models.CharField(max_length=20, choices=[('view', 'View'), ('view-and-download', 'View and Download')])
    key = models.CharField(max_length=255, default="")

    shared_with_teams = models.ManyToManyField(Team, related_name="shared_files", blank=True)

    def __str__(self):
        return self.file_name


class SharedFile(models.Model):
    file = models.OneToOneField(File, on_delete=models.CASCADE, related_name="shared_info")
    
    # Permissions for users and teams
    shared_with_user = models.ManyToManyField(User, blank=True, related_name="shared_files")
    user_permissions = models.ManyToManyField(User, through='UserFilePermission', related_name='shared_file_user_permissions', blank=True)
    
    shared_with_team = models.ManyToManyField(Team, blank=True, related_name="team_shared_files")
    team_permissions = models.ManyToManyField(Team, through='TeamFilePermission', related_name='shared_file_team_permissions', blank=True)
    
    def __str__(self):
        return f"{self.file.file_name} - Permissions"

class UserFilePermission(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    shared_file = models.ForeignKey(SharedFile, on_delete=models.CASCADE)
    permission = models.CharField(max_length=20, choices=[('view', 'View'), ('view-and-download', 'View and Download')])

    def __str__(self):
        return f"{self.user.username} - {self.permission}"

class TeamFilePermission(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    shared_file = models.ForeignKey(SharedFile, on_delete=models.CASCADE)
    permission = models.CharField(max_length=20, choices=[('view', 'View'), ('view-and-download', 'View and Download')])

    def __str__(self):
        return f"{self.team.name} - {self.permission}"

