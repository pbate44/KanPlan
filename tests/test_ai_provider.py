"""
Tests for AI provider configuration: OpenRouter vs local OpenAI-compatible
servers (Ollama, LM Studio…). No real network requests are made.
"""

import importlib
import json
from unittest.mock import MagicMock, patch

import openai
import pytest
import requests
from django.urls import reverse

from app.services import ai_service
from app.services.ai_service import CardAIAssistant

OLLAMA_URL = "http://localhost:11434/v1"
MOCK_API_RESPONSE = "Local answer."


@pytest.fixture(autouse=True)
def clear_models_cache():
    ai_service._models_cache.clear()


@pytest.fixture
def local_ai(settings):
    settings.AI_BASE_URL = OLLAMA_URL
    settings.AI_API_KEY = ""
    return settings


def _models_response(data):
    resp = MagicMock()
    resp.json.return_value = {"data": data}
    return resp


def _api_error(cls):
    # ask_question only checks the exception type, so skip the constructor
    # (which needs real HTTP request/response objects).
    return cls.__new__(cls)


class TestSettingsDefaults:

    def _load(self, monkeypatch, **env):
        for key in ("AI_BASE_URL", "AI_API_KEY", "OPENROUTER_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        with patch("dotenv.load_dotenv"):
            import kanplan.settings
            return importlib.reload(kanplan.settings)

    def test_defaults_to_local_ollama(self, monkeypatch):
        s = self._load(monkeypatch)
        assert s.AI_BASE_URL.endswith(":11434/v1")
        assert s.AI_API_KEY == ""

    def test_openrouter_key_alone_selects_openrouter(self, monkeypatch):
        s = self._load(monkeypatch, OPENROUTER_API_KEY="sk-or-x")
        assert s.AI_BASE_URL == "https://openrouter.ai/api/v1"
        assert s.AI_API_KEY == "sk-or-x"

    def test_explicit_base_url_wins(self, monkeypatch):
        s = self._load(monkeypatch, OPENROUTER_API_KEY="sk-or-x", AI_BASE_URL="http://localhost:1234/v1/")
        assert s.AI_BASE_URL == "http://localhost:1234/v1"

    def test_openrouter_key_not_sent_to_other_servers(self, monkeypatch):
        s = self._load(monkeypatch, OPENROUTER_API_KEY="sk-or-x", AI_BASE_URL="https://example.com/v1")
        assert s.AI_API_KEY == ""


class TestProviderName:

    @pytest.mark.parametrize("url, name", [
        ("https://openrouter.ai/api/v1", "OpenRouter"),
        ("http://localhost:11434/v1", "Ollama"),
        ("http://host.docker.internal:11434/v1", "Ollama"),
        ("http://localhost:1234/v1", "LM Studio"),
        ("https://api.openai.com/v1", "api.openai.com"),
    ])
    def test_names(self, settings, url, name):
        settings.AI_BASE_URL = url
        assert ai_service.provider_name() == name


class TestListModels:

    @patch("app.services.ai_service.requests.get")
    def test_openrouter_marks_free_and_paid(self, mock_get, settings):
        mock_get.return_value = _models_response([
            {"id": "a/free", "name": "Free", "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "a/paid", "name": "Paid", "pricing": {"prompt": "0.001", "completion": "0.002"}},
        ])
        models = ai_service.list_models()
        assert [(m["id"], m["free"]) for m in models] == [("a/free", True), ("a/paid", False)]
        assert mock_get.call_args.kwargs["headers"] == {"Authorization": "Bearer test-key"}

    @patch("app.services.ai_service.requests.get")
    def test_local_models_have_no_price_and_no_auth(self, mock_get, local_ai):
        mock_get.return_value = _models_response([{"id": "llama3.2:latest"}])
        models = ai_service.list_models()
        assert models == [{"id": "llama3.2:latest", "name": "llama3.2:latest", "context_length": None, "free": None}]
        assert mock_get.call_args.args[0] == f"{OLLAMA_URL}/models"
        assert mock_get.call_args.kwargs["headers"] == {}

    @patch("app.services.ai_service.requests.get")
    def test_cache_is_per_server(self, mock_get, settings):
        mock_get.return_value = _models_response([{"id": "x"}])
        ai_service.list_models()
        ai_service.list_models()
        assert mock_get.call_count == 1
        settings.AI_BASE_URL = OLLAMA_URL
        ai_service.list_models()
        assert mock_get.call_count == 2


class TestResolveModel:

    def test_openrouter_default(self, settings):
        assert ai_service.resolve_model(None) == ai_service.OPENROUTER_DEFAULT_MODEL

    def test_ai_model_setting_is_default(self, settings):
        settings.AI_MODEL = "openai/gpt-x"
        assert ai_service.resolve_model(None) == "openai/gpt-x"
        assert ai_service.resolve_model("user/pick") == "user/pick"

    @patch("app.services.ai_service.list_models", return_value=[{"id": "llama3.2"}, {"id": "qwen3"}])
    def test_local_defaults_to_first_available(self, _mock, local_ai):
        assert ai_service.resolve_model(None) == "llama3.2"
        assert ai_service.resolve_model("qwen3") == "qwen3"

    @patch("app.services.ai_service.list_models", return_value=[{"id": "llama3.2"}])
    def test_local_ignores_unavailable_saved_model(self, _mock, local_ai):
        assert ai_service.resolve_model("anthropic/claude-haiku-4-5") == "llama3.2"

    @patch("app.services.ai_service.list_models", side_effect=Exception("down"))
    def test_local_unreachable_keeps_saved_model(self, _mock, local_ai):
        assert ai_service.resolve_model("llama3.2") == "llama3.2"
        assert ai_service.resolve_model(None) is None


@pytest.mark.django_db
class TestAskQuestionLocal:

    @patch("app.services.ai_service.list_models", return_value=[{"id": "llama3.2"}])
    @patch("app.services.ai_service.CardAIAssistant._update_context_async")
    @patch("app.services.ai_service._ask_ai", return_value=MOCK_API_RESPONSE)
    def test_works_without_api_key(self, mock_ask, mock_ctx, _mock_models, local_ai, card, user_profile):
        result = CardAIAssistant().ask_question(card.id, "hi", user_profile=user_profile, web_search=True)
        assert result == "Local answer."
        assert mock_ask.call_args.args[0] == "llama3.2"
        # Web search is OpenRouter-only and must not be sent to other servers.
        assert mock_ask.call_args.kwargs["web_search"] is False

    @patch("app.services.ai_service.list_models", return_value=[])
    @patch("app.services.ai_service._ask_ai")
    def test_no_models_returns_setup_message(self, mock_ask, _mock_models, local_ai, card, user_profile):
        result = CardAIAssistant().ask_question(card.id, "hi", user_profile=user_profile)
        assert "ollama pull" in result
        mock_ask.assert_not_called()

    @patch("app.services.ai_service.list_models", return_value=[{"id": "llama3.2"}])
    @patch("app.services.ai_service._ask_ai", side_effect=_api_error(openai.APIConnectionError))
    def test_unreachable_server_message(self, _mock_ask, _mock_models, local_ai, card, user_profile):
        result = CardAIAssistant().ask_question(card.id, "hi", user_profile=user_profile)
        assert "Couldn't reach" in result and "Is Ollama running?" in result

    @patch("app.services.ai_service.list_models", return_value=[{"id": "llama3.2"}])
    @patch("app.services.ai_service._ask_ai", side_effect=_api_error(openai.NotFoundError))
    def test_missing_model_message(self, _mock_ask, _mock_models, local_ai, card, user_profile):
        result = CardAIAssistant().ask_question(card.id, "hi", user_profile=user_profile)
        assert "isn't available" in result and "Settings" in result


@pytest.mark.django_db
class TestAIViews:

    @patch("app.services.ai_service.list_models", side_effect=Exception("down"))
    def test_models_endpoint_reports_unreachable_server(self, _mock, local_ai, auth_client):
        resp = auth_client.get(reverse("get_ai_models"))
        assert resp.status_code == 502
        assert "Couldn't reach" in resp.json()["message"]

    @patch("app.services.ai_service.list_models", return_value=[{"id": "llama3.2", "free": None}])
    def test_models_endpoint_lists_models(self, _mock, local_ai, auth_client):
        resp = auth_client.get(reverse("get_ai_models"))
        assert resp.json() == {"status": "success", "models": [{"id": "llama3.2", "free": None}]}

    def _card_html(self, auth_client, card):
        return auth_client.get(
            reverse("card_detail", args=[card.id]), HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        ).content.decode()

    def test_web_search_toggle_shown_on_openrouter(self, auth_client, card):
        assert "ai-web-search-toggle" in self._card_html(auth_client, card)

    def test_web_search_toggle_hidden_for_local(self, local_ai, auth_client, card):
        assert "ai-web-search-toggle" not in self._card_html(auth_client, card)

    def test_settings_page_shows_provider(self, local_ai, auth_client):
        html = auth_client.get(reverse("user_settings")).content.decode()
        assert "via Ollama" in html and OLLAMA_URL in html


def _use(profile, provider, base_url="", api_key=""):
    profile.ai_provider = provider
    profile.ai_base_url = base_url
    profile.ai_api_key  = api_key
    profile.save()


class TestConnectionFor:

    def test_blank_provider_uses_env(self, settings):
        conn = ai_service.build_connection("")
        assert conn == ai_service.Connection("https://openrouter.ai/api/v1", "test-key", from_env=True)

    def test_local_presets(self, settings):
        assert ai_service.build_connection("ollama").base_url == settings.OLLAMA_BASE_URL
        assert ai_service.build_connection("lmstudio").base_url == settings.LMSTUDIO_BASE_URL
        assert ai_service.build_connection("ollama", "http://gpu-box:11434/v1/").base_url == "http://gpu-box:11434/v1"

    def test_openrouter_falls_back_to_server_key(self, settings):
        settings.OPENROUTER_API_KEY = "sk-server"
        assert ai_service.build_connection("openrouter").api_key == "sk-server"
        assert ai_service.build_connection("openrouter", api_key="sk-mine").api_key == "sk-mine"

    def test_user_connection_ignores_env_default_model(self, settings):
        settings.AI_MODEL = "llama3.2"
        conn = ai_service.build_connection("openrouter", api_key="k")
        assert ai_service.resolve_model(None, conn) == ai_service.OPENROUTER_DEFAULT_MODEL


@pytest.mark.django_db
class TestAskQuestionUserConnection:

    @patch("app.services.ai_service.list_models", return_value=[{"id": "llama3.2"}])
    @patch("app.services.ai_service.CardAIAssistant._update_context_async")
    @patch("app.services.ai_service._ask_ai", return_value=MOCK_API_RESPONSE)
    def test_uses_profile_connection(self, mock_ask, _ctx, _models, card, user_profile):
        _use(user_profile, "ollama")
        CardAIAssistant().ask_question(card.id, "hi", user_profile=user_profile, web_search=True)
        conn = mock_ask.call_args.kwargs["conn"]
        assert conn.base_url.endswith(":11434/v1") and conn.api_key == ""
        assert mock_ask.call_args.kwargs["web_search"] is False

    @patch("app.services.ai_service._ask_ai")
    def test_openrouter_without_key_points_to_settings(self, mock_ask, card, user_profile):
        _use(user_profile, "openrouter")
        result = CardAIAssistant().ask_question(card.id, "hi", user_profile=user_profile)
        assert "Settings" in result and ".env" not in result
        mock_ask.assert_not_called()


@pytest.mark.django_db
class TestConnectionViews:

    def _post(self, client, name, **body):
        return client.post(reverse(name), data=json.dumps(body), content_type="application/json")

    def test_save_custom_connection(self, auth_client, user_profile):
        user_profile.ai_model = "old/model"
        user_profile.save()
        resp = self._post(auth_client, "save_ai_connection",
                          provider="custom", base_url="https://api.openai.com/v1/", api_key="sk-1")
        assert resp.json()["status"] == "success"
        user_profile.refresh_from_db()
        assert (user_profile.ai_provider, user_profile.ai_base_url, user_profile.ai_api_key) == \
            ("custom", "https://api.openai.com/v1", "sk-1")
        # Switching server clears a model picked for the old one.
        assert user_profile.ai_model is None

    def test_blank_key_keeps_saved_key_for_same_server(self, auth_client, user_profile):
        _use(user_profile, "openrouter", api_key="sk-saved")
        self._post(auth_client, "save_ai_connection", provider="openrouter", api_key="")
        user_profile.refresh_from_db()
        assert user_profile.ai_api_key == "sk-saved"

    def test_saved_key_not_carried_to_another_server(self, auth_client, user_profile):
        _use(user_profile, "custom", "https://a.example/v1", "sk-a")
        self._post(auth_client, "save_ai_connection", provider="custom", base_url="https://b.example/v1")
        user_profile.refresh_from_db()
        assert user_profile.ai_api_key == ""

    def test_local_providers_drop_key(self, auth_client, user_profile):
        self._post(auth_client, "save_ai_connection", provider="ollama", api_key="sk-x")
        user_profile.refresh_from_db()
        assert user_profile.ai_provider == "ollama" and user_profile.ai_api_key == ""

    @pytest.mark.parametrize("body, message", [
        ({"provider": "bogus"}, "Unknown"),
        ({"provider": "custom"}, "Enter the server URL"),
        ({"provider": "custom", "base_url": "ftp://x/v1"}, "http"),
    ])
    def test_save_rejects_invalid(self, auth_client, body, message):
        resp = self._post(auth_client, "save_ai_connection", **body)
        assert resp.status_code == 400 and message in resp.json()["message"]

    def test_settings_page_never_renders_key(self, auth_client, user_profile):
        _use(user_profile, "openrouter", api_key="sk-or-secret-1234")
        html = auth_client.get(reverse("user_settings")).content.decode()
        assert "sk-or-secret" not in html
        assert "1234" in html and "via OpenRouter" in html

    def test_models_endpoint_uses_profile_connection(self, auth_client, user_profile):
        _use(user_profile, "lmstudio")
        with patch("app.services.ai_service.list_models", return_value=[]) as mock_list:
            auth_client.get(reverse("get_ai_models"))
        assert mock_list.call_args.args[0].base_url.endswith(":1234/v1")

    @patch("app.services.ai_service.requests.get")
    def test_test_endpoint_reports_model_count(self, mock_get, auth_client):
        mock_get.return_value = _models_response([{"id": "a"}, {"id": "b"}])
        resp = self._post(auth_client, "test_ai_connection", provider="ollama")
        assert resp.json() == {"status": "success", "message": "Connected to Ollama: 2 models available."}

    @patch("app.services.ai_service.requests.get")
    def test_test_endpoint_reports_bad_key(self, mock_get, auth_client):
        err = requests.HTTPError(response=MagicMock(status_code=401))
        mock_get.return_value.raise_for_status.side_effect = err
        resp = self._post(auth_client, "test_ai_connection", provider="openrouter", api_key="bad")
        assert resp.json()["message"] == "OpenRouter rejected the API key."

    @patch("app.services.ai_service.requests.get", side_effect=requests.ConnectionError())
    def test_test_endpoint_reports_unreachable(self, _mock, auth_client):
        resp = self._post(auth_client, "test_ai_connection", provider="lmstudio")
        assert "Couldn't reach LM Studio" in resp.json()["message"]
