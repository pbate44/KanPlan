
import json
import logging
import re
from urllib.parse import quote

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .helpers import json_error
from app.forms import CardLogEntryForm
from app.services import ai_service
from app.services.cards import CardError, card_field_error, card_json, create_card
from app.models import (
    Card,
    CardLogEntry,
    Column,
    Swimlane,
)

logger = logging.getLogger(__name__)

_VALID_COLOR_RE = re.compile(
    r'^(#[0-9a-fA-F]{3,6}|rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\))$'
)

@login_required
@require_POST
def add_card(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return json_error("Invalid JSON")

    column_id   = data.get('column_id')
    title       = data.get('title', '').strip()
    description = data.get('description', '')
    swimlane_id = data.get('swimlane_id')
    color       = data.get('color', '').strip()
    priority    = data.get('priority', 0)

    if not column_id or not title:
        return json_error("Column ID and title are required")

    field_error = card_field_error(title, description)
    if field_error:
        return json_error(field_error)

    if color and not _VALID_COLOR_RE.match(color):
        return json_error("Invalid color format.")

    try:
        priority = int(priority)
        if not (0 <= priority <= 10):
            raise ValueError
    except (TypeError, ValueError):
        return json_error("Priority must be between 0 and 10")

    column = get_object_or_404(Column, pk=column_id, board__owner=request.user)
    swimlane = get_object_or_404(Swimlane, pk=swimlane_id, board=column.board) if swimlane_id else None

    try:
        card = create_card(
            request.user, column, swimlane,
            title=title, description=description, priority=priority, color=color,
        )
    except CardError as e:
        return json_error(e.message, code=e.code)
    except Exception:
        logger.exception("Error creating card for user %s", request.user.pk)
        return json_error("An error occurred while creating the card.", 500)

    return JsonResponse({"status": "success", "card": card_json(card)})


@login_required
@require_http_methods(["GET", "POST"])
def card_detail(request, card_id):
    card = get_object_or_404(Card, pk=card_id, column__board__owner=request.user)
    log_entries = card.log_entries.order_by('-created_at')
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if request.method == 'POST':
        form = CardLogEntryForm(request.POST)

        if form.is_valid():
            entry = form.save(commit=False)
            entry.card = card
            entry.source = 'manual'
            entry.save()

            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'entry': {
                        'id': entry.id,
                        'text': entry.text,
                        'source': entry.get_source_display(),
                        'created_at': entry.created_at.strftime('%Y-%m-%d %H:%M'),
                    },
                })

    else:
        form = CardLogEntryForm()

    # Cards only open as a modal on their board, so send direct visits there.
    if not is_ajax:
        return redirect('board_detail', board_id=card.column.board_id)

    subtasks = card.subtasks.order_by('is_complete', 'created_at')
    profile    = request.user.profile
    ai_conn    = ai_service.connection_for(profile)
    ai_model_display = ai_service.model_display_name(profile.ai_model, ai_conn)

    return render(request, 'card_detail_content.html', {
        'card':                 card,
        'log_entries':          log_entries,
        'form':                 form,
        'subtasks':             subtasks,
        'ai_model_display':     ai_model_display,
        'ai_chat_always_open':  profile.ai_chat_always_open,
        'ai_web_search':        ai_service.is_openrouter(ai_conn),
    })



@login_required
@require_POST
def delete_card(request, card_id):
    card = get_object_or_404(Card, pk=card_id, column__board__owner=request.user)

    try:
        card.delete()
    except Exception:
        logger.exception("Error deleting card %s", card_id)
        return json_error("An error occurred while deleting the card.", 500)

    return JsonResponse({"status": "success"})


