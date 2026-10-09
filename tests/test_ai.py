"""
Tests for app/views/ai.py and app/services/ai_service.py

All AI API calls are mocked — no real API requests are made.
"""

import json
import pytest
from unittest.mock import patch
from django.urls import reverse

from app.models import (
    AIChatMessage,
    AIChatSession,
    Card,
    CardLogEntry,
)
from app.services.ai_service import CardAIAssistant

MOCK_API_RESPONSE = "This card is about building a new feature."


def _chat_url(card):
    return reverse("card_ai_chat", args=[card.id])


def _post_question(client, card, question="What is this card about?", **extra):
    payload = {"question": question, **extra}
    return client.post(
        _chat_url(card),
        data=json.dumps(payload),
        content_type="application/json",
    )


@pytest.mark.django_db
class TestAIChatEndpoint:

    def test_unauthenticated_redirects_to_login(self, client, card):
        response = _post_question(client, card)
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    def test_nonexistent_card_returns_404(self, auth_client):
        url = reverse("card_ai_chat", args=[99999])
        response = auth_client.post(
            url, data=json.dumps({"question": "hello"}), content_type="application/json"
        )
        assert response.status_code == 404

    def test_empty_question_returns_400(self, auth_client, card):
        response = _post_question(auth_client, card, question="")
        assert response.status_code == 400
        assert response.json()["status"] == "error"

    def test_whitespace_only_question_returns_400(self, auth_client, card):
        response = _post_question(auth_client, card, question="   ")
        assert response.status_code == 400

    @patch("app.services.ai_service._ask_ai", return_value=MOCK_API_RESPONSE)
    @patch("app.services.ai_service.CardAIAssistant._update_context_async")
    def test_success_returns_json_with_response(self, _mock_ctx, _mock_ask, auth_client, card):
        response = _post_question(auth_client, card)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["response"] == MOCK_API_RESPONSE
        assert "session_id" in data

    @patch("app.services.ai_service._ask_ai", return_value=MOCK_API_RESPONSE)
    @patch("app.services.ai_service.CardAIAssistant._update_context_async")
    def test_creates_user_message(self, _mock_ctx, _mock_ask, auth_client, card):
        _post_question(auth_client, card, question="How do I fix this?")
        user_msgs = AIChatMessage.objects.filter(card=card, role="user")
        assert user_msgs.count() == 1
        assert user_msgs.first().content == "How do I fix this?"

    @patch("app.services.ai_service._ask_ai", return_value=MOCK_API_RESPONSE)
    @patch("app.services.ai_service.CardAIAssistant._update_context_async")
    def test_creates_assistant_message(self, _mock_ctx, _mock_ask, auth_client, card):
        _post_question(auth_client, card)
        assistant_msgs = AIChatMessage.objects.filter(card=card, role="assistant")
        assert assistant_msgs.count() == 1
        assert assistant_msgs.first().content == MOCK_API_RESPONSE

    @patch("app.services.ai_service._ask_ai", return_value=MOCK_API_RESPONSE)
    @patch("app.services.ai_service.CardAIAssistant._update_context_async")
    def test_creates_session_when_none_exists(self, _mock_ctx, _mock_ask, auth_client, card):
        assert AIChatSession.objects.filter(card=card).count() == 0
        _post_question(auth_client, card)
        assert AIChatSession.objects.filter(card=card).count() == 1

    @patch("app.services.ai_service._ask_ai", return_value=MOCK_API_RESPONSE)
    @patch("app.services.ai_service.CardAIAssistant._update_context_async")
    def test_reuses_existing_session_when_id_provided(self, _mock_ctx, _mock_ask, auth_client, card):
        session = AIChatSession.objects.create(card=card)
        _post_question(auth_client, card, session_id=session.id)
        assert AIChatSession.objects.filter(card=card).count() == 1

    @patch("app.services.ai_service._ask_ai", return_value=MOCK_API_RESPONSE)
    @patch("app.services.ai_service.CardAIAssistant._update_context_async")
    def test_web_search_flag_forwarded_on_openrouter(self, _mock_ctx, mock_ask, auth_client, card):
        _post_question(auth_client, card, web_search=True)
        assert mock_ask.call_args.kwargs.get("web_search") is True

    @patch("app.services.ai_service._ask_ai")
    def test_missing_api_key_returns_setup_message(self, mock_ask, auth_client, card, settings):
        settings.AI_API_KEY = ""
        response = _post_question(auth_client, card)
        assert response.status_code == 200
        assert "OPENROUTER_API_KEY" in response.json()["response"]
        mock_ask.assert_not_called()

    @patch("app.services.ai_service._ask_ai", side_effect=Exception("connection error"))
    def test_provider_exception_returns_graceful_message(self, _mock_ask, auth_client, card):
        # ask_question catches provider errors and returns a user-friendly string,
        # so the view still returns 200 (not 500).
        response = _post_question(auth_client, card)
        assert response.status_code == 200
        data = response.json()
        assert "problem" in data["response"].lower()


