# _file_sharing_app/teams/views.py

from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_yasg.utils import swagger_auto_schema
from .models import Team
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated
from .serializers import AddMemberSerializer, RemoveMemberSerializer, TeamSerializer, UpdateTeamSerializer


class TeamViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing teams, including creating, updating, deleting, and managing members.
    """
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        # Associate the team with the current user as a member upon creation
        team = serializer.save()
        team.members.add(self.request.user)

    @swagger_auto_schema(
        operation_description="Add a user as a member of the team.",
        responses={200: "User added as a member.", 400: "User already a member.", 404: "User not found."},
        request_body=AddMemberSerializer
    )
    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        """
        Add a user as a member of the team.
        """
        team = self.get_object()
        user_id = request.data.get('user_id')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if user in team.members.all():
            return Response({"detail": "User is already a member."}, status=status.HTTP_400_BAD_REQUEST)

        team.members.add(user)
        return Response({"detail": "User added as a member."}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Remove a user from the team.",
        responses={200: "User removed from team.", 400: "User is not a member.", 404: "User not found."},
        request_body=RemoveMemberSerializer
    )
    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        """
        Remove a user from the team.
        """
        team = self.get_object()
        user_id = request.data.get('user_id')

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if user not in team.members.all():
            return Response({"detail": "User is not a member."}, status=status.HTTP_400_BAD_REQUEST)

        team.members.remove(user)
        return Response({"detail": "User removed from team."}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Update the team's name and description.",
        responses={200: "Team updated successfully."},
        request_body=UpdateTeamSerializer
    )
    @action(detail=True, methods=['post'])
    def update_team(self, request, pk=None):
        """
        Update the team's name and description.
        """
        team = self.get_object()
        name = request.data.get('name')
        description = request.data.get('description')

        if name:
            team.name = name
        if description:
            team.description = description
        
        team.save()
        return Response({"detail": "Team updated successfully."}, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Delete the team.",
        responses={204: "Team deleted successfully."}
    )
    @action(detail=True, methods=['delete'])
    def delete_team(self, request, pk=None):
        """
        Delete the team.
        """
        team = self.get_object()
        team.delete()
        return Response({"detail": "Team deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(
        operation_description="Delete the team.",
        responses={204: "Team deleted successfully."}
    )
    @action(detail=True, methods=['delete'])
    def delete_team(self, request, pk=None):
        """
        Delete the team.
        """
        team = self.get_object()
        team.delete()
        return Response({"detail": "Team deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
