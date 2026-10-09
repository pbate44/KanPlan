"""
Tests for the board AI assistant: app/services/board_ai.py and app/views/board_ai.py

The AI client is replaced with a scripted fake, so no API requests are made.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import openai
import pytest
from django.urls import reverse

from app.models import AIChatMessage, AIChatSession, Board, Card, CardLogEntry, Column, Subtask, Swimlane
from app.services import board_ai
from app.views.helpers import MAX_CARDS_PER_BOARD


def _tool_call(name, args, call_id="call_1"):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


def _reply(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _fake_client(*responses):
    """A client whose completions return `responses` in order (exceptions are raised)."""
    client = MagicMock()
    client.chat.completions.create.side_effect = list(responses)
    return client


def _patch_client(*responses):
    client = _fake_client(*responses)
    return patch("app.services.ai_service._ai_client", return_value=client), client


def _status_error(cls, status, message):
    """An openai status error without building an HTTP response for it."""
    error = cls.__new__(cls)
    Exception.__init__(error, message)
    error.status_code = status
    return error


@pytest.fixture
def lane(board):
    return Swimlane.objects.create(name="Default", board=board, position=0)


@pytest.fixture
def done_column(board):
    return Column.objects.create(name="Done", board=board, position=1)


@pytest.fixture
def board_card(column, lane):
    return Card.objects.create(title="Write docs", description="Explain setup", column=column, swimlane=lane, position=0)


@pytest.fixture
def other_board_card(other_user):
    board = Board.objects.create(name="Private", owner=other_user)
    column = Column.objects.create(name="To Do", board=board, position=0)
    return Card.objects.create(title="Secret", column=column, position=0)


def _ask(client, board, question="Hello", **extra):
    return client.post(
        reverse("board_ai_chat", args=[board.id]),
        data=json.dumps({"question": question, **extra}),
        content_type="application/json",
    )


@pytest.mark.django_db
class TestBoardOutline:

    def test_lists_columns_swimlanes_and_cards_with_ids(self, board, column, done_column, lane, board_card):
        Subtask.objects.create(card=board_card, title="a", is_complete=True)
        Subtask.objects.create(card=board_card, title="b")
        outline = board_ai.board_outline(board)
        assert f"[id {column.id}] To Do | [id {done_column.id}] Done" in outline
        assert f"[id {lane.id}] Default" in outline
        assert f"[card {board_card.id}] Write docs (subtasks 1/2 done)" in outline

    def test_descriptions_are_not_in_the_outline(self, board, board_card):
        assert "Explain setup" not in board_ai.board_outline(board)

    def test_card_without_swimlane_is_shown_in_first_swimlane(self, board, column, lane):
        Card.objects.create(title="Loose", column=column, position=0)
        outline = board_ai.board_outline(board)
        assert outline.index("Swimlane [id") < outline.index("Loose")


@pytest.mark.django_db
class TestBoardChat:

    def test_unauthenticated_redirects(self, client, board):
        assert _ask(client, board).status_code == 302

    def test_other_users_board_returns_404(self, client, other_user, board):
        client.force_login(other_user)
        assert _ask(client, board).status_code == 404

    def test_empty_question_returns_400(self, auth_client, board):
        assert _ask(auth_client, board, question="  ").status_code == 400

    def test_plain_answer_saves_question_and_reply(self, auth_client, board, lane):
        patcher, client = _patch_client(_reply("Two columns."))
        with patcher:
            data = _ask(auth_client, board, "How many columns?").json()
        assert data["response"] == "Two columns."
        assert data["actions"] == []
        roles = list(AIChatMessage.objects.filter(session_id=data["session_id"]).values_list("role", flat=True))
        assert roles == ["system", "user", "assistant"]
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["tools"] == board_ai.TOOLS
        assert "BOARD: Test Board" in kwargs["messages"][0]["content"]

    def test_get_card_details_returns_description_and_subtasks(self, auth_client, board, board_card):
        Subtask.objects.create(card=board_card, title="Draft")
        patcher, client = _patch_client(
            _reply(tool_calls=[_tool_call("get_card_details", {"card_ids": [board_card.id]})]),
            _reply("It explains setup."),
        )
        with patcher:
            _ask(auth_client, board)
        tool_msg = client.chat.completions.create.call_args.kwargs["messages"][-1]
        assert tool_msg["role"] == "tool"
        result = json.loads(tool_msg["content"])
        assert result["cards"][0]["description"] == "Explain setup"
        assert result["cards"][0]["subtasks"] == [{"title": "Draft", "complete": False}]

    def test_get_card_details_hides_other_users_cards(self, auth_client, board, other_board_card):
        patcher, client = _patch_client(
            _reply(tool_calls=[_tool_call("get_card_details", {"card_ids": [other_board_card.id]})]),
            _reply("Not found."),
        )
        with patcher:
            _ask(auth_client, board)
        result = json.loads(client.chat.completions.create.call_args.kwargs["messages"][-1]["content"])
        assert result["cards"] == []
        assert result["not_found"] == [other_board_card.id]

    def test_create_card_with_subtasks(self, auth_client, board, column, lane):
        patcher, _ = _patch_client(
            _reply(tool_calls=[_tool_call("create_card", {
                "column_id": column.id, "swimlane_id": lane.id,
                "title": "Ship it", "description": "Release v1", "subtasks": ["Tag", "Announce"],
            })]),
            _reply("Created it."),
        )
        with patcher:
            data = _ask(auth_client, board, "Add a release card").json()

        card = Card.objects.get(title="Ship it")
        assert (card.column, card.swimlane, card.description) == (column, lane, "Release v1")
        assert list(card.subtasks.values_list("title", flat=True)) == ["Tag", "Announce"]
        assert CardLogEntry.objects.filter(card=card, source="ai").exists()

        [action] = data["actions"]
        assert action["data"]["type"] == "card_created"
        assert action["data"]["card"]["id"] == card.id
        roles = list(AIChatMessage.objects.filter(session_id=data["session_id"]).values_list("role", flat=True))
        assert roles == ["system", "user", "action", "assistant"]

    def test_create_card_in_other_users_column_is_refused(self, auth_client, board, lane, other_board_card):
        patcher, client = _patch_client(
            _reply(tool_calls=[_tool_call("create_card", {"column_id": other_board_card.column_id, "title": "X"})]),
            _reply("Couldn't."),
        )
        with patcher:
            data = _ask(auth_client, board).json()
        assert not Card.objects.filter(title="X").exists()
        assert data["actions"] == []
        assert "error" in json.loads(client.chat.completions.create.call_args.kwargs["messages"][-1]["content"])

    def test_create_card_rejects_long_title(self, auth_client, board, column, lane):
        patcher, client = _patch_client(
            _reply(tool_calls=[_tool_call("create_card", {"column_id": column.id, "title": "x" * 101})]),
            _reply("Too long."),
        )
        with patcher:
            _ask(auth_client, board)
        assert Card.objects.count() == 0
        result = json.loads(client.chat.completions.create.call_args.kwargs["messages"][-1]["content"])
        assert "100 characters" in result["error"]

    def test_create_card_respects_board_limit(self, auth_client, board, column, lane):
        Card.objects.bulk_create([Card(title=f"c{i}", column=column, swimlane=lane) for i in range(MAX_CARDS_PER_BOARD)])
        patcher, client = _patch_client(
            _reply(tool_calls=[_tool_call("create_card", {"column_id": column.id, "title": "One more"})]),
            _reply("Board is full."),
        )
        with patcher:
            _ask(auth_client, board)
        assert not Card.objects.filter(title="One more").exists()
        result = json.loads(client.chat.completions.create.call_args.kwargs["messages"][-1]["content"])
        assert "up to" in result["error"]

    def test_missing_argument_is_reported_to_model(self, auth_client, board, column):
        patcher, client = _patch_client(
            _reply(tool_calls=[_tool_call("create_card", {"column_id": column.id})]),
            _reply("Oops."),
        )
        with patcher:
            _ask(auth_client, board)
        result = json.loads(client.chat.completions.create.call_args.kwargs["messages"][-1]["content"])
        assert result == {"error": "Missing required argument: title."}

    def test_move_card_keeps_swimlane_by_default(self, auth_client, board, done_column, lane, board_card):
        patcher, _ = _patch_client(
            _reply(tool_calls=[_tool_call("move_card", {"card_id": board_card.id, "column_id": done_column.id})]),
            _reply("Moved."),
        )
        with patcher:
            data = _ask(auth_client, board).json()
        board_card.refresh_from_db()
        assert (board_card.column, board_card.swimlane) == (done_column, lane)
        assert data["actions"][0]["data"]["type"] == "card_moved"
        assert "To Do / Default to Done / Default" in data["actions"][0]["content"]

    def test_move_other_users_card_is_refused(self, auth_client, board, done_column, other_board_card):
        patcher, _ = _patch_client(
            _reply(tool_calls=[_tool_call("move_card", {"card_id": other_board_card.id, "column_id": done_column.id})]),
            _reply("No."),
        )
        with patcher:
            _ask(auth_client, board)
        other_board_card.refresh_from_db()
        assert other_board_card.column.board != board

    def test_delete_cards_only_creates_a_pending_request(self, auth_client, board, board_card):
        patcher, client = _patch_client(
            _reply(tool_calls=[_tool_call("delete_cards", {"card_ids": [board_card.id]})]),
            _reply("Please confirm."),
        )
        with patcher:
            data = _ask(auth_client, board).json()
        assert Card.objects.filter(pk=board_card.id).exists()
        [action] = data["actions"]
        assert action["data"]["status"] == "pending"
        assert action["data"]["card_ids"] == [board_card.id]
        result = json.loads(client.chat.completions.create.call_args.kwargs["messages"][-1]["content"])
        assert result["status"] == "awaiting_user_confirmation"

    def test_delete_cards_ignores_other_users_cards(self, auth_client, board, board_card, other_board_card):
        patcher, _ = _patch_client(
            _reply(tool_calls=[_tool_call("delete_cards", {"card_ids": [board_card.id, other_board_card.id]})]),
            _reply("Please confirm."),
        )
        with patcher:
            data = _ask(auth_client, board).json()
        assert data["actions"][0]["data"]["card_ids"] == [board_card.id]

    def test_stops_after_max_rounds(self, auth_client, board, board_card):
        call = _reply(tool_calls=[_tool_call("get_card_details", {"card_ids": [board_card.id]})])
        patcher, client = _patch_client(*[call] * board_ai.MAX_TOOL_ROUNDS)
        with patcher:
            data = _ask(auth_client, board).json()
        assert client.chat.completions.create.call_count == board_ai.MAX_TOOL_ROUNDS
        assert "stopped after" in data["response"]

    def test_model_without_tool_support_gets_clear_message(self, auth_client, board):
        error = _status_error(openai.BadRequestError, 400, "registry.ollama.ai/library/gemma2 does not support tools")
        patcher, _ = _patch_client(error)
        with patcher:
            data = _ask(auth_client, board).json()
        assert "can't use tools" in data["response"]

    def test_openrouter_no_tool_endpoint_gets_clear_message(self, auth_client, board):
        error = _status_error(openai.NotFoundError, 404, "No endpoints found that support tool use.")
        patcher, _ = _patch_client(error)
        with patcher:
            data = _ask(auth_client, board).json()
        assert "can't use tools" in data["response"]

    def test_other_errors_use_standard_message(self, auth_client, board):
        patcher, _ = _patch_client(RuntimeError("boom"))
        with patcher:
            data = _ask(auth_client, board).json()
        assert "problem contacting the AI service" in data["response"]
        assert "boom" not in data["response"]

    def test_web_search_adds_openrouter_plugin(self, auth_client, board):
        patcher, client = _patch_client(_reply("Searched."))
        with patcher:
            _ask(auth_client, board, web_search=True)
        assert client.chat.completions.create.call_args.kwargs["extra_body"] == {"plugins": [{"id": "web"}]}

    def test_web_search_ignored_off_openrouter(self, auth_client, board, user):
        user.profile.ai_provider = "ollama"
        user.profile.ai_model = "llama3.2"
        user.profile.save()
        patcher, client = _patch_client(_reply("Local."))
        with patcher, patch("app.services.ai_service.list_models", return_value=[{"id": "llama3.2"}]):
            _ask(auth_client, board, web_search=True)
        assert "extra_body" not in client.chat.completions.create.call_args.kwargs

    def test_missing_api_key_returns_setup_message(self, auth_client, board, settings):
        settings.AI_API_KEY = ""
        patcher, client = _patch_client()
        with patcher:
            data = _ask(auth_client, board).json()
        assert "OPENROUTER_API_KEY" in data["response"]
        client.chat.completions.create.assert_not_called()

    def test_history_includes_board_changes_as_notes(self, auth_client, board, column, lane):
        patcher, _ = _patch_client(
            _reply(tool_calls=[_tool_call("create_card", {"column_id": column.id, "title": "First"})]),
            _reply("Made it."),
        )
        with patcher:
            session_id = _ask(auth_client, board, "Make a card").json()["session_id"]

        patcher, client = _patch_client(_reply("Yes."))
        with patcher:
            _ask(auth_client, board, "Did that work?", session_id=session_id)
        messages = client.chat.completions.create.call_args.kwargs["messages"]
        assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
        assert 'Created card "First"' in messages[2]["content"]
        assert messages[3]["content"] == "Did that work?"


@pytest.mark.django_db
class TestDeleteConfirmation:

    def _request(self, board, cards, session=None):
        session = session or AIChatSession.objects.create(board=board)
        return AIChatMessage.objects.create(
            board=board, session=session, role="action", content="Asked to delete",
            data={"type": "delete_request", "status": "pending",
                  "card_ids": [c.id for c in cards], "titles": [c.title for c in cards]},
        )

    def _resolve(self, client, board, msg, decision):
        name = "board_ai_confirm_action" if decision == "confirm" else "board_ai_cancel_action"
        return client.post(reverse(name, args=[board.id, msg.id]))

    def test_confirm_deletes_cards_and_records_it(self, auth_client, board, board_card):
        msg = self._request(board, [board_card])
        data = self._resolve(auth_client, board, msg, "confirm").json()
        assert not Card.objects.filter(pk=board_card.id).exists()
        assert data["deleted_card_ids"] == [board_card.id]
        assert data["action"]["data"]["type"] == "delete_done"
        msg.refresh_from_db()
        assert msg.data["status"] == "confirmed"

    def test_cancel_keeps_cards(self, auth_client, board, board_card):
        msg = self._request(board, [board_card])
        data = self._resolve(auth_client, board, msg, "cancel").json()
        assert Card.objects.filter(pk=board_card.id).exists()
        assert data["deleted_card_ids"] == []
        msg.refresh_from_db()
        assert msg.data["status"] == "cancelled"

    def test_cannot_resolve_twice(self, auth_client, board, board_card):
        msg = self._request(board, [board_card])
        self._resolve(auth_client, board, msg, "cancel")
        response = self._resolve(auth_client, board, msg, "confirm")
        assert response.status_code == 409
        assert Card.objects.filter(pk=board_card.id).exists()

    def test_other_user_cannot_confirm(self, client, other_user, board, board_card):
        msg = self._request(board, [board_card])
        client.force_login(other_user)
        assert self._resolve(client, board, msg, "confirm").status_code == 404
        assert Card.objects.filter(pk=board_card.id).exists()

    def test_tampered_request_cannot_delete_other_boards_cards(self, auth_client, board, other_board_card):
        msg = self._request(board, [other_board_card])
        data = self._resolve(auth_client, board, msg, "confirm").json()
        assert Card.objects.filter(pk=other_board_card.id).exists()
        assert data["deleted_card_ids"] == []

    def test_non_delete_action_cannot_be_confirmed(self, auth_client, board):
        session = AIChatSession.objects.create(board=board)
        msg = AIChatMessage.objects.create(
            board=board, session=session, role="action", content="Moved", data={"type": "card_moved"},
        )
        assert self._resolve(auth_client, board, msg, "confirm").status_code == 400

    def test_already_deleted_cards_are_reported(self, auth_client, board, board_card, column, lane):
        second = Card.objects.create(title="Gone", column=column, swimlane=lane)
        msg = self._request(board, [board_card, second])
        second.delete()
        data = self._resolve(auth_client, board, msg, "confirm").json()
        assert "1 had already been deleted" in data["action"]["content"]


@pytest.mark.django_db
class TestBoardSessions:

    def test_history_without_sessions_is_empty(self, auth_client, board):
        data = auth_client.get(reverse("board_ai_history", args=[board.id])).json()
        assert data == {"status": "success", "session_id": None, "messages": []}

    def test_history_includes_action_data(self, auth_client, board):
        session = AIChatSession.objects.create(board=board)
        AIChatMessage.objects.create(board=board, session=session, role="action", content="x", data={"type": "card_moved"})
        data = auth_client.get(reverse("board_ai_history", args=[board.id])).json()
        assert data["messages"][0]["data"] == {"type": "card_moved"}

    def test_new_session_and_list(self, auth_client, board):
        auth_client.post(reverse("board_ai_new_session", args=[board.id]))
        sessions = auth_client.get(reverse("board_ai_sessions", args=[board.id])).json()["sessions"]
        assert len(sessions) == 1
        assert sessions[0]["message_count"] == 0

    def test_board_sessions_are_separate_from_card_sessions(self, auth_client, board, card):
        AIChatSession.objects.create(card=card)
        sessions = auth_client.get(reverse("board_ai_sessions", args=[board.id])).json()["sessions"]
        assert sessions == []

    def test_cannot_read_other_users_history(self, client, other_user, board):
        session = AIChatSession.objects.create(board=board)
        client.force_login(other_user)
        url = reverse("board_ai_history", args=[board.id]) + f"?session_id={session.id}"
        assert client.get(url).status_code == 404

    def test_delete_session(self, auth_client, board):
        session = AIChatSession.objects.create(board=board)
        auth_client.post(reverse("board_ai_delete_session", args=[board.id, session.id]))
        assert not AIChatSession.objects.filter(pk=session.id).exists()

    def test_session_must_have_card_or_board(self, db):
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            AIChatSession.objects.create()
