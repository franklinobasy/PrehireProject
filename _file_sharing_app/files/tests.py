from django.test import TestCase
from django.contrib.auth.models import User
from teams.models import Team
from files.models import File, SharedFile, UserFilePermission, TeamFilePermission


class FileAppTests(TestCase):
    def setUp(self):
        # Create test users
        self.user1 = User.objects.create_user(username="user1", password="password123")
        self.user2 = User.objects.create_user(username="user2", password="password123")

        # Create test team
        self.team = Team.objects.create(name="Test Team")
        self.team.members.add(self.user1, self.user2)  # Add users to team

        # Create a file
        self.file = File.objects.create(
            file_name="test_file.txt",
            key="test_key",
            file_size=12345,
            uploaded_by=self.user1,
        )

        # Create SharedFile instance
        self.shared_file = SharedFile.objects.create(file=self.file)

    def test_file_creation(self):
        """Test file creation and correct fields"""
        self.assertEqual(self.file.file_name, "test_file.txt")
        self.assertEqual(self.file.key, "test_key")
        self.assertEqual(self.file.uploaded_by, self.user1)
        self.assertEqual(self.file.file_size, 12345)

    def test_shared_file_creation(self):
        """Test SharedFile is correctly linked to File"""
        self.assertEqual(self.shared_file.file, self.file)

    def test_user_file_permission_creation(self):
        """Test UserFilePermission creation and correct fields"""
        permission = UserFilePermission.objects.create(
            user=self.user1,
            shared_file=self.shared_file,
            permission="view-and-download",
        )

        self.assertEqual(permission.user, self.user1)
        self.assertEqual(permission.shared_file, self.shared_file)
        self.assertEqual(permission.permission, "view-and-download")

    def test_team_file_permission_creation(self):
        """Test TeamFilePermission creation and correct fields"""
        permission = TeamFilePermission.objects.create(
            team=self.team, shared_file=self.shared_file, permission="view"
        )

        self.assertEqual(permission.team, self.team)
        self.assertEqual(permission.shared_file, self.shared_file)
        self.assertEqual(permission.permission, "view")

    def test_user_permission_unique_together(self):
        """Test that UserFilePermission enforces uniqueness of user and shared_file"""
        UserFilePermission.objects.create(
            user=self.user1, shared_file=self.shared_file, permission="view"
        )

        # Try to create a duplicate permission for the same user and shared_file
        with self.assertRaises(Exception):  # Expecting a unique constraint violation
            UserFilePermission.objects.create(
                user=self.user1,
                shared_file=self.shared_file,
                permission="view-and-download",
            )

    def test_team_permission_unique_together(self):
        """Test that TeamFilePermission enforces uniqueness of team and shared_file"""
        TeamFilePermission.objects.create(
            team=self.team, shared_file=self.shared_file, permission="view"
        )

        # Try to create a duplicate permission for the same team and shared_file
        with self.assertRaises(Exception):  # Expecting a unique constraint violation
            TeamFilePermission.objects.create(
                team=self.team,
                shared_file=self.shared_file,
                permission="view-and-download",
            )
