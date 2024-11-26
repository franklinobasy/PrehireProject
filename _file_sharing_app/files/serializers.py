from rest_framework import serializers
from .models import File, SharedFile
from teams.models import Team
from django.contrib.auth.models import User


class FileSerializer(serializers.ModelSerializer):
    """
    Serializer for the File model, including metadata and access details.
    """
    uploaded_by = serializers.ReadOnlyField(source='uploaded_by.username')
    shared_with_teams = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    file = serializers.FileField(write_only=True) 

    class Meta:
        model = File
        fields = [
            'id', 'file', 'uploaded_by', 'uploaded_at', 'shared_with_teams', 'permissions'
        ]

    def get_shared_with_teams(self, obj):
        """
        Return the names of teams the file is shared with.
        """
        return obj.shared_with_teams.values_list('name', flat=True)

    def get_permissions(self, obj):
        """
        Returns a dictionary containing shared permissions for teams and users.
        Includes only users and teams the file is shared with.
        """
        permissions = {}
        shared_info = obj.shared_info  # Access the related SharedFile instance

        if shared_info:
            # Shared permissions for users
            user_permissions = {
                user.username: shared_info.permissions
                for user in shared_info.shared_with_user.all()
            }
            # Shared permissions for teams
            team_permissions = {
                team.name: shared_info.permissions
                for team in shared_info.shared_with_team.all()
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

        file_name = file.name
        file_size = file.size

        instance.file_name = file_name
        instance.file_size = file_size

        instance.save()

        return instance


class SharedFileSerializer(serializers.ModelSerializer):
    shared_with_user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), many=True)
    shared_with_team = serializers.PrimaryKeyRelatedField(queryset=Team.objects.all(), many=True)

    class Meta:
        model = SharedFile
        fields = ['file', 'shared_with_user', 'user_permissions', 'shared_with_team', 'team_permissions']

    def validate(self, data):
        """
        Custom validation for permissions.
        """
        if not data.get('shared_with_user') and not data.get('shared_with_team'):
            raise serializers.ValidationError("You must specify at least one user or team to share with.")
        return data
