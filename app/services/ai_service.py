import threading
import time
import logging
import docx
import csv
from dataclasses import dataclass
from io import BytesIO, StringIO
from urllib.parse import urlparse

import openai
import requests
from django.conf import settings
from django.utils import timezone

from app.models import Card, CardAttachment, CardLogEntry, AIChatMessage
from pypdf import PdfReader

logger = logging.getLogger(__name__)

STATIC_INSTRUCTIONS = """You are a helpful AI assistant for a project management system.
Answer questions based on the card context provided. If the information isn't in the context,
acknowledge this but provide helpful general advice related to the card's topic.
Keep your answers concise and professional."""

CONTEXT_UPDATE_INSTRUCTIONS = """You are maintaining a compact knowledge summary for a project task card.
You will be given the current summary (may be empty) and recent activity data.
Produce an updated summary that captures all key facts, decisions, blockers, and progress.
Be concise but complete. Do not invent information. Output only the updated summary text, nothing else."""

# Used on OpenRouter when neither the user nor AI_MODEL picks a model.
OPENROUTER_DEFAULT_MODEL = "anthropic/claude-haiku-4-5"

LOG_LIMIT          = 20
FILE_LIMIT         = 5
CHAT_HISTORY_LIMIT = 10


@dataclass(frozen=True)
class Connection:
    base_url: str
    api_key:  str = ""
    # True when it comes from .env, False when the user set it in Settings.
    from_env: bool = True


def default_connection():
    return Connection(settings.AI_BASE_URL, settings.AI_API_KEY)


def preset_url(provider):
    return {
        "ollama":     settings.OLLAMA_BASE_URL,
        "lmstudio":   settings.LMSTUDIO_BASE_URL,
        "openrouter": settings.OPENROUTER_BASE_URL,
    }.get(provider, "")


def build_connection(provider, base_url="", api_key=""):
    """The connection for a provider picked in Settings ('' = the .env default)."""
    if not provider:
        return default_connection()
    if provider == "openrouter":
        return Connection(settings.OPENROUTER_BASE_URL, api_key or settings.OPENROUTER_API_KEY, from_env=False)
    return Connection((base_url or preset_url(provider)).rstrip("/"), api_key, from_env=False)


def connection_for(profile):
    if profile is None:
        return default_connection()
    return build_connection(profile.ai_provider, profile.ai_base_url, profile.ai_api_key)


def _where_to_fix(conn, env_var):
    if conn.from_env:
        return f"Check {env_var} in your .env file."
    return "Check the connection in Settings → AI Assistant."


def no_api_key_message(conn):
    if conn.from_env:
        return (
            "OpenRouter needs an API key. Add OPENROUTER_API_KEY to the .env file in the "
            "KanPlan folder and restart the app, or add a key in Settings → AI Assistant."
        )
    return "OpenRouter needs an API key. Add one in Settings → AI Assistant."


def is_openrouter(conn=None):
    conn = conn or default_connection()
    return "openrouter.ai" in conn.base_url


def provider_name(conn=None):
    conn = conn or default_connection()
    if is_openrouter(conn):
        return "OpenRouter"
    url = urlparse(conn.base_url)
    known_ports = {11434: "Ollama", 1234: "LM Studio"}
    return known_ports.get(url.port) or url.hostname or conn.base_url


def unreachable_message(conn=None):
    conn = conn or default_connection()
    hint = " Is Ollama running?" if provider_name(conn) == "Ollama" else ""
    return (
        f"Couldn't reach the AI server ({provider_name(conn)} at {conn.base_url}).{hint} "
        f"{_where_to_fix(conn, 'AI_BASE_URL')}"
    )


def _ai_client(conn):
    # Local servers don't need a key, but the client requires a non-empty one.
    return openai.OpenAI(api_key=conn.api_key or "not-needed", base_url=conn.base_url)


# base_url -> {"models": [...], "ts": fetch time}
_models_cache = {}


