"""Tests for app/views/board.py and app/views/column.py"""

import io
import json

import pytest
from django.urls import reverse
from PIL import Image as PilImage

from app.models import Board, Card, Column, Swimlane


def _post_json(client, url, data):
    return client.post(url, json.dumps(data), content_type="application/json")


def _make_png_file(size=(10, 10)):
    """Return an in-memory PNG file object."""
    buf = io.BytesIO()
    img = PilImage.new("RGB", size, color=(255, 0, 0))
    img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "test.png"
    return buf


@pytest.mark.django_db
class TestBoardViews:

    def test_dashboard_shows_only_own_boards(self, auth_client, user, other_user):
        Board.objects.create(name="My Board", owner=user)
        Board.objects.create(name="Their Board", owner=other_user)

        resp = auth_client.get(reverse("dashboard"))

        assert resp.status_code == 200
        board_names = [b.name for b in resp.context["boards"]]
        assert "My Board" in board_names
        assert "Their Board" not in board_names

    def test_create_board_success(self, auth_client):
        resp = _post_json(auth_client, reverse("create_board"), {"name": "New Board", "description": "desc"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["board"]["name"] == "New Board"
        assert Board.objects.filter(name="New Board").exists()

    def test_create_board_seeds_default_columns_and_swimlane(self, auth_client):
        _post_json(auth_client, reverse("create_board"), {"name": "Seeded Board"})

        board = Board.objects.get(name="Seeded Board")
        column_names = list(board.columns.values_list("name", flat=True).order_by("position"))
        assert column_names == ["To Do", "In Progress", "Done"]
        assert board.swimlanes.filter(name="Default").exists()

    def test_create_board_requires_name(self, auth_client):
        resp = _post_json(auth_client, reverse("create_board"), {"name": ""})

        assert resp.status_code == 400
        assert resp.json()["status"] == "error"

    def test_create_board_name_too_long(self, auth_client):
        resp = _post_json(auth_client, reverse("create_board"), {"name": "x" * 101})

        assert resp.status_code == 400

    def test_create_board_invalid_json(self, auth_client):
        resp = auth_client.post(reverse("create_board"), "not-json", content_type="application/json")

        assert resp.status_code == 400

    def test_update_board_name(self, auth_client, board):
        resp = _post_json(
            auth_client,
            reverse("update_board", kwargs={"board_id": board.pk}),
            {"name": "Renamed Board", "description": ""},
        )

        assert resp.status_code == 200
        assert resp.json()["board"]["name"] == "Renamed Board"
        board.refresh_from_db()
        assert board.name == "Renamed Board"

    def test_update_board_requires_name(self, auth_client, board):
        resp = _post_json(
            auth_client,
            reverse("update_board", kwargs={"board_id": board.pk}),
            {"name": "", "description": ""},
        )

        assert resp.status_code == 400

    def test_update_board_title_endpoint(self, auth_client, board):
        resp = _post_json(
            auth_client,
            reverse("update_board_title", kwargs={"board_id": board.pk}),
            {"title": "Quick Title"},
        )

        assert resp.status_code == 200
        assert resp.json()["title"] == "Quick Title"
        board.refresh_from_db()
        assert board.name == "Quick Title"

    def test_delete_board_removes_board_and_children(self, auth_client, user):
        keep = Board.objects.create(name="Keep Me", owner=user)
        Column.objects.create(name="Col A", board=keep, position=0)

        target = Board.objects.create(name="Delete Me", owner=user)
        col = Column.objects.create(name="Col B", board=target, position=0)
        swimlane = Swimlane.objects.create(name="Default", board=target, position=0)
        Card.objects.create(title="Card 1", column=col, swimlane=swimlane, position=0)

        resp = _post_json(
            auth_client,
            reverse("delete_board", kwargs={"board_id": target.pk}),
            {},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert not Board.objects.filter(pk=target.pk).exists()
        assert not Column.objects.filter(board=target).exists()
        assert not Card.objects.filter(column=col).exists()

    def test_delete_last_board_is_rejected(self, auth_client, board):
        resp = _post_json(
            auth_client,
            reverse("delete_board", kwargs={"board_id": board.pk}),
            {},
        )

        assert resp.status_code == 400
        assert Board.objects.filter(pk=board.pk).exists()

    def test_get_board_details(self, auth_client, board):
        resp = auth_client.get(reverse("get_board_details", kwargs={"board_id": board.pk}))

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["board"]["id"] == board.pk
        assert data["board"]["name"] == board.name

    def test_board_detail_page(self, auth_client, board, column):  # column populates board
        resp = auth_client.get(reverse("board_detail", kwargs={"board_id": board.pk}))

        assert resp.status_code == 200

    def test_upload_board_image(self, auth_client, board):
        resp = auth_client.post(
            reverse("upload_board_image", kwargs={"board_id": board.pk}),
            {"image": _make_png_file()},
            format="multipart",
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        board.refresh_from_db()
        assert board.image

    def test_remove_board_image(self, auth_client, board):
        auth_client.post(
            reverse("upload_board_image", kwargs={"board_id": board.pk}),
            {"image": _make_png_file()},
            format="multipart",
        )
        board.refresh_from_db()
        assert board.image, "setup: image must be present before removal"

        resp = _post_json(
            auth_client,
            reverse("remove_board_image", kwargs={"board_id": board.pk}),
            {},
        )

        assert resp.status_code == 200
        board.refresh_from_db()
        assert not board.image

    def test_remove_board_image_when_none_returns_400(self, auth_client, board):
        resp = _post_json(
            auth_client,
            reverse("remove_board_image", kwargs={"board_id": board.pk}),
            {},
        )

        assert resp.status_code == 400


@pytest.mark.django_db
class TestBoardPermissions:

    def test_dashboard_requires_login(self, client):
        resp = client.get(reverse("dashboard"))

        assert resp.status_code == 302
        assert "/login/" in resp["Location"]

    def test_board_detail_requires_login(self, client, board):
        resp = client.get(reverse("board_detail", kwargs={"board_id": board.pk}))

        assert resp.status_code == 302

    def test_create_board_requires_login(self, client):
        resp = _post_json(client, reverse("create_board"), {"name": "X"})

        assert resp.status_code == 302

    def test_update_board_requires_login(self, client, board):
        resp = _post_json(
            client,
            reverse("update_board", kwargs={"board_id": board.pk}),
            {"name": "X"},
        )

        assert resp.status_code == 302

    def test_delete_board_requires_login(self, client, board):
        resp = _post_json(
            client,
            reverse("delete_board", kwargs={"board_id": board.pk}),
            {},
        )

        assert resp.status_code == 302

    def test_other_user_cannot_view_board(self, client, other_user, board):
        client.force_login(other_user)
        resp = client.get(reverse("board_detail", kwargs={"board_id": board.pk}))

        assert resp.status_code == 404

    def test_other_user_cannot_update_board(self, client, other_user, board):
        original_name = board.name
        client.force_login(other_user)
        resp = _post_json(
            client,
            reverse("update_board", kwargs={"board_id": board.pk}),
            {"name": "Hijacked"},
        )

        assert resp.status_code == 404
        board.refresh_from_db()
        assert board.name == original_name

    def test_other_user_cannot_delete_board(self, client, other_user, board):
        Board.objects.create(name="Decoy", owner=other_user)
        client.force_login(other_user)
        resp = _post_json(
            client,
            reverse("delete_board", kwargs={"board_id": board.pk}),
            {},
        )

        assert resp.status_code == 404
        assert Board.objects.filter(pk=board.pk).exists()

    def test_other_user_cannot_get_board_details(self, client, other_user, board):
        client.force_login(other_user)
        resp = client.get(reverse("get_board_details", kwargs={"board_id": board.pk}))

        assert resp.status_code == 404


@pytest.mark.django_db
class TestColumnViews:

    def test_add_column_success(self, auth_client, board):
        resp = _post_json(
            auth_client,
            reverse("add_column"),
            {"board_id": board.pk, "name": "Review"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["column"]["name"] == "Review"
        assert Column.objects.filter(board=board, name="Review").exists()

    def test_add_column_requires_name(self, auth_client, board):
        resp = _post_json(
            auth_client,
            reverse("add_column"),
            {"board_id": board.pk, "name": ""},
        )

        assert resp.status_code == 400

    def test_add_column_name_too_long(self, auth_client, board):
        resp = _post_json(
            auth_client,
            reverse("add_column"),
            {"board_id": board.pk, "name": "x" * 51},
        )

        assert resp.status_code == 400

    def test_add_column_requires_board_id(self, auth_client):
        resp = _post_json(auth_client, reverse("add_column"), {"name": "Orphan"})

        assert resp.status_code == 400

    def test_add_column_on_other_users_board_returns_404(self, client, other_user, board):
        client.force_login(other_user)
        resp = _post_json(
            client,
            reverse("add_column"),
            {"board_id": board.pk, "name": "Sneaky"},
        )

        assert resp.status_code == 404
        assert not Column.objects.filter(board=board, name="Sneaky").exists()

    def test_update_column_name(self, auth_client, column):
        resp = _post_json(
            auth_client,
            reverse("update_column_name", kwargs={"column_id": column.pk}),
            {"name": "Renamed"},
        )

        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"
        column.refresh_from_db()
        assert column.name == "Renamed"

    def test_update_column_name_empty_returns_400(self, auth_client, column):
        resp = _post_json(
            auth_client,
            reverse("update_column_name", kwargs={"column_id": column.pk}),
            {"name": ""},
        )

        assert resp.status_code == 400

    def test_update_column_name_other_user_rejected(self, client, other_user, column):
        original_name = column.name
        client.force_login(other_user)
        resp = _post_json(
            client,
            reverse("update_column_name", kwargs={"column_id": column.pk}),
            {"name": "Hijacked"},
        )

        assert resp.status_code == 404
        column.refresh_from_db()
        assert column.name == original_name

    def test_delete_column_and_its_cards(self, auth_client, board, swimlane):
        col_a = Column.objects.create(name="Keep", board=board, position=0)
        col_b = Column.objects.create(name="Delete Me", board=board, position=1)
        Card.objects.create(title="Orphan Card", column=col_b, swimlane=swimlane, position=0)

        resp = _post_json(
            auth_client,
            reverse("delete_column", kwargs={"column_id": col_b.pk}),
            {},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert not Column.objects.filter(pk=col_b.pk).exists()
        assert not Card.objects.filter(column=col_b).exists()
        assert Column.objects.filter(pk=col_a.pk).exists()

    def test_delete_last_column_is_rejected(self, auth_client, board):
        col = Column.objects.create(name="Only Column", board=board, position=0)

        resp = _post_json(
            auth_client,
            reverse("delete_column", kwargs={"column_id": col.pk}),
            {},
        )

        assert resp.status_code == 400
        assert Column.objects.filter(pk=col.pk).exists()

    def test_delete_column_other_user_returns_404(self, client, other_user, board):
        Column.objects.create(name="Col A", board=board, position=0)
        col_b = Column.objects.create(name="Col B", board=board, position=1)
        client.force_login(other_user)

        resp = _post_json(
            client,
            reverse("delete_column", kwargs={"column_id": col_b.pk}),
            {},
        )

        assert resp.status_code == 404
        assert Column.objects.filter(pk=col_b.pk).exists()

    def test_save_column_sort_order_reorders_cards(self, auth_client, board, column, swimlane):
        card_a = Card.objects.create(title="A", column=column, swimlane=swimlane, position=0)
        card_b = Card.objects.create(title="B", column=column, swimlane=swimlane, position=1)
        card_c = Card.objects.create(title="C", column=column, swimlane=swimlane, position=2)

        resp = _post_json(
            auth_client,
            reverse("save_column_sort_order"),
            {"column_id": column.pk, "card_orders": [card_c.pk, card_a.pk, card_b.pk]},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        card_c.refresh_from_db()
        card_a.refresh_from_db()
        card_b.refresh_from_db()
        assert card_c.position == 0
        assert card_a.position == 1
        assert card_b.position == 2

    def test_save_column_sort_order_requires_login(self, client, column):
        resp = _post_json(
            client,
            reverse("save_column_sort_order"),
            {"column_id": column.pk, "card_orders": []},
        )

        assert resp.status_code == 302

    def test_add_column_requires_login(self, client, board):
        resp = _post_json(client, reverse("add_column"), {"board_id": board.pk, "name": "X"})

        assert resp.status_code == 302

    def test_delete_column_requires_login(self, client, column):
        resp = _post_json(
            client,
            reverse("delete_column", kwargs={"column_id": column.pk}),
            {},
        )

        assert resp.status_code == 302


@pytest.mark.django_db
class TestBoardDescriptionLength:

    def test_create_board_rejects_long_description(self, auth_client):
        resp = _post_json(auth_client, reverse("create_board"), {"name": "B", "description": "x" * 3001})
        assert resp.status_code == 400
        assert not Board.objects.filter(name="B").exists()

    def test_update_board_rejects_long_description(self, auth_client, board):
        resp = _post_json(auth_client, reverse("update_board", args=[board.pk]), {"name": "B", "description": "x" * 3001})
        assert resp.status_code == 400
        board.refresh_from_db()
        assert board.description == ""
