"""
Tests for the shared response format, limits and board invariants:

- Errors are {"status": "error", "message": ...}
- Another user's objects return 404 (not 500) from every write endpoint
- Limits return 400 with code "limit_reached"
- Every board keeps at least one swimlane; the board page doesn't create one
"""

import importlib
import json

import pytest
from django.apps import apps
from django.urls import reverse

from app.models import Board, Card, Column, Swimlane
from app.views.helpers import MAX_BOARDS_PER_USER, MAX_COLUMNS_PER_BOARD


def _post_json(client, url, data=None):
    return client.post(url, data=json.dumps(data or {}), content_type="application/json")


@pytest.mark.django_db
class TestOtherUsersObjectsReturn404:

    @pytest.fixture
    def other_client(self, client, other_user):
        client.force_login(other_user)
        return client

    @pytest.mark.parametrize("url_name,payload", [
        ("update_board", {"name": "Hijack"}),
        ("delete_board", {}),
        ("remove_board_image", {}),
        ("update_board_title", {"title": "Hijack"}),
    ])
    def test_board_endpoints(self, other_client, board, url_name, payload):
        resp = _post_json(other_client, reverse(url_name, args=[board.pk]), payload)
        assert resp.status_code == 404

    def test_board_details(self, other_client, board):
        assert other_client.get(reverse("get_board_details", args=[board.pk])).status_code == 404

    @pytest.mark.parametrize("url_name,payload", [
        ("delete_card", {}),
        ("update_card_description", {"description": "x"}),
        ("update_card_priority", {"priority": 1}),
        ("update_card_color", {"color": "#ffffff"}),
    ])
    def test_card_endpoints(self, other_client, card, url_name, payload):
        resp = _post_json(other_client, reverse(url_name, args=[card.pk]), payload)
        assert resp.status_code == 404

    def test_update_column_name(self, other_client, column):
        resp = _post_json(other_client, reverse("update_column_name", args=[column.pk]), {"name": "x"})
        assert resp.status_code == 404

    def test_move_card(self, other_client, card, column):
        resp = _post_json(other_client, reverse("update_card_position_manual"), {
            "card_id": card.pk, "position": 0, "column": column.pk,
        })
        assert resp.status_code == 404


@pytest.mark.django_db
class TestErrorFormat:

    def test_plain_validation_error(self, auth_client, board):
        resp = _post_json(auth_client, reverse("add_column"), {"board_id": board.pk, "name": ""})
        assert resp.status_code == 400
        assert resp.json() == {"status": "error", "message": "Board ID and name are required"}

    def test_move_card_rejects_non_integer_position(self, auth_client, card, column):
        resp = _post_json(auth_client, reverse("update_card_position_manual"), {
            "card_id": card.pk, "position": "top", "column": column.pk,
        })
        assert resp.status_code == 400
        assert resp.json()["status"] == "error"

    def test_column_limit(self, auth_client, board):
        for i in range(MAX_COLUMNS_PER_BOARD):
            Column.objects.create(board=board, name=f"C{i}", position=i)
        resp = _post_json(auth_client, reverse("add_column"), {"board_id": board.pk, "name": "One more"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "limit_reached"
        assert "plan" not in resp.json()["message"].lower()

    def test_board_limit(self, auth_client, user):
        for i in range(MAX_BOARDS_PER_USER):
            Board.objects.create(name=f"B{i}", owner=user)
        resp = _post_json(auth_client, reverse("create_board"), {"name": "One more"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "limit_reached"


@pytest.mark.django_db
class TestSwimlaneInvariant:

    def test_board_page_does_not_create_swimlanes(self, auth_client, board, column):
        assert auth_client.get(reverse("board_detail", args=[board.pk])).status_code == 200
        assert not Swimlane.objects.filter(board=board).exists()

    def test_board_page_shows_limits(self, auth_client, board, swimlane):
        html = auth_client.get(reverse("board_detail", args=[board.pk])).content.decode()
        assert 'data-max-columns="7"' in html
        assert 'data-max-cards="200"' in html

    def test_backfill_migration_gives_boards_and_cards_a_swimlane(self, board, column, user):
        orphan = Card.objects.create(title="Orphan", column=column, position=0)
        lane_board = Board.objects.create(name="Has lanes", owner=user)
        lane = Swimlane.objects.create(board=lane_board, name="Lane", position=0)
        lane_col = Column.objects.create(board=lane_board, name="Col", position=0)
        stray = Card.objects.create(title="Stray", column=lane_col, position=0)

        migration = importlib.import_module("app.migrations.0004_backfill_default_swimlanes")
        migration.backfill_default_swimlanes(apps, None)

        default = Swimlane.objects.get(board=board)
        assert default.name == "Default"
        orphan.refresh_from_db()
        stray.refresh_from_db()
        assert orphan.swimlane_id == default.pk
        assert stray.swimlane_id == lane.pk
        assert Swimlane.objects.filter(board=lane_board).count() == 1
