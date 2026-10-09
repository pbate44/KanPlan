"""Tests for app/views/subtasks.py"""

import json

import pytest
from django.urls import reverse

from app.models import Subtask


def _post_json(client, url, data):
    return client.post(url, json.dumps(data), content_type="application/json")


@pytest.mark.django_db
class TestListSubtasks:

    def test_list_returns_subtasks_for_card(self, auth_client, card, subtask):
        resp = auth_client.get(reverse("list_subtasks", kwargs={"card_id": card.pk}))

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        ids = [s["id"] for s in data["subtasks"]]
        assert subtask.pk in ids

    def test_list_returns_empty_list_when_no_subtasks(self, auth_client, card):
        resp = auth_client.get(reverse("list_subtasks", kwargs={"card_id": card.pk}))

        assert resp.status_code == 200
        assert resp.json()["subtasks"] == []

    def test_list_requires_login(self, client, card):
        resp = client.get(reverse("list_subtasks", kwargs={"card_id": card.pk}))

        assert resp.status_code == 302

    def test_list_other_users_card_returns_404(self, client, other_user, card):
        client.force_login(other_user)
        resp = client.get(reverse("list_subtasks", kwargs={"card_id": card.pk}))

        assert resp.status_code == 404

    def test_list_nonexistent_card_returns_404(self, auth_client):
        resp = auth_client.get(reverse("list_subtasks", kwargs={"card_id": 99999}))

        assert resp.status_code == 404

    def test_list_incomplete_subtasks_before_complete(self, auth_client, card):
        s_done = Subtask.objects.create(title="Done", card=card, is_complete=True)
        s_open = Subtask.objects.create(title="Open", card=card, is_complete=False)

        resp = auth_client.get(reverse("list_subtasks", kwargs={"card_id": card.pk}))
        ids = [s["id"] for s in resp.json()["subtasks"]]

        assert ids.index(s_open.pk) < ids.index(s_done.pk)