@pytest.mark.django_db
class TestAIChatHistory:

    def _url(self, card):
        return reverse("card_ai_chat_history", args=[card.id])

    def test_unauthenticated_redirects(self, client, card):
        assert client.get(self._url(card)).status_code == 302

    def test_returns_empty_list_when_no_session(self, auth_client, card):
        response = auth_client.get(self._url(card))
        assert response.status_code == 200
        assert response.json()["messages"] == []

    def test_returns_messages_in_order(self, auth_client, card):
        session = AIChatSession.objects.create(card=card)
        AIChatMessage.objects.create(card=card, session=session, role="user",      content="Hi")
        AIChatMessage.objects.create(card=card, session=session, role="assistant", content="Hello!")
        messages = auth_client.get(self._url(card)).json()["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_filters_by_session_id(self, auth_client, card):
        session_a = AIChatSession.objects.create(card=card)
        session_b = AIChatSession.objects.create(card=card)
        AIChatMessage.objects.create(card=card, session=session_a, role="user", content="Session A")
        AIChatMessage.objects.create(card=card, session=session_b, role="user", content="Session B")
        response = auth_client.get(self._url(card), {"session_id": session_a.id})
        messages = response.json()["messages"]
        assert len(messages) == 1
        assert messages[0]["content"] == "Session A"

    def test_message_payload_has_expected_keys(self, auth_client, card):
        session = AIChatSession.objects.create(card=card)
        AIChatMessage.objects.create(card=card, session=session, role="user", content="Test")
        message = auth_client.get(self._url(card)).json()["messages"][0]
        assert {"role", "content", "created_at"} <= message.keys()


@pytest.mark.django_db
class TestChatSessions:

    def test_list_sessions_returns_all_for_card(self, auth_client, card):
        AIChatSession.objects.create(card=card)
        AIChatSession.objects.create(card=card)
        url = reverse("list_chat_sessions", args=[card.id])
        response = auth_client.get(url)
        assert response.status_code == 200
        assert len(response.json()["sessions"]) == 2

    def test_list_sessions_unauthenticated_redirects(self, client, card):
        url = reverse("list_chat_sessions", args=[card.id])
        assert client.get(url).status_code == 302

    def test_read_endpoints_reject_post(self, auth_client, card):
        for name in ("list_chat_sessions", "card_ai_chat_history"):
            assert auth_client.post(reverse(name, args=[card.id])).status_code == 405

    def test_new_session_creates_welcome_message(self, auth_client, card):
        url = reverse("new_chat_session", args=[card.id])
        response = auth_client.post(url)
        assert response.status_code == 200
        session_id = response.json()["session"]["id"]
        welcome = AIChatMessage.objects.get(session_id=session_id, role="system")
        assert "Hello" in welcome.content

    def test_new_session_response_has_expected_keys(self, auth_client, card):
        url = reverse("new_chat_session", args=[card.id])
        session_data = auth_client.post(url).json()["session"]
        assert {"id", "title", "created_at", "message_count"} <= session_data.keys()

    def test_delete_session_removes_it(self, auth_client, card):
        session = AIChatSession.objects.create(card=card)
        url = reverse("delete_chat_session", args=[card.id, session.id])
        response = auth_client.post(url)
        assert response.status_code == 200
        assert not AIChatSession.objects.filter(pk=session.id).exists()

    def test_delete_session_belonging_to_different_card_returns_404(self, auth_client, card, column):
        other_card = Card.objects.create(title="Other Card", column=column, position=1)
        session = AIChatSession.objects.create(card=other_card)
        url = reverse("delete_chat_session", args=[card.id, session.id])
        assert auth_client.post(url).status_code == 404


@pytest.mark.django_db
class TestCardContextAssembly:

    def test_context_includes_card_title(self, card):
        context = CardAIAssistant().get_card_context(card)
        assert card.title in context

    def test_context_includes_card_description(self, card):
        card.description = "Fix the broken login redirect"
        card.save()
        context = CardAIAssistant().get_card_context(card)
        assert "Fix the broken login redirect" in context

    def test_context_includes_subtasks(self, card, subtask):
        context = CardAIAssistant().get_card_context(card)
        assert subtask.title in context
        assert "SUBTASKS" in context

    def test_context_includes_accumulated_ai_context(self, card):
        card.ai_context = "Previously summarised: this is a bug fix."
        card.save()
        context = CardAIAssistant().get_card_context(card)
        assert "Previously summarised" in context
        assert "ACCUMULATED" in context

    def test_context_includes_log_entries(self, card):
        CardLogEntry.objects.create(card=card, text="Investigated root cause", source="manual")
        context = CardAIAssistant().get_card_context(card)
        assert "Investigated root cause" in context

    def test_context_without_ai_context_omits_accumulated_section(self, card):
        card.ai_context = ""
        card.save()
        context = CardAIAssistant().get_card_context(card)
        assert "ACCUMULATED" not in context


@pytest.mark.django_db
class TestAIErrorHandling:

    def test_question_over_max_length_returns_error_string(self, card, user_profile):
        long_q = "x" * (CardAIAssistant.MAX_QUESTION_LENGTH + 1)
        result = CardAIAssistant().ask_question(card.id, long_q, user_profile=user_profile)
        assert "too long" in result.lower()

    def test_nonexistent_card_id_returns_error_string(self, user_profile):
        result = CardAIAssistant().ask_question(99999, "hello", user_profile=user_profile)
        assert "not found" in result.lower()


@pytest.mark.django_db
class TestAIChatPermissions:

    @pytest.fixture
    def other_client(self, client, other_user):
        client.force_login(other_user)
        return client

    @pytest.fixture
    def session(self, card):
        session = AIChatSession.objects.create(card=card)
        AIChatMessage.objects.create(card=card, session=session, role="user", content="Secret plans")
        return session

    @patch("app.services.ai_service._ask_ai", return_value=MOCK_API_RESPONSE)
    def test_cannot_chat_about_other_users_card(self, mock_ask, other_client, card):
        response = _post_question(other_client, card)
        assert response.status_code == 404
        mock_ask.assert_not_called()

    def test_cannot_read_other_users_history(self, other_client, card, session):
        url = reverse("card_ai_chat_history", args=[card.id])
        response = other_client.get(url, {"session_id": session.id})
        assert response.status_code == 404

    def test_cannot_list_other_users_sessions(self, other_client, card, session):
        response = other_client.get(reverse("list_chat_sessions", args=[card.id]))
        assert response.status_code == 404

    def test_cannot_create_session_on_other_users_card(self, other_client, card):
        response = other_client.post(reverse("new_chat_session", args=[card.id]))
        assert response.status_code == 404
        assert not AIChatSession.objects.filter(card=card).exists()

    def test_cannot_delete_other_users_session(self, other_client, card, session):
        url = reverse("delete_chat_session", args=[card.id, session.id])
        assert other_client.post(url).status_code == 404
        assert AIChatSession.objects.filter(pk=session.id).exists()

    @patch("app.services.ai_service.CardAIAssistant.ask_question", side_effect=RuntimeError("db password=hunter2"))
    def test_unexpected_error_does_not_leak_details(self, _mock_ask, auth_client, card):
        response = _post_question(auth_client, card)
        assert response.status_code == 500
        assert "hunter2" not in response.content.decode()


@pytest.mark.django_db
class TestAIChatHistorySaving:

    @patch("app.services.ai_service._ask_ai", return_value=MOCK_API_RESPONSE)
    @patch("app.services.ai_service.CardAIAssistant._update_context_async")
    def test_question_is_not_duplicated_in_history(self, _mock_ctx, mock_ask, auth_client, card):
        _post_question(auth_client, card, question="First question")
        _post_question(auth_client, card, question="Second question")

        history = mock_ask.call_args.args[3]
        assert [m["content"] for m in history] == ["First question", MOCK_API_RESPONSE]
        assert mock_ask.call_args.args[2] == "Second question"

    @patch("app.services.ai_service._ask_ai", return_value=MOCK_API_RESPONSE)
    @patch("app.services.ai_service.CardAIAssistant._update_context_async")
    def test_question_and_answer_are_saved_in_order(self, _mock_ctx, _mock_ask, auth_client, card):
        _post_question(auth_client, card, question="Hello?")
        roles = list(
            AIChatMessage.objects.filter(card=card).exclude(role="system").values_list("role", flat=True)
        )
        assert roles == ["user", "assistant"]