def _is_free(model):
    pricing = model.get("pricing", {})
    return float(pricing.get("prompt") or 1) == 0 and float(pricing.get("completion") or 1) == 0


def list_models(conn=None, use_cache=True):
    """Models offered by the server. Raises if it can't be reached."""
    conn = conn or default_connection()
    # Local servers gain models whenever the user pulls one, so cache briefly.
    ttl = 3600 if is_openrouter(conn) else 30
    cached = _models_cache.get(conn.base_url)
    if use_cache and cached and time.time() - cached["ts"] < ttl:
        return cached["models"]

    headers = {"Authorization": f"Bearer {conn.api_key}"} if conn.api_key else {}
    resp = requests.get(f"{conn.base_url}/models", headers=headers, timeout=5)
    resp.raise_for_status()
    models = [
        {
            "id":             m["id"],
            "name":           m.get("name") or m["id"],
            "context_length": m.get("context_length"),
            # Only OpenRouter reports pricing; None means "not applicable".
            "free":           _is_free(m) if is_openrouter(conn) else None,
        }
        for m in resp.json().get("data", [])
        if m.get("id")
    ]
    _models_cache[conn.base_url] = {"models": models, "ts": time.time()}
    return models


def _default_model(conn):
    # AI_MODEL is meant for the .env server; a model name rarely carries across providers.
    return settings.AI_MODEL if conn.from_env else ""


def resolve_model(user_model, conn=None):
    """The model to call: the user's pick, else AI_MODEL, else a provider default."""
    conn = conn or default_connection()
    if is_openrouter(conn):
        return user_model or _default_model(conn) or OPENROUTER_DEFAULT_MODEL
    try:
        available = [m["id"] for m in list_models(conn)]
    except Exception:
        available = []
    # Ignore a saved model the server doesn't have (e.g. after switching provider).
    if user_model and (user_model in available or not available):
        return user_model
    return _default_model(conn) or (available[0] if available else None)


def model_display_name(user_model, conn=None):
    conn = conn or default_connection()
    if is_openrouter(conn):
        return user_model or _default_model(conn) or OPENROUTER_DEFAULT_MODEL
    return user_model or _default_model(conn) or "Default model"


def prepare_call(user_profile):
    """(conn, model, None) when the AI can be called, else (conn, None, a message saying why not)."""
    conn = connection_for(user_profile)
    if is_openrouter(conn) and not conn.api_key:
        return conn, None, no_api_key_message(conn)

    model = resolve_model(user_profile.ai_model, conn)
    if not model:
        return conn, None, (
            f"No AI model is available from {provider_name(conn)} at {conn.base_url}. "
            "Make sure it's running and has a model installed (for Ollama: `ollama pull llama3.2`)."
        )
    return conn, model, None


def api_error_message(exc, conn, model):
    """A message for the user explaining a failed AI call."""
    if isinstance(exc, openai.APIConnectionError):
        logger.warning("AI server unreachable at %s", conn.base_url)
        return unreachable_message(conn)
    if isinstance(exc, openai.NotFoundError):
        return (
            f"The model '{model}' isn't available from {provider_name(conn)}. "
            "Choose another in Settings → AI Model."
        )
    if isinstance(exc, openai.AuthenticationError):
        return f"{provider_name(conn)} rejected the API key. {_where_to_fix(conn, 'AI_API_KEY')}"
    logger.exception("Error calling AI API at %s", conn.base_url, exc_info=exc)
    return "There was a problem contacting the AI service. Please try again in a moment."


_context_update_in_progress: set = set()
_context_update_lock = threading.Lock()


def _ask_ai(model, card_context, question, history=None, web_search=False, conn=None):
    client = _ai_client(conn or default_connection())
    system_message = (
        f"{STATIC_INSTRUCTIONS}\n\n"
        f"You have access to the following information about a card (task):\n\n{card_context}"
    )
    messages = [{"role": "system", "content": system_message}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})

    extra_kwargs = {}
    if web_search:
        extra_kwargs["extra_body"] = {"plugins": [{"id": "web"}]}

    response = client.chat.completions.create(
        model=model,
        max_tokens=1500,
        temperature=0.3,
        messages=messages,
        **extra_kwargs,
    )
    return response.choices[0].message.content


