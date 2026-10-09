"""Tests for app/views/swimlane.py"""

import json

import pytest
from django.urls import reverse

from app.models import Card, Swimlane


def _post_json(client, url, data):
    return client.post(url, json.dumps(data), content_type="application/json")


@pytest.mark.django_db
class TestSwimlaneCRUD:

    def test_add_swimlane_success(self, auth_client, board):
        resp = _post_json(auth_client, reverse("add_swimlane"), {"board_id": board.pk, "name": "Sprint 1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["swimlane"]["name"] == "Sprint 1"
        assert data["swimlane"]["board_id"] == board.pk
        assert Swimlane.objects.filter(board=board, name="Sprint 1").exists()

    def test_add_swimlane_default_name(self, auth_client, board):
        resp = _post_json(auth_client, reverse("add_swimlane"), {"board_id": board.pk})
        assert resp.status_code == 200
        assert resp.json()["swimlane"]["name"] == "New Swimlane"

    def test_add_swimlane_custom_height_clamped(self, auth_client, board):
        resp = _post_json(auth_client, reverse("add_swimlane"), {"board_id": board.pk, "height": 50})
        assert resp.status_code == 200
        assert resp.json()["swimlane"]["height"] == 100  # clamped to min

        resp2 = _post_json(auth_client, reverse("add_swimlane"), {"board_id": board.pk, "height": 9999})
        assert resp2.status_code == 200
        assert resp2.json()["swimlane"]["height"] == 2000  # clamped to max

    def test_add_swimlane_invalid_height(self, auth_client, board):
        resp = _post_json(auth_client, reverse("add_swimlane"), {"board_id": board.pk, "height": "bad"})
        assert resp.status_code == 400

    def test_add_swimlane_name_too_long(self, auth_client, board):
        resp = _post_json(auth_client, reverse("add_swimlane"), {"board_id": board.pk, "name": "x" * 101})
        assert resp.status_code == 400

    def test_add_swimlane_missing_board_id(self, auth_client):
        resp = _post_json(auth_client, reverse("add_swimlane"), {"name": "Lane"})
        assert resp.status_code == 400

    def test_add_swimlane_assigns_existing_cards_when_first(self, auth_client, board, column):
        card = Card.objects.create(title="Existing Card", column=column, position=0)
        assert card.swimlane is None

        resp = _post_json(auth_client, reverse("add_swimlane"), {"board_id": board.pk, "name": "Lane A"})
        assert resp.status_code == 200
        swimlane_id = resp.json()["swimlane"]["id"]

        card.refresh_from_db()
        assert card.swimlane_id == swimlane_id

    def test_add_second_swimlane_does_not_reassign_cards(self, auth_client, board, column, swimlane):
        card = Card.objects.create(title="Card", column=column, position=0, swimlane=swimlane)

        resp = _post_json(auth_client, reverse("add_swimlane"), {"board_id": board.pk, "name": "Lane B"})
        assert resp.status_code == 200

        card.refresh_from_db()
        assert card.swimlane_id == swimlane.pk  # unchanged

    def test_add_swimlane_enforces_limit(self, auth_client, board):
        for i in range(7):
            Swimlane.objects.create(board=board, name=f"Lane {i}", position=i)

        resp = _post_json(auth_client, reverse("add_swimlane"), {"board_id": board.pk, "name": "Over limit"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "limit_reached"

    def test_add_swimlane_position_increments(self, auth_client, board):
        _post_json(auth_client, reverse("add_swimlane"), {"board_id": board.pk, "name": "First"})
        resp = _post_json(auth_client, reverse("add_swimlane"), {"board_id": board.pk, "name": "Second"})
        assert resp.json()["swimlane"]["position"] == 1

    # ── Update name ──────────────────────────────────────────────────────────────

    def test_update_swimlane_name(self, auth_client, swimlane):
        url = reverse("update_swimlane_name", args=[swimlane.pk])
        resp = _post_json(auth_client, url, {"name": "Renamed Lane"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed Lane"
        swimlane.refresh_from_db()
        assert swimlane.name == "Renamed Lane"

    def test_update_swimlane_name_empty(self, auth_client, swimlane):
        url = reverse("update_swimlane_name", args=[swimlane.pk])
        resp = _post_json(auth_client, url, {"name": "   "})
        assert resp.status_code == 400

    def test_update_swimlane_name_too_long(self, auth_client, swimlane):
        url = reverse("update_swimlane_name", args=[swimlane.pk])
        resp = _post_json(auth_client, url, {"name": "y" * 101})
        assert resp.status_code == 400

    # ── Delete ───────────────────────────────────────────────────────────────────

    def test_delete_swimlane_success(self, auth_client, board, swimlane):
        Swimlane.objects.create(board=board, name="Other", position=1)
        url = reverse("delete_swimlane", args=[swimlane.pk])
        resp = _post_json(auth_client, url, {})
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert not Swimlane.objects.filter(pk=swimlane.pk).exists()

    def test_cannot_delete_last_swimlane(self, auth_client, board, column, swimlane):
        card = Card.objects.create(title="Card", column=column, position=0, swimlane=swimlane)

        url = reverse("delete_swimlane", args=[swimlane.pk])
        resp = _post_json(auth_client, url, {})
        assert resp.status_code == 400
        assert resp.json()["status"] == "error"

        assert Swimlane.objects.filter(pk=swimlane.pk).exists()
        card.refresh_from_db()
        assert card.swimlane_id == swimlane.pk

    def test_delete_swimlane_reassigns_cards_to_preceding(self, auth_client, board, column):
        lane_a = Swimlane.objects.create(board=board, name="A", position=0)
        lane_b = Swimlane.objects.create(board=board, name="B", position=1)
        card = Card.objects.create(title="Card", column=column, position=0, swimlane=lane_b)

        url = reverse("delete_swimlane", args=[lane_b.pk])
        resp = _post_json(auth_client, url, {})
        assert resp.status_code == 200

        card.refresh_from_db()
        assert card.swimlane_id == lane_a.pk

    def test_delete_swimlane_reassigns_cards_to_first_when_no_preceding(self, auth_client, board, column):
        lane_a = Swimlane.objects.create(board=board, name="A", position=0)
        lane_b = Swimlane.objects.create(board=board, name="B", position=1)
        card = Card.objects.create(title="Card", column=column, position=0, swimlane=lane_a)

        url = reverse("delete_swimlane", args=[lane_a.pk])
        resp = _post_json(auth_client, url, {})
        assert resp.status_code == 200

        card.refresh_from_db()
        assert card.swimlane_id == lane_b.pk

    def test_delete_swimlane_reorders_remaining_positions(self, auth_client, board):
        lane_a = Swimlane.objects.create(board=board, name="A", position=0)
        lane_b = Swimlane.objects.create(board=board, name="B", position=1)
        lane_c = Swimlane.objects.create(board=board, name="C", position=2)

        url = reverse("delete_swimlane", args=[lane_a.pk])
        _post_json(auth_client, url, {})

        lane_b.refresh_from_db()
        lane_c.refresh_from_db()
        assert lane_b.position == 0
        assert lane_c.position == 1

    def test_delete_swimlane_does_not_delete_cards(self, auth_client, board, column, swimlane):
        card = Card.objects.create(title="Keep Me", column=column, position=0, swimlane=swimlane)

        _post_json(auth_client, reverse("delete_swimlane", args=[swimlane.pk]), {})

        assert Card.objects.filter(pk=card.pk).exists()


@pytest.mark.django_db
class TestSwimlanePermissions:

    def test_add_swimlane_unauthenticated(self, client, board):
        resp = _post_json(client, reverse("add_swimlane"), {"board_id": board.pk, "name": "Lane"})
        assert resp.status_code == 302

    def test_update_swimlane_unauthenticated(self, client, swimlane):
        resp = _post_json(client, reverse("update_swimlane_name", args=[swimlane.pk]), {"name": "X"})
        assert resp.status_code == 302

    def test_delete_swimlane_unauthenticated(self, client, swimlane):
        resp = _post_json(client, reverse("delete_swimlane", args=[swimlane.pk]), {})
        assert resp.status_code == 302

    def test_add_swimlane_to_other_users_board(self, client, other_user, board):
        client.force_login(other_user)
        resp = _post_json(client, reverse("add_swimlane"), {"board_id": board.pk, "name": "Lane"})
        assert resp.status_code == 404

    def test_update_swimlane_on_other_users_board(self, client, other_user, swimlane):
        client.force_login(other_user)
        resp = _post_json(client, reverse("update_swimlane_name", args=[swimlane.pk]), {"name": "X"})
        assert resp.status_code == 404

    def test_delete_swimlane_on_other_users_board(self, client, other_user, swimlane):
        client.force_login(other_user)
        resp = _post_json(client, reverse("delete_swimlane", args=[swimlane.pk]), {})
        assert resp.status_code == 404
