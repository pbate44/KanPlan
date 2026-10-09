"""Tests for app/views/auth.py"""

import pytest

from django.contrib.auth.models import User
from django.urls import reverse

from app.models import Board


# Password used for the shared `user` fixture (matches conftest.py).
USER_PASSWORD = "testpassword123"


@pytest.mark.django_db
class TestLogin:

    def test_get_renders_login_form(self, client):
        assert client.get(reverse("login")).status_code == 200

    def test_valid_credentials_redirect_to_dashboard(self, client, user):
        response = client.post(reverse("login"), {
            "username": user.username,
            "password": USER_PASSWORD,
        })
        assert response.status_code == 302
        assert response["Location"] == reverse("dashboard")

    def test_valid_login_sets_session(self, client, user):
        client.post(reverse("login"), {
            "username": user.username,
            "password": USER_PASSWORD,
        })
        assert "_auth_user_id" in client.session

    def test_invalid_credentials_re_renders_form(self, client, user):
        response = client.post(reverse("login"), {
            "username": user.username,
            "password": "wrongpassword",
        })
        assert response.status_code == 200
        assert "_auth_user_id" not in client.session

    def test_login_respects_safe_next_param(self, client, user):
        target = reverse("user_settings")
        response = client.post(f"{reverse('login')}?next={target}", {
            "username": user.username,
            "password": USER_PASSWORD,
            "next": target,
        })
        assert response.status_code == 302
        assert response["Location"] == target

    def test_unsafe_next_falls_back_to_dashboard(self, client, user):
        response = client.post(reverse("login"), {
            "username": user.username,
            "password": USER_PASSWORD,
            "next": "http://evil.example.com/steal",
        })
        assert response.status_code == 302
        assert "evil.example.com" not in response["Location"]


SIGNUP_DATA = {
    "username": "brandnewuser",
    "password1": "Str0ng!Pass99",
    "password2": "Str0ng!Pass99",
}


@pytest.mark.django_db
class TestSignup:

    def test_get_renders_signup_form(self, client):
        assert client.get(reverse("signup")).status_code == 200

    def test_valid_signup_creates_user(self, client):
        client.post(reverse("signup"), SIGNUP_DATA)
        assert User.objects.filter(username="brandnewuser").exists()

    def test_valid_signup_creates_user_profile(self, client):
        client.post(reverse("signup"), SIGNUP_DATA)
        u = User.objects.get(username="brandnewuser")
        assert hasattr(u, "profile")

    def test_valid_signup_creates_starter_board(self, client):
        client.post(reverse("signup"), SIGNUP_DATA)
        u = User.objects.get(username="brandnewuser")
        assert Board.objects.filter(owner=u).count() == 1

    def test_valid_signup_starter_board_has_three_columns(self, client):
        client.post(reverse("signup"), SIGNUP_DATA)
        u = User.objects.get(username="brandnewuser")
        assert Board.objects.get(owner=u).columns.count() == 3

    def test_valid_signup_redirects(self, client):
        response = client.post(reverse("signup"), SIGNUP_DATA)
        assert response.status_code == 302

    def test_valid_signup_starter_board_matches_new_boards(self, client):
        client.post(reverse("signup"), SIGNUP_DATA)
        board = Board.objects.get(owner__username="brandnewuser")
        assert list(board.columns.values_list("name", flat=True)) == ["To Do", "In Progress", "Done"]
        assert board.swimlanes.count() == 1

    def test_valid_signup_logs_user_in(self, client):
        response = client.post(reverse("signup"), SIGNUP_DATA, follow=True)
        assert response.wsgi_request.user.username == "brandnewuser"
        assert response.redirect_chain[-1][0] == reverse("dashboard")

    def test_duplicate_username_rejected(self, client, user):
        response = client.post(reverse("signup"), {
            **SIGNUP_DATA,
            "username": user.username,
        })
        assert response.status_code == 200
        assert User.objects.filter(username=user.username).count() == 1

    def test_password_mismatch_rejected(self, client):
        response = client.post(reverse("signup"), {
            **SIGNUP_DATA,
            "password2": "DifferentPass99!",
        })
        assert response.status_code == 200
        assert not User.objects.filter(username="brandnewuser").exists()


@pytest.mark.django_db
class TestLogout:

    def test_post_clears_session(self, auth_client):
        auth_client.post(reverse("logout"))
        assert "_auth_user_id" not in auth_client.session

    def test_post_redirects_to_login(self, auth_client):
        response = auth_client.post(reverse("logout"))
        assert response.status_code == 302
        assert response["Location"] == reverse("login")

    def test_get_not_allowed(self, auth_client):
        assert auth_client.get(reverse("logout")).status_code == 405


@pytest.mark.django_db
class TestHome:

    def test_anonymous_redirects_to_login(self, client):
        response = client.get(reverse("home"))
        assert response.status_code == 302
        assert response["Location"] == reverse("login")

    def test_authenticated_redirects_to_dashboard(self, auth_client):
        response = auth_client.get(reverse("home"))
        assert response.status_code == 302
        assert response["Location"] == reverse("dashboard")


@pytest.mark.django_db
class TestDeleteAccount:

    def test_valid_deletion_removes_user(self, auth_client, user):
        pk = user.pk
        auth_client.post(reverse("delete_account"), {
            "confirm_delete": "yes",
            "password": USER_PASSWORD,
        })
        assert not User.objects.filter(pk=pk).exists()

    def test_valid_deletion_redirects_to_goodbye(self, auth_client, user):
        response = auth_client.post(reverse("delete_account"), {
            "confirm_delete": "yes",
            "password": USER_PASSWORD,
        })
        assert response.status_code == 302
        assert response["Location"] == reverse("goodbye")

    def test_wrong_password_does_not_delete(self, auth_client, user):
        response = auth_client.post(reverse("delete_account"), {
            "confirm_delete": "yes",
            "password": "wrongpassword",
        })
        assert response.status_code == 302
        assert User.objects.filter(pk=user.pk).exists()

    def test_missing_confirm_does_not_delete(self, auth_client, user):
        response = auth_client.post(reverse("delete_account"), {"password": USER_PASSWORD})
        assert response.status_code == 302
        assert User.objects.filter(pk=user.pk).exists()

    def test_unauthenticated_request_redirects(self, client):
        response = client.post(reverse("delete_account"), {
            "confirm_delete": "yes",
            "password": USER_PASSWORD,
        })
        assert response.status_code == 302


@pytest.mark.django_db
class TestPasswordWhitespace:

    def test_password_change_keeps_surrounding_spaces(self, auth_client, user):
        new = "  Spaced!Pass99  "
        resp = auth_client.post(reverse("edit_password"), {
            "current_password": "testpassword123",
            "new_password": new,
            "confirm_password": new,
        })
        assert resp.status_code == 200
        user.refresh_from_db()
        assert user.check_password(new)
        assert not user.check_password(new.strip())


@pytest.mark.django_db
class TestLoggedOutNav:

    def test_login_page_shows_only_signup_button(self, client):
        html = client.get(reverse("login")).content.decode()
        assert "Create Account" in html
        assert "Sign in" not in html

    def test_signup_page_shows_only_login_button(self, client):
        html = client.get(reverse("signup")).content.decode()
        assert "Sign in" in html
        assert "Create Account" not in html