@pytest.mark.django_db
class TestSubtaskCRUD:

    def test_add_subtask_success(self, auth_client, card):
        resp = _post_json(auth_client, reverse("add_subtask", kwargs={"card_id": card.pk}), {
            "title": "Write tests",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["subtask"]["title"] == "Write tests"
        assert data["subtask"]["is_complete"] is False
        assert Subtask.objects.filter(card=card, title="Write tests").exists()

    def test_add_subtask_persisted_with_correct_card(self, auth_client, card):
        _post_json(auth_client, reverse("add_subtask", kwargs={"card_id": card.pk}), {
            "title": "Linked subtask",
        })

        st = Subtask.objects.get(title="Linked subtask")
        assert st.card_id == card.pk

    def test_add_subtask_empty_title_rejected(self, auth_client, card):
        resp = _post_json(auth_client, reverse("add_subtask", kwargs={"card_id": card.pk}), {
            "title": "",
        })

        assert resp.status_code == 400
        assert not Subtask.objects.filter(card=card).exists()

    def test_add_subtask_title_too_long_rejected(self, auth_client, card):
        resp = _post_json(auth_client, reverse("add_subtask", kwargs={"card_id": card.pk}), {
            "title": "x" * 101,
        })

        assert resp.status_code == 400

    def test_add_subtask_invalid_json_rejected(self, auth_client, card):
        resp = auth_client.post(
            reverse("add_subtask", kwargs={"card_id": card.pk}),
            "not-json",
            content_type="application/json",
        )

        assert resp.status_code == 400

    def test_add_subtask_requires_login(self, client, card):
        resp = _post_json(client, reverse("add_subtask", kwargs={"card_id": card.pk}), {
            "title": "Sneaky",
        })

        assert resp.status_code == 302

    def test_add_subtask_other_users_card_returns_404(self, client, other_user, card):
        client.force_login(other_user)
        resp = _post_json(client, reverse("add_subtask", kwargs={"card_id": card.pk}), {
            "title": "Hijack",
        })

        assert resp.status_code == 404
        assert not Subtask.objects.filter(title="Hijack").exists()

    def test_delete_subtask_success(self, auth_client, subtask):
        subtask_pk = subtask.pk
        resp = _post_json(
            auth_client,
            reverse("delete_subtask", kwargs={"subtask_id": subtask.pk}),
            {},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert not Subtask.objects.filter(pk=subtask_pk).exists()

    def test_delete_subtask_requires_login(self, client, subtask):
        resp = _post_json(client, reverse("delete_subtask", kwargs={"subtask_id": subtask.pk}), {})

        assert resp.status_code == 302
        assert Subtask.objects.filter(pk=subtask.pk).exists()

    def test_delete_subtask_other_user_returns_404(self, client, other_user, subtask):
        client.force_login(other_user)
        resp = _post_json(client, reverse("delete_subtask", kwargs={"subtask_id": subtask.pk}), {})

        assert resp.status_code == 404
        assert Subtask.objects.filter(pk=subtask.pk).exists()

    def test_delete_subtask_nonexistent_returns_404(self, auth_client):
        resp = _post_json(auth_client, reverse("delete_subtask", kwargs={"subtask_id": 99999}), {})

        assert resp.status_code == 404


@pytest.mark.django_db
class TestSubtaskToggle:

    def test_toggle_incomplete_to_complete(self, auth_client, subtask):
        assert subtask.is_complete is False

        resp = _post_json(auth_client, reverse("toggle_subtask", kwargs={"subtask_id": subtask.pk}), {})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["subtask"]["is_complete"] is True
        subtask.refresh_from_db()
        assert subtask.is_complete is True

    def test_toggle_complete_to_incomplete(self, auth_client, card):
        st = Subtask.objects.create(title="Done already", card=card, is_complete=True)

        resp = _post_json(auth_client, reverse("toggle_subtask", kwargs={"subtask_id": st.pk}), {})

        assert resp.status_code == 200
        assert resp.json()["subtask"]["is_complete"] is False
        st.refresh_from_db()
        assert st.is_complete is False

    def test_toggle_requires_login(self, client, subtask):
        resp = _post_json(client, reverse("toggle_subtask", kwargs={"subtask_id": subtask.pk}), {})

        assert resp.status_code == 302

    def test_toggle_other_users_subtask_returns_404(self, client, other_user, subtask):
        client.force_login(other_user)
        resp = _post_json(client, reverse("toggle_subtask", kwargs={"subtask_id": subtask.pk}), {})

        assert resp.status_code == 404
        subtask.refresh_from_db()
        assert subtask.is_complete is False

    def test_toggle_nonexistent_subtask_returns_404(self, auth_client):
        resp = _post_json(auth_client, reverse("toggle_subtask", kwargs={"subtask_id": 99999}), {})

        assert resp.status_code == 404


@pytest.mark.django_db
class TestSubtaskPermissions:

    def test_update_subtask_title(self, auth_client, subtask):
        resp = _post_json(
            auth_client,
            reverse("update_subtask", kwargs={"subtask_id": subtask.pk}),
            {"title": "Updated title"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["subtask"]["title"] == "Updated title"
        subtask.refresh_from_db()
        assert subtask.title == "Updated title"

    def test_update_subtask_empty_title_rejected(self, auth_client, subtask):
        original = subtask.title
        resp = _post_json(
            auth_client,
            reverse("update_subtask", kwargs={"subtask_id": subtask.pk}),
            {"title": ""},
        )

        assert resp.status_code == 400
        subtask.refresh_from_db()
        assert subtask.title == original

    def test_update_subtask_title_too_long_rejected(self, auth_client, subtask):
        original = subtask.title
        resp = _post_json(
            auth_client,
            reverse("update_subtask", kwargs={"subtask_id": subtask.pk}),
            {"title": "x" * 101},
        )

        assert resp.status_code == 400
        subtask.refresh_from_db()
        assert subtask.title == original

    def test_update_subtask_invalid_json_rejected(self, auth_client, subtask):
        resp = auth_client.post(
            reverse("update_subtask", kwargs={"subtask_id": subtask.pk}),
            "not-json",
            content_type="application/json",
        )

        assert resp.status_code == 400

    def test_update_subtask_requires_login(self, client, subtask):
        resp = _post_json(
            client,
            reverse("update_subtask", kwargs={"subtask_id": subtask.pk}),
            {"title": "New title"},
        )

        assert resp.status_code == 302

    def test_update_subtask_other_user_returns_404(self, client, other_user, subtask):
        original = subtask.title
        client.force_login(other_user)
        resp = _post_json(
            client,
            reverse("update_subtask", kwargs={"subtask_id": subtask.pk}),
            {"title": "Hijacked"},
        )

        assert resp.status_code == 404
        subtask.refresh_from_db()
        assert subtask.title == original

    def test_update_subtask_nonexistent_returns_404(self, auth_client):
        resp = _post_json(
            auth_client,
            reverse("update_subtask", kwargs={"subtask_id": 99999}),
            {"title": "Ghost"},
        )

        assert resp.status_code == 404
