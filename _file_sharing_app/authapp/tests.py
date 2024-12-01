# _file_sharing_app/authapp/tests.py

from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth.models import User


class AuthAppTests(APITestCase):
    """
    Test cases for the authentication app.
    """

    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            username="testuser", email="testuser@example.com", password="testpassword"
        )
        self.register_url = "/api/auth/register/"
        self.login_url = "/api/auth/login/"
        self.logout_url = "/api/auth/logout/"
        self.profile_url = "/api/auth/profile/"

    def test_register_user(self):
        """
        Test user registration.
        """
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newpassword",
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("message", response.data)
        self.assertEqual(response.data["message"], "User created successfully")

    def test_login_user(self):
        """
        Test user login.
        """
        data = {
            "username": self.user.username,
            "password": "testpassword",
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_login_invalid_credentials(self):
        """
        Test login with invalid credentials.
        """
        data = {
            "username": self.user.username,
            "password": "wrongpassword",
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("detail", response.data)
        self.assertEqual(
            response.data["detail"],
            "No active account found with the given credentials",
        )

    def test_logout_user(self):
        """
        Test user logout using refresh token.
        """
        # Log in the user to get the refresh token
        login_response = self.client.post(
            self.login_url, {"username": self.user.username, "password": "testpassword"}
        )

        refresh_token = login_response.data["refresh"]
        # Send the refresh token to logout
        response = self.client.post(self.logout_url, {"refresh": refresh_token})

        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        self.assertEqual(response.data["message"], "Logged out successfully")
