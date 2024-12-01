import random
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from django.contrib.auth.models import User

from .models import Team


class TeamTests(APITestCase):
    def setUp(self):
        # Register a user with a unique username
        self.user_data = {
            "username": f"testuser{random.randint(1000, 9999)}",  # Unique username
            "password": "testpassword123",
            "email": "testuser@example.com",
        }
        self.user = User.objects.create_user(**self.user_data)

        # Login and get the JWT token
        login_url = reverse("token_obtain_pair")  # Replace with your actual login URL
        response = self.client.post(
            login_url,
            {
                "username": self.user_data["username"],
                "password": self.user_data["password"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.token = response.data["access"]  # Assuming the token is in `access` key

        # Set the Authorization header for future requests
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.token)

        # Create a test team for delete and other tests
        self.team = Team.objects.create(
            name="Test Team", description="A team for testing"
        )
        self.team.members.add(self.user)

    def test_create_team(self):
        url = reverse("team-list")  # Update with correct team URL
        new_user_data = {
            "username": f"testuser{random.randint(1000, 9999)}",  # Unique username
            "password": "testpassword1234",
            "email": "testuser1@example.com",
        }
        new_user = User.objects.create_user(**new_user_data)

        data = {
            "name": f"New Team- {random.randint(1000, 9999)}",
            "description": "A new team for testing.",
            "members": [new_user.id],
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        team_data = response.data
        self.assertIn("id", team_data)

    def test_list_teams(self):
        url = reverse("team-list")  # Update with correct team URL
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_add_member(self):
        # Create a team for testing
        team = Team.objects.create(name=f"Test Team - {random.randint(1000, 9999)}")

        # Ensure user is not already a member before trying to add
        if self.user not in team.members.all():
            team.members.add(self.user)
        self.assertIn(self.user, team.members.all())

    def test_add_member_user_not_found(self):
        # Create a team first
        team = Team.objects.create(name="Team with Member")
        add_member_url = reverse(
            "add-member", args=[team.id]
        )  # Update with correct URL
        non_existent_user_id = 9999
        response = self.client.post(
            add_member_url, {"user_id": non_existent_user_id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_remove_member(self):
        # Create a team first
        team = Team.objects.create(name="Team with Members")
        other_user = User.objects.create_user(
            username="anotheruser", password="password"
        )
        team.members.add(other_user)  # Add the user to the team
        remove_member_url = reverse(
            "remove-member", args=[team.id]
        )  # Update with correct URL
        response = self.client.post(remove_member_url, {"user_id": other_user.id})
        self.assertEqual(
            response.status_code, 200
        )  # Check if member was removed successfully

    def test_remove_member_user_not_in_team(self):
        # Create a team first
        team = Team.objects.create(name="Team with Members")
        other_user = User.objects.create_user(
            username="anotheruser", password="password"
        )
        remove_member_url = reverse(
            "remove-member", args=[team.id]
        )  # Update with correct URL
        response = self.client.post(remove_member_url, {"user_id": other_user.id})
        self.assertEqual(
            response.status_code, 400
        )  # Check if user not found in the team response is returned

    def test_update_team(self):
        # Create a team first
        update_team_url = reverse(
            "update-team", args=[self.team.id]
        )  # Update with correct URL
        response = self.client.post(
            update_team_url,
            {"name": "Updated Team", "description": "Updated description"},
        )
        self.assertEqual(
            response.status_code, 200
        )  # Check if team update was successful

    def test_delete_team(self):
        delete_team_url = reverse(
            "delete-team", args=[self.team.id]
        )  # Use correct URL for delete
        response = self.client.delete(delete_team_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Ensure the team is deleted from the database
        self.assertFalse(Team.objects.filter(id=self.team.id).exists())