@login_required
@require_POST
def update_card_description(request, card_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return json_error("Invalid JSON")

    description = data.get('description', '')
    title = data.get('title', None)

    if title is not None:
        if not title.strip():
            return json_error("Title cannot be empty")
        if len(title) > 100:
            return json_error("Title must be 100 characters or fewer")

    if len(description) > 16000:
        return json_error("Description must be 16,000 characters or fewer")

    card = get_object_or_404(Card, pk=card_id, column__board__owner=request.user)

    try:
        update_fields = ['description']
        card.description = description

        if title is not None:
            card.title = title
            update_fields.append('title')

        card.save(update_fields=update_fields)

    except Exception:
        logger.exception("Error updating card %s", card_id)
        return json_error("An error occurred while updating the card.", 500)

    return JsonResponse({
        "status": "success",
        "description": card.description,
        "title": card.title,
    })


@login_required
@require_POST
def update_card_priority(request, card_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return json_error("Invalid JSON")

    priority = data.get('priority')

    if priority is None:
        return json_error("Priority value is required")

    try:
        if isinstance(priority, bool):
            raise ValueError
        priority = int(priority)
        if not (0 <= priority <= 10):
            raise ValueError
    except (TypeError, ValueError):
        return json_error("Priority must be between 0 and 10")

    card = get_object_or_404(Card, pk=card_id, column__board__owner=request.user)

    try:
        card.priority = priority
        card.save(update_fields=['priority'])
    except Exception:
        logger.exception("Error updating priority for card %s", card_id)
        return json_error("An error occurred while updating the card priority.", 500)

    return JsonResponse({"status": "success", "priority": card.priority})


@login_required
@require_POST
def update_card_color(request, card_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return json_error("Invalid JSON")

    color = data.get('color', '').strip()

    if not color:
        return json_error("Card color is required")

    if not _VALID_COLOR_RE.match(color):
        return json_error("Invalid color format.")

    css_class = Card.determine_css_class_from_color(color)

    card = get_object_or_404(Card, pk=card_id, column__board__owner=request.user)

    try:
        card.color = color
        card.css_class = css_class
        card.save(update_fields=['color', 'css_class'])
    except Exception:
        logger.exception("Error updating color for card %s", card_id)
        return json_error("An error occurred while updating the card color.", 500)

    return JsonResponse({
        "status": "success",
        "color": card.color,
        "css_class": card.css_class,
    })


@login_required
@require_POST
def delete_log_entry(request, entry_id):
    try:
        entry = CardLogEntry.objects.get(id=entry_id, card__column__board__owner=request.user)
        entry.delete()
    except CardLogEntry.DoesNotExist:
        return json_error('Log entry not found', 404)
    except Exception:
        logger.exception("Error deleting log entry %s", entry_id)
        return json_error('An error occurred while deleting the log entry.', 500)

    return JsonResponse({'status': 'success', 'message': 'Log entry deleted successfully'})


@login_required
@require_POST
def update_log_entry(request, entry_id):
    try:
        entry = CardLogEntry.objects.get(id=entry_id, card__column__board__owner=request.user)
    except CardLogEntry.DoesNotExist:
        return json_error('Log entry not found', 404)

    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
    except (json.JSONDecodeError, AttributeError):
        text = request.POST.get('text', '').strip()

    if not text:
        return json_error('Text cannot be empty')

    if len(text) > 100000:
        return json_error('Text must be 100,000 characters or fewer')

    entry.text = text
    entry.save(update_fields=['text'])
    return JsonResponse({'status': 'success', 'text': entry.text})


PDF_UNAVAILABLE_MESSAGE = (
    "PDF export is unavailable because WeasyPrint's system libraries are not installed. "
    "See https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation"
)


def _get_weasyprint():
    # WeasyPrint needs system libraries (Pango) that may not be installed.
    # Import lazily so the rest of the app still runs without them.
    try:
        import weasyprint
        return weasyprint
    except (ImportError, OSError):
        logger.warning("WeasyPrint unavailable; PDF export disabled", exc_info=True)
        return None


@login_required
def export_card_log_pdf(request, card_id):
    card = get_object_or_404(Card, id=card_id, column__board__owner=request.user)
    log_entries = card.log_entries.all().order_by('-created_at')
    html_string = render_to_string('pdf_template.html', {
        'card': card,
        'log_entries': log_entries,
        'now': timezone.now(),
    })
    weasyprint = _get_weasyprint()
    if weasyprint is None:
        return HttpResponse(PDF_UNAVAILABLE_MESSAGE, content_type='text/plain', status=503)
    filename = quote(f"{card.title}_log.pdf")
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f"attachment; filename*=UTF-8''{filename}"
    pdf_file = weasyprint.HTML(string=html_string).write_pdf()
    response.write(pdf_file)
    return response
