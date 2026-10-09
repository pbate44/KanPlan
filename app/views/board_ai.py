import json
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from app.models import AIChatMessage, AIChatSession, Board, Card
from app.services.board_ai import ask_board_question

from .helpers import json_error

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = (
    "Hello! I'm your board assistant. I can answer questions about this board, "
    "and create, move or delete cards when you ask. How can I help?"
)


def _get_owned_board(request, board_id):
    return get_object_or_404(Board, pk=board_id, owner=request.user)


def _create_session(board):
    session = AIChatSession.objects.create(board=board)
    AIChatMessage.objects.create(board=board, session=session, role='system', content=WELCOME_MESSAGE)
    return session


def _get_or_create_active_session(board, session_id=None):
    """Return the requested session (if valid), the most recent session, or a brand-new one."""
    if session_id:
        session = AIChatSession.objects.filter(pk=session_id, board=board).first()
        if session:
            return session
    session = AIChatSession.objects.filter(board=board).order_by('-updated_at').first()
    return session or _create_session(board)


def _touch(session):
    AIChatSession.objects.filter(pk=session.pk).update(updated_at=timezone.now())


def _message_json(msg):
    return {
        'id':         msg.id,
        'role':       msg.role,
        'content':    msg.content,
        'data':       msg.data,
        'created_at': msg.created_at.isoformat(),
    }


@login_required
@require_POST
def board_ai_chat(request, board_id):
    board = _get_owned_board(request, board_id)
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return json_error('Invalid JSON')

    question = str(data.get('question') or '').strip()
    if not question:
        return json_error('No question provided')

    try:
        session = _get_or_create_active_session(board, data.get('session_id'))
        reply, actions = ask_board_question(
            board, request.user, session, question, web_search=bool(data.get('web_search', False)),
        )
        _touch(session)
        return JsonResponse({
            'status':     'success',
            'response':   reply.content,
            'actions':    [_message_json(a) for a in actions],
            'session_id': session.id,
        })
    except Exception:
        logger.exception("Board AI chat failed for board %s", board_id)
        return json_error('An error occurred while contacting the AI assistant.', 500)


@login_required
@require_GET
def board_ai_history(request, board_id):
    board = _get_owned_board(request, board_id)
    session_id = request.GET.get('session_id')
    if session_id:
        if not session_id.isdigit():
            raise Http404
        session = get_object_or_404(AIChatSession, pk=session_id, board=board)
    else:
        session = AIChatSession.objects.filter(board=board).order_by('-updated_at').first()
    messages = session.messages.order_by('created_at', 'id') if session else []
    return JsonResponse({
        'status':     'success',
        'session_id': session.id if session else None,
        'messages':   [_message_json(m) for m in messages],
    })


@login_required
@require_GET
def board_ai_sessions(request, board_id):
    board = _get_owned_board(request, board_id)
    sessions = AIChatSession.objects.filter(board=board).order_by('-updated_at')
    return JsonResponse({
        'status': 'success',
        'sessions': [
            {
                'id':            s.id,
                'title':         s.title,
                'created_at':    s.created_at.isoformat(),
                'updated_at':    s.updated_at.isoformat(),
                'message_count': s.messages.filter(role__in=['user', 'assistant']).count(),
            }
            for s in sessions
        ],
    })


@login_required
@require_POST
def board_ai_new_session(request, board_id):
    board = _get_owned_board(request, board_id)
    session = _create_session(board)
    return JsonResponse({
        'status': 'success',
        'session': {
            'id':            session.id,
            'title':         session.title,
            'created_at':    session.created_at.isoformat(),
            'message_count': 0,
        },
    })


@login_required
@require_POST
def board_ai_delete_session(request, board_id, session_id):
    board = _get_owned_board(request, board_id)
    get_object_or_404(AIChatSession, pk=session_id, board=board).delete()
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def board_ai_resolve_action(request, board_id, message_id, decision):
    """Confirm or cancel a delete the assistant asked for.

    The cards to delete come from the stored request, never from this request's body.
    """
    board = _get_owned_board(request, board_id)
    get_object_or_404(AIChatMessage, pk=message_id, board=board, role='action')

    with transaction.atomic():
        pending = AIChatMessage.objects.select_for_update().get(pk=message_id)
        data = dict(pending.data or {})
        if data.get('type') != 'delete_request':
            return json_error('This action has nothing to confirm.')
        if data.get('status') != 'pending':
            return json_error(f"This request was already {data.get('status')}.", 409)

        deleted_ids = []
        if decision == 'confirm':
            cards = list(Card.objects.filter(id__in=data.get('card_ids', []), column__board=board))
            deleted_ids = [c.id for c in cards]
            titles = ", ".join(f'"{c.title}"' for c in cards)
            Card.objects.filter(id__in=deleted_ids).delete()

            gone = len(data.get('card_ids', [])) - len(deleted_ids)
            if deleted_ids:
                n = len(deleted_ids)
                content = f"Deleted {n} card{'' if n == 1 else 's'}: {titles}."
            else:
                content = "Nothing was deleted."
            if gone:
                content += f" {gone} had already been deleted."
            data['status'] = 'confirmed'
            result = {'type': 'delete_done', 'card_ids': deleted_ids}
        else:
            content = "Cancelled the request to delete cards; nothing was deleted."
            data['status'] = 'cancelled'
            result = {'type': 'delete_cancelled'}

        result['request_id'] = pending.id
        data['resolved_at'] = timezone.now().isoformat()
        pending.data = data
        pending.save(update_fields=['data'])
        note = AIChatMessage.objects.create(
            board=board, session=pending.session, role='action', content=content, data=result,
        )

    if pending.session_id:
        _touch(pending.session)

    return JsonResponse({
        'status':           'success',
        'deleted_card_ids': deleted_ids,
        'request':          _message_json(pending),
        'action':           _message_json(note),
    })
