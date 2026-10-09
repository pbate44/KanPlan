from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command


@pytest.mark.django_db
class TestSetupFirstUser:

    @patch("app.management.commands.setup_first_user.call_command")
    @patch("builtins.input")
    def test_does_nothing_when_users_exist(self, mock_input, mock_call, user):
        with patch("sys.stdin.isatty", return_value=True):
            call_command("setup_first_user")
        mock_input.assert_not_called()
        mock_call.assert_not_called()

    @patch("app.management.commands.setup_first_user.call_command")
    @patch("builtins.input")
    def test_does_nothing_without_terminal(self, mock_input, mock_call):
        with patch("sys.stdin.isatty", return_value=False):
            call_command("setup_first_user")
        mock_input.assert_not_called()
        mock_call.assert_not_called()

    @patch("app.management.commands.setup_first_user.call_command")
    @patch("builtins.input", return_value="")
    def test_creates_superuser_on_yes(self, _mock_input, mock_call):
        with patch("sys.stdin.isatty", return_value=True):
            call_command("setup_first_user")
        mock_call.assert_called_once_with("createsuperuser")

    @patch("app.management.commands.setup_first_user.call_command")
    @patch("builtins.input", return_value="n")
    def test_skips_on_no(self, _mock_input, mock_call):
        with patch("sys.stdin.isatty", return_value=True):
            call_command("setup_first_user")
        mock_call.assert_not_called()

    @patch("app.management.commands.setup_first_user.call_command", side_effect=KeyboardInterrupt)
    @patch("builtins.input", return_value="y")
    def test_cancelled_createsuperuser_does_not_fail(self, _mock_input, _mock_call):
        with patch("sys.stdin.isatty", return_value=True):
            call_command("setup_first_user")
        assert not User.objects.exists()

    def test_created_superuser_gets_profile(self):
        User.objects.create_superuser("owner", "owner@example.com", "pw-12345-long")
        assert User.objects.get(username="owner").profile is not None

    def test_from_env_creates_account(self, monkeypatch):
        monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "admin")
        monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "pw-12345-long")
        call_command("setup_first_user", "--from-env")
        admin = User.objects.get(username="admin")
        assert admin.is_superuser
        assert admin.check_password("pw-12345-long")

    def test_from_env_without_vars_does_nothing(self, monkeypatch):
        monkeypatch.delenv("DJANGO_SUPERUSER_USERNAME", raising=False)
        monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)
        call_command("setup_first_user", "--from-env")
        assert not User.objects.exists()

    def test_from_env_skips_when_users_exist(self, monkeypatch, user):
        monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "admin")
        monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "pw-12345-long")
        call_command("setup_first_user", "--from-env")
        assert not User.objects.filter(username="admin").exists()