def _ask_ai_raw(model, system_text, user_text, conn=None):
    client = _ai_client(conn or default_connection())
    response = client.chat.completions.create(
        model=model,
        max_tokens=1000,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
    )
    return response.choices[0].message.content or ""


class CardAIAssistant:

    MAX_QUESTION_LENGTH = 2000

    def _needs_context_update(self, card):
        if not card.ai_context_updated_at:
            return (
                CardLogEntry.objects.filter(card=card).exists() or
                card.attachments.exists()
            )
        cutoff = card.ai_context_updated_at
        has_new_logs  = CardLogEntry.objects.filter(card=card, created_at__gt=cutoff).exists()
        has_new_files = card.attachments.filter(upload_date__gt=cutoff).exists()
        return has_new_logs or has_new_files

    def _build_recent_data_snapshot(self, card, include_file_content=False):
        parts = [
            f"CARD TITLE: {card.title}",
            f"CARD DESCRIPTION: {card.description}",
        ]

        subtasks = card.subtasks.all()
        if subtasks:
            parts.append("\nSUBTASKS:")
            for subtask in subtasks:
                status = "complete" if subtask.is_complete else "incomplete"
                due    = f" (due: {subtask.due_date})" if subtask.due_date else ""
                parts.append(f"- [{status}] {subtask.title}{due}")
                if subtask.description:
                    parts.append(f"  {subtask.description}")

        log_entries = list(
            CardLogEntry.objects.filter(card=card).order_by('-created_at')[:LOG_LIMIT]
        )
        log_entries.reverse()
        if log_entries:
            parts.append(f"\nRECENT LOG ENTRIES (last {LOG_LIMIT}):")
            for entry in log_entries:
                timestamp = entry.created_at.strftime("%Y-%m-%d %H:%M")
                parts.append(f"[{timestamp}] ({entry.source}) {entry.text}")

        attachments = list(card.attachments.order_by('-upload_date')[:FILE_LIMIT])
        if attachments:
            if include_file_content:
                parts.append(f"\nRECENT ATTACHED FILES (last {FILE_LIMIT}):")
                for attachment in attachments:
                    try:
                        parts.append(f"\nCONTENT FROM FILE: {attachment.filename}")
                        file_content = get_file_content_from_storage(attachment)
                        if len(file_content) > 5000:
                            parts.append(file_content[:5000] + "... [truncated]")
                        else:
                            parts.append(file_content)
                    except Exception as e:
                        parts.append(f"[Error reading file: {str(e)}]")
            else:
                parts.append("\nATTACHED FILES (select one in chat to include its content):")
                for attachment in attachments:
                    date_str = attachment.upload_date.strftime("%Y-%m-%d") if attachment.upload_date else "unknown"
                    parts.append(f"- {attachment.filename} ({attachment.file_type}, uploaded {date_str})")

        return "\n".join(parts)

    def get_card_context(self, card):
        parts = []
        if card.ai_context:
            parts.append("ACCUMULATED CARD CONTEXT (compressed history):")
            parts.append(card.ai_context)
            parts.append("")
        parts.append(self._build_recent_data_snapshot(card))
        return "\n".join(parts)

    def get_chat_history(self, card_id, session_id=None):
        qs = AIChatMessage.objects.filter(role__in=['user', 'assistant'])
        if session_id:
            qs = qs.filter(session_id=session_id)
        else:
            qs = qs.filter(card__id=card_id)
        recent_messages = qs.order_by('-created_at')[:CHAT_HISTORY_LIMIT]
        return [
            {"role": msg.role, "content": msg.content}
            for msg in reversed(list(recent_messages))
        ]

    def _update_context_async(self, card_id, model, conn=None):
        conn = conn or default_connection()
        if is_openrouter(conn) and not conn.api_key:
            return
        summary_model = (settings.AI_SUMMARY_MODEL if conn.from_env else "") or model
        with _context_update_lock:
            if card_id in _context_update_in_progress:
                return
            _context_update_in_progress.add(card_id)

        def _run():
            try:
                card        = Card.objects.get(id=card_id)
                recent_data = self._build_recent_data_snapshot(card, include_file_content=True)

                user_text = (
                    f"CURRENT SUMMARY:\n{card.ai_context or '(none yet)'}\n\n"
                    f"RECENT ACTIVITY DATA:\n{recent_data}\n\n"
                    "Please produce an updated compact summary capturing all key facts, "
                    "decisions, progress, and blockers from both the current summary and "
                    "the recent activity data."
                )

                new_context = _ask_ai_raw(
                    summary_model, CONTEXT_UPDATE_INSTRUCTIONS, user_text, conn=conn
                )

                Card.objects.filter(id=card_id).update(
                    ai_context=new_context,
                    ai_context_updated_at=timezone.now(),
                )
            except Exception:
                logger.exception("Background context update failed for card %s", card_id)
            finally:
                with _context_update_lock:
                    _context_update_in_progress.discard(card_id)

        threading.Thread(target=_run, daemon=True).start()

    def ask_question(self, card_id, question, user_profile, session_id=None, web_search=False, attachment_ids=None):
        if len(question) > self.MAX_QUESTION_LENGTH:
            return (
                f"Your question is too long (max {self.MAX_QUESTION_LENGTH} characters). "
                "Please shorten it and try again."
            )

        conn, model, problem = prepare_call(user_profile)
        if problem:
            return problem

        # Web search is an OpenRouter plugin; other servers would reject it.
        web_search = web_search and is_openrouter(conn)

        try:
            card = Card.objects.get(id=card_id)
        except Card.DoesNotExist:
            return "Card not found."

        card_context = self.get_card_context(card)

        if attachment_ids:
            file_sections = []
            for att_id in attachment_ids:
                try:
                    attachment   = CardAttachment.objects.get(id=att_id, card=card)
                    file_content = get_file_content_from_storage(attachment)
                    if len(file_content) > 8000:
                        file_content = file_content[:8000] + "... [truncated]"
                    file_sections.append(
                        f"FILE ATTACHED TO THIS QUESTION — {attachment.filename}:\n{file_content}"
                    )
                except CardAttachment.DoesNotExist:
                    pass
            if file_sections:
                card_context += "\n\n" + "\n\n".join(file_sections)

        history = self.get_chat_history(card_id, session_id=session_id)

        try:
            response_text = _ask_ai(
                model, card_context, question, history, web_search=web_search, conn=conn
            )

            if self._needs_context_update(card):
                self._update_context_async(card_id, model, conn)

            return response_text

        except Exception as exc:
            return api_error_message(exc, conn, model)


def get_file_content_from_storage(attachment):
    try:
        with attachment.file.open('rb') as f:
            file_bytes = f.read()
    except Exception as e:
        return f"[Error reading file from storage: {str(e)}]"

    kind = attachment.kind

    try:
        if kind == 'pdf':
            pdf = PdfReader(BytesIO(file_bytes))
            return "\n".join(page.extract_text() for page in pdf.pages)
        elif kind == 'docx':
            doc = docx.Document(BytesIO(file_bytes))
            return "\n".join(para.text for para in doc.paragraphs)
        elif kind in ('text', 'rtf'):
            return file_bytes.decode('utf-8', errors='replace')
        elif kind == 'csv':
            reader = csv.reader(StringIO(file_bytes.decode('utf-8', errors='replace')))
            return "\n".join(",".join(row) for row in reader)
        else:
            return "[Unsupported file type for content extraction]"
    except Exception as e:
        return f"[Error extracting file content: {str(e)}]"
