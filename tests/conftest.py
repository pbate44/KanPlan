"""Shared pytest fixtures for KanPlan tests."""

import pytest
from django.contrib.auth.models import User
from app.models import Board, Column, Card, Swimlane, Subtask, UserProfile


@pytest.fixture
def user(db):
    """A basic authenticated user. UserProfile is created automatically via signal."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpassword123",
    )


@pytest.fixture
def user_profile(user):
    return user.profile


@pytest.fixture
def other_user(db):
    """A second user — useful for testing permission boundaries."""
    return User.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="otherpassword123",
    )


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def board(user):
    return Board.objects.create(name="Test Board", owner=user)


@pytest.fixture
def column(board):
    return Column.objects.create(name="To Do", board=board, position=0)


@pytest.fixture
def card(column):
    return Card.objects.create(
        title="Test Card",
        column=column,
        position=0,
    )


@pytest.fixture
def swimlane(board):
    return Swimlane.objects.create(name="Test Lane", board=board, position=0)


@pytest.fixture
def subtask(card):
    return Subtask.objects.create(title="Test Subtask", card=card)
