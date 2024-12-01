# _file_sharing_app/teams/serializers.py
from rest_framework import serializers

from .models import Team


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name", "description", "members", "created_at", "updated_at"]


class AddMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class RemoveMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class UpdateTeamSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, max_length=100)
    description = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
