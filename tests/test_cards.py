"""Tests for app/views/card.py"""

import json
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from app.models import Board, Card, CardLogEntry, Column, Swimlane


def _post_json(client, url, data):
    return client.post(url, json.dumps(data), content_type="application/json")


@pytest.mark.django_db
class TestCardCRUD:

    def test_create_card_success(self, auth_client, column, swimlane):
        resp = _post_json(auth_client, reverse("add_card"), {
            "column_id": column.pk,
            "title": "New Card",
            "swimlane_id": swimlane.pk,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["card"]["title"] == "New Card"
        assert Card.objects.filter(title="New Card").exists()

    def test_create_card_requires_title(self, auth_client, column, swimlane):
        resp = _post_json(auth_client, reverse("add_card"), {
            "column_id": column.pk,
            "title": "",
            "swimlane_id": swimlane.pk,
        })

        assert resp.status_code == 400

    def test_create_card_requires_column_id(self, auth_client):
        resp = _post_json(auth_client, reverse("add_card"), {"title": "Orphan"})

        assert resp.status_code == 400

    def test_create_card_title_too_long(self, auth_client, column, swimlane):
        resp = _post_json(auth_client, reverse("add_card"), {
            "column_id": column.pk,
            "title": "x" * 101,
            "swimlane_id": swimlane.pk,
        })

        assert resp.status_code == 400

    def test_create_card_invalid_color_rejected(self, auth_client, column, swimlane):
        resp = _post_json(auth_client, reverse("add_card"), {
            "column_id": column.pk,
            "title": "Colored Card",
            "swimlane_id": swimlane.pk,
            "color": "not-a-color",
        })

        assert resp.status_code == 400

    def test_create_card_valid_hex_color(self, auth_client, column, swimlane):
        resp = _post_json(auth_client, reverse("add_card"), {
            "column_id": column.pk,
            "title": "Blue Card",
            "swimlane_id": swimlane.pk,
            "color": "#abc123",
        })

        assert resp.status_code == 200
        assert resp.json()["card"]["color"] == "#abc123"

    def test_create_card_priority_out_of_range_rejected(self, auth_client, column, swimlane):
        resp = _post_json(auth_client, reverse("add_card"), {
            "column_id": column.pk,
            "title": "High Priority",
            "swimlane_id": swimlane.pk,
            "priority": 11,
        })

        assert resp.status_code == 400

    def test_create_card_invalid_json(self, auth_client):
        resp = auth_client.post(reverse("add_card"), "bad-json", content_type="application/json")

        assert resp.status_code == 400

    def test_card_detail_get(self, auth_client, card):
        # Use the AJAX path so the test doesn't need the full template tree.
        resp = auth_client.get(
            reverse("card_detail", kwargs={"card_id": card.pk}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert resp.status_code == 200
        assert resp.context["card"] == card

    def test_update_card_description(self, auth_client, card):
        resp = _post_json(
            auth_client,
            reverse("update_card_description", kwargs={"card_id": card.pk}),
            {"description": "Updated description"},
        )

        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"
        card.refresh_from_db()
        assert card.description == "Updated description"

    def test_update_card_title_via_description_endpoint(self, auth_client, card):
        resp = _post_json(
            auth_client,
            reverse("update_card_description", kwargs={"card_id": card.pk}),
            {"description": "", "title": "New Title"},
        )

        assert resp.status_code == 200
        assert resp.json()["title"] == "New Title"
        card.refresh_from_db()
        assert card.title == "New Title"

    def test_update_card_empty_title_rejected(self, auth_client, card):
        resp = _post_json(
            auth_client,
            reverse("update_card_description", kwargs={"card_id": card.pk}),
            {"description": "", "title": ""},
        )

        assert resp.status_code == 400

    def test_update_card_priority(self, auth_client, card):
        resp = _post_json(
            auth_client,
            reverse("update_card_priority", kwargs={"card_id": card.pk}),
            {"priority": 5},
        )

        assert resp.status_code == 200
        assert resp.json()["priority"] == 5
        card.refresh_from_db()
        assert card.priority == 5

    def test_update_card_priority_out_of_range_rejected(self, auth_client, card):
        resp = _post_json(
            auth_client,
            reverse("update_card_priority", kwargs={"card_id": card.pk}),
            {"priority": 99},
        )

        assert resp.status_code == 400

    def test_update_card_color(self, auth_client, card):
        resp = _post_json(
            auth_client,
            reverse("update_card_color", kwargs={"card_id": card.pk}),
            {"color": "rgb(12, 133, 8)"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["color"] == "rgb(12, 133, 8)"
        assert data["css_class"] == "card-color-dark-green"
        card.refresh_from_db()
        assert card.color == "rgb(12, 133, 8)"

    def test_update_card_color_invalid_format_rejected(self, auth_client, card):
        resp = _post_json(
            auth_client,
            reverse("update_card_color", kwargs={"card_id": card.pk}),
            {"color": "hotpink"},
        )

        assert resp.status_code == 400

    def test_update_card_color_empty_rejected(self, auth_client, card):
        resp = _post_json(
            auth_client,
            reverse("update_card_color", kwargs={"card_id": card.pk}),
            {"color": ""},
        )

        assert resp.status_code == 400

    def test_delete_card(self, auth_client, card):
        card_pk = card.pk
        resp = _post_json(
            auth_client,
            reverse("delete_card", kwargs={"card_id": card.pk}),
            {},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert not Card.objects.filter(pk=card_pk).exists()


@pytest.mark.django_db
class TestCardOrdering:

    def test_update_card_position_moves_to_new_column(self, auth_client, board, swimlane, card):
        col_b = Column.objects.create(name="Done", board=board, position=1)

        resp = _post_json(auth_client, reverse("update_card_position_manual"), {
            "card_id": card.pk,
            "position": 0,
            "column": col_b.pk,
            "swimlane_id": swimlane.pk,
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["card"]["column"] == col_b.pk
        card.refresh_from_db()
        assert card.column_id == col_b.pk

    def test_update_card_position_missing_params_rejected(self, auth_client, card):
        resp = _post_json(auth_client, reverse("update_card_position_manual"), {"card_id": card.pk})

        assert resp.status_code == 400


@pytest.mark.django_db
class TestCardLogEntries:

    def test_add_log_entry_via_post(self, auth_client, card):
        resp = auth_client.post(
            reverse("card_detail", kwargs={"card_id": card.pk}),
            {"text": "Work done here"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["entry"]["text"] == "Work done here"
        assert CardLogEntry.objects.filter(card=card, text="Work done here").exists()

    def test_delete_log_entry(self, auth_client, card):
        entry = CardLogEntry.objects.create(card=card, text="To be deleted", source="manual")

        resp = _post_json(
            auth_client,
            reverse("delete_log_entry", kwargs={"entry_id": entry.pk}),
            {},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert not CardLogEntry.objects.filter(pk=entry.pk).exists()

    def test_delete_log_entry_not_found_returns_404(self, auth_client):
        resp = _post_json(auth_client, reverse("delete_log_entry", kwargs={"entry_id": 99999}), {})

        assert resp.status_code == 404

    def test_delete_log_entry_other_user_returns_404(self, client, other_user, card):
        entry = CardLogEntry.objects.create(card=card, text="Private", source="manual")
        client.force_login(other_user)

        resp = _post_json(
            client,
            reverse("delete_log_entry", kwargs={"entry_id": entry.pk}),
            {},
        )

        assert resp.status_code == 404
        assert CardLogEntry.objects.filter(pk=entry.pk).exists()

    def test_update_log_entry(self, auth_client, card):
        entry = CardLogEntry.objects.create(card=card, text="Original text", source="manual")

        resp = _post_json(
            auth_client,
            reverse("update_log_entry", kwargs={"entry_id": entry.pk}),
            {"text": "Updated text"},
        )

        assert resp.status_code == 200
        assert resp.json()["text"] == "Updated text"
        entry.refresh_from_db()
        assert entry.text == "Updated text"

    def test_update_log_entry_empty_text_rejected(self, auth_client, card):
        entry = CardLogEntry.objects.create(card=card, text="Keep me", source="manual")

        resp = _post_json(
            auth_client,
            reverse("update_log_entry", kwargs={"entry_id": entry.pk}),
            {"text": ""},
        )

        assert resp.status_code == 400
        entry.refresh_from_db()
        assert entry.text == "Keep me"

    def test_update_log_entry_not_found_returns_404(self, auth_client):
        resp = _post_json(auth_client, reverse("update_log_entry", kwargs={"entry_id": 99999}), {"text": "x"})

        assert resp.status_code == 404

    def test_update_log_entry_other_user_returns_404(self, client, other_user, card):
        entry = CardLogEntry.objects.create(card=card, text="Private", source="manual")
        client.force_login(other_user)

        resp = _post_json(
            client,
            reverse("update_log_entry", kwargs={"entry_id": entry.pk}),
            {"text": "Hijacked"},
        )

        assert resp.status_code == 404
        entry.refresh_from_db()
        assert entry.text == "Private"


@pytest.mark.django_db
class TestCardPDFExport:

    def test_export_pdf_returns_pdf_response(self, auth_client, card):
        fake_pdf = b"%PDF-1.4 fake pdf content"
        mock_html = MagicMock()
        mock_html.return_value.write_pdf.return_value = fake_pdf

        mock_weasyprint = MagicMock(HTML=mock_html)

        with patch("app.views.card._get_weasyprint", return_value=mock_weasyprint):
            resp = auth_client.get(reverse("export_card_log_pdf", kwargs={"card_id": card.pk}))

        assert resp.status_code == 200
        assert resp["Content-Type"] == "application/pdf"
        assert b"Content-Disposition" or "attachment" in resp.get("Content-Disposition", "")

    def test_export_pdf_without_weasyprint_returns_503(self, auth_client, card):
        with patch("app.views.card._get_weasyprint", return_value=None):
            resp = auth_client.get(reverse("export_card_log_pdf", kwargs={"card_id": card.pk}))

        assert resp.status_code == 503
        assert b"WeasyPrint" in resp.content

    def test_export_pdf_requires_login(self, client, card):
        resp = client.get(reverse("export_card_log_pdf", kwargs={"card_id": card.pk}))

        assert resp.status_code == 302

    def test_export_pdf_other_user_returns_404(self, client, other_user, card):
        client.force_login(other_user)
        resp = client.get(reverse("export_card_log_pdf", kwargs={"card_id": card.pk}))

        assert resp.status_code == 404


@pytest.mark.django_db
class TestCardPermissions:

    def test_add_card_requires_login(self, client, column):
        resp = _post_json(client, reverse("add_card"), {"column_id": column.pk, "title": "X"})

        assert resp.status_code == 302

    def test_card_detail_requires_login(self, client, card):
        resp = client.get(reverse("card_detail", kwargs={"card_id": card.pk}))

        assert resp.status_code == 302

    def test_delete_card_requires_login(self, client, card):
        resp = _post_json(client, reverse("delete_card", kwargs={"card_id": card.pk}), {})

        assert resp.status_code == 302

    def test_update_description_requires_login(self, client, card):
        resp = _post_json(
            client,
            reverse("update_card_description", kwargs={"card_id": card.pk}),
            {"description": "x"},
        )

        assert resp.status_code == 302

    def test_update_priority_requires_login(self, client, card):
        resp = _post_json(
            client,
            reverse("update_card_priority", kwargs={"card_id": card.pk}),
            {"priority": 3},
        )

        assert resp.status_code == 302

    def test_other_user_cannot_view_card(self, client, other_user, card):
        client.force_login(other_user)
        resp = client.get(reverse("card_detail", kwargs={"card_id": card.pk}))

        assert resp.status_code == 404

    def test_other_user_cannot_delete_card(self, client, other_user, card):
        client.force_login(other_user)
        resp = _post_json(client, reverse("delete_card", kwargs={"card_id": card.pk}), {})

        assert resp.status_code == 404
        assert Card.objects.filter(pk=card.pk).exists()

    def test_other_user_cannot_update_card_description(self, client, other_user, card):
        original_desc = card.description
        client.force_login(other_user)
        resp = _post_json(
            client,
            reverse("update_card_description", kwargs={"card_id": card.pk}),
            {"description": "Hijacked"},
        )

        assert resp.status_code == 404
        card.refresh_from_db()
        assert card.description == original_desc

    def test_other_user_cannot_update_card_priority(self, client, other_user, card):
        client.force_login(other_user)
        resp = _post_json(
            client,
            reverse("update_card_priority", kwargs={"card_id": card.pk}),
            {"priority": 9},
        )

        assert resp.status_code == 404
        card.refresh_from_db()
        assert card.priority != 9

    def test_add_card_on_other_users_column_returns_404(self, client, other_user, column, swimlane):
        client.force_login(other_user)
        resp = _post_json(client, reverse("add_card"), {
            "column_id": column.pk,
            "title": "Sneaky",
            "swimlane_id": swimlane.pk,
        })

        assert resp.status_code == 404
        assert not Card.objects.filter(title="Sneaky").exists()

    def test_update_card_position_rejects_other_users_swimlane(self, auth_client, card, column, swimlane, other_user):
        other_board = Board.objects.create(name="Other Board", owner=other_user)
        other_lane = Swimlane.objects.create(name="Other Lane", board=other_board, position=0)
        card.swimlane = swimlane
        card.save()

        resp = _post_json(auth_client, reverse("update_card_position_manual"), {
            "card_id": card.pk,
            "position": 0,
            "column": column.pk,
            "swimlane_id": other_lane.pk,
        })

        assert resp.status_code == 404
        card.refresh_from_db()
        assert card.swimlane_id == swimlane.pk

    def test_move_card_requires_login(self, client, card):
        resp = _post_json(client, reverse("update_card_position_manual"), {})

        assert resp.status_code == 302


@pytest.mark.django_db
class TestCardBugFixes:

    def test_card_detail_without_ajax_redirects_to_board(self, auth_client, card):
        resp = auth_client.get(reverse("card_detail", kwargs={"card_id": card.pk}))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("board_detail", kwargs={"board_id": card.column.board_id})

    def test_log_entry_post_without_ajax_redirects_to_board(self, auth_client, card):
        resp = auth_client.post(reverse("card_detail", kwargs={"card_id": card.pk}), {"text": "Plain form post"})
        assert resp.status_code == 302
        assert card.log_entries.filter(text="Plain form post").exists()

    @pytest.mark.parametrize("value,expected", [("5", 5), (7, 7)])
    def test_priority_accepts_numeric_values(self, auth_client, card, value, expected):
        resp = _post_json(auth_client, reverse("update_card_priority", kwargs={"card_id": card.pk}), {"priority": value})
        assert resp.status_code == 200
        card.refresh_from_db()
        assert card.priority == expected

    @pytest.mark.parametrize("value", ["abc", True, 11, -1, [3]])
    def test_priority_rejects_invalid_values(self, auth_client, card, value):
        resp = _post_json(auth_client, reverse("update_card_priority", kwargs={"card_id": card.pk}), {"priority": value})
        assert resp.status_code == 400

    def test_add_card_creates_no_orphan_chat_message(self, auth_client, column, swimlane):
        from app.models import AIChatMessage
        resp = _post_json(auth_client, reverse("add_card"), {"column_id": column.pk, "title": "New"})
        assert resp.status_code == 200
        assert not AIChatMessage.objects.filter(card_id=resp.json()["card"]["id"]).exists()

    def test_add_card_rejects_long_description(self, auth_client, column, swimlane):
        resp = _post_json(auth_client, reverse("add_card"), {
            "column_id": column.pk, "title": "Long", "description": "x" * 16001,
        })
        assert resp.status_code == 400
        assert not Card.objects.filter(title="Long").exists()

    def test_update_log_entry_rejects_long_text(self, auth_client, card):
        entry = CardLogEntry.objects.create(card=card, text="short", source="manual")
        resp = _post_json(auth_client, reverse("update_log_entry", kwargs={"entry_id": entry.pk}), {"text": "x" * 100001})
        assert resp.status_code == 400
        entry.refresh_from_db()
        assert entry.text == "short"
