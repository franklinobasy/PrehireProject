from rest_framework import serializers
from .models import File, SharedFile
from teams.models import Team
from django.contrib.auth.models import User


from rest_framework import serializers
from .models import File, SharedFile
from teams.models import Team
from django.contrib.auth.models import User

class FileSerializer(serializers.ModelSerializer):
    """
    Serializer for the File model, including metadata and access details.
    """
    uploaded_by = serializers.ReadOnlyField(source='uploaded_by.username')
    shared_with_users = serializers.SerializerMethodField()
    shared_with_teams = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    file = serializers.FileField(write_only=True)

    class Meta:
        model = File
        fields = [
            'uuid', 'file', 'uploaded_by', 'uploaded_at', 'shared_with_users', 'shared_with_teams', 'permissions'
        ]

    def get_shared_with_users(self, obj):
        """
        Returns a list of usernames who have the file shared with them, by querying UserFilePermission.
        """
        # Access the related SharedFile instance and fetch associated users from UserFilePermission
        shared_info = obj.shared_info
        user_permissions = shared_info.userfilepermission_set.all()
        return [user_permission.user.username for user_permission in user_permissions]

    def get_shared_with_teams(self, obj):
        """
        Returns a list of team names who have the file shared with them, by querying TeamFilePermission.
        """
        # Access the related SharedFile instance and fetch associated teams from TeamFilePermission
        shared_info = obj.shared_info
        team_permissions = shared_info.teamfilepermission_set.all()
        return [team_permission.team.name for team_permission in team_permissions]

    def get_permissions(self, obj):
        """
        Returns a dictionary containing shared permissions for users and teams.
        Includes only users and teams the file is shared with.
        """
        permissions = {}
        shared_info = obj.shared_info  # Access the related SharedFile instance

        if shared_info:
            # Fetch user permissions
            user_permissions = {
                user_permission.user.username: user_permission.permission
                for user_permission in shared_info.userfilepermission_set.all()
            }

            # Fetch team permissions
            team_permissions = {
                team_permission.team.name: team_permission.permission
                for team_permission in shared_info.teamfilepermission_set.all()
            }

            permissions['users'] = user_permissions
            permissions['teams'] = team_permissions

        return permissions

    def create(self, validated_data):
        """
        Create a new file and handle file upload logic.
        """
        file = validated_data.pop('file')
        instance = super().create(validated_data)

        # Set file metadata
        file_name = file.name
        file_size = file.size

        instance.file_name = file_name
        instance.file_size = file_size

        instance.save()

        return instance


class SharedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = SharedFile
        fields = ['file']

