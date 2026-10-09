import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from app.models import Card, AIChatMessage, AIChatSession
from app.services.ai_service import CardAIAssistant

from .helpers import json_error

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = "Hello! I'm your AI assistant. I can help answer questions about this card. How can I help you today?"


def _get_owned_card(request, card_id):
    return get_object_or_404(Card, pk=card_id, column__board__owner=request.user)


def _create_session(card):
    session = AIChatSession.objects.create(card=card)
    AIChatMessage.objects.create(card=card, session=session, role='system', content=WELCOME_MESSAGE)
    return session


def _get_or_create_active_session(card, session_id=None):
    """Return the requested session (if valid), the most recent session, or a brand-new one."""
    if session_id:
        session = AIChatSession.objects.filter(pk=session_id, card=card).first()
        if session:
            return session
    session = AIChatSession.objects.filter(card=card).order_by('-updated_at').first()
    return session or _create_session(card)


@login_required
@require_POST
def card_ai_chat(request, card_id):
    card = _get_owned_card(request, card_id)
    try:
        data = json.loads(request.body or "{}")
        question      = data.get('question', '').strip()
        session_id    = data.get('session_id')
        web_search    = bool(data.get('web_search', False))
        attachment_ids = data.get('attachment_ids') or []

        if not question:
            return json_error('No question provided')

        session = _get_or_create_active_session(card, session_id)

        ai_assistant = CardAIAssistant()
        response = ai_assistant.ask_question(card_id, question, user_profile=request.user.profile, session_id=session.id, web_search=web_search, attachment_ids=attachment_ids)
        # Saved after asking, so the history sent to the AI doesn't already contain the question.
        AIChatMessage.objects.create(card=card, session=session, role='user', content=question)
        AIChatMessage.objects.create(card=card, session=session, role='assistant', content=response)

        AIChatSession.objects.filter(pk=session.id).update(updated_at=timezone.now())

        return JsonResponse({'status': 'success', 'response': response, 'session_id': session.id})
    except Exception:
        logger.exception("AI chat failed for card %s", card_id)
        return json_error('An error occurred while contacting the AI assistant.', 500)


@login_required
@require_GET
def card_ai_history(request, card_id):
    card = _get_owned_card(request, card_id)
    try:
        session_id = request.GET.get('session_id')
        if session_id:
            messages = AIChatMessage.objects.filter(session_id=session_id, card=card).order_by('created_at')
        else:
            session = AIChatSession.objects.filter(card=card).order_by('-updated_at').first()
            messages = AIChatMessage.objects.filter(session=session).order_by('created_at') if session else AIChatMessage.objects.none()

        return JsonResponse({
            'status': 'success',
            'messages': [
                {
                    'role': msg.role,
                    'content': msg.content,
                    'created_at': msg.created_at.isoformat()
                } for msg in messages
            ]
        })
    except Exception:
        logger.exception("Error loading chat history for card %s", card_id)
        return json_error('An error occurred while loading the chat history.', 500)


@login_required
@require_GET
def list_chat_sessions(request, card_id):
    card = _get_owned_card(request, card_id)
    try:
        sessions = AIChatSession.objects.filter(card=card).order_by('-updated_at')
        result = []
        for s in sessions:
            msg_count = s.messages.filter(role__in=['user', 'assistant']).count()
            result.append({
                'id': s.id,
                'title': s.title,
                'created_at': s.created_at.isoformat(),
                'updated_at': s.updated_at.isoformat(),
                'message_count': msg_count,
            })
        return JsonResponse({'status': 'success', 'sessions': result})
    except Exception:
        logger.exception("Error listing chat sessions for card %s", card_id)
        return json_error('An error occurred while loading chat sessions.', 500)


@login_required
@require_POST
def new_chat_session(request, card_id):
    card = _get_owned_card(request, card_id)
    try:
        session = _create_session(card)
        return JsonResponse({
            'status': 'success',
            'session': {
                'id': session.id,
                'title': session.title,
                'created_at': session.created_at.isoformat(),
                'message_count': 0,
            }
        })
    except Exception:
        logger.exception("Error creating chat session for card %s", card_id)
        return json_error('An error occurred while creating the chat session.', 500)


@login_required
@require_POST
def delete_chat_session(request, card_id, session_id):
    card = _get_owned_card(request, card_id)
    session = get_object_or_404(AIChatSession, pk=session_id, card=card)
    try:
        session.delete()
        return JsonResponse({'status': 'success'})
    except Exception:
        logger.exception("Error deleting chat session %s", session_id)
        return json_error('An error occurred while deleting the chat session.', 500)
