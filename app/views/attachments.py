
import logging
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from app.models import Card, CardAttachment

from .helpers import json_error

logger = logging.getLogger(__name__)


ALLOWED_ATTACHMENT_TYPES = {
    '.pdf':  {'application/pdf'},
    '.doc':  {'application/msword'},
    '.docx': {'application/vnd.openxmlformats-officedocument.wordprocessingml.document'},
    '.xls':  {'application/vnd.ms-excel'},
    '.xlsx': {'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'},
    '.csv':  {'text/csv', 'text/plain', 'application/csv'},
    '.txt':  {'text/plain'},
    '.rtf':  {'application/rtf', 'text/rtf', 'text/richtext'},
    '.png':  {'image/png'},
    '.jpg':  {'image/jpeg'},
    '.jpeg': {'image/jpeg'},
    '.gif':  {'image/gif'},
    '.webp': {'image/webp'},
}
ALLOWED_ATTACHMENT_MIMES = set().union(*ALLOWED_ATTACHMENT_TYPES.values())


@login_required
@require_POST
def upload_attachment(request, card_id):
    card = get_object_or_404(Card, pk=card_id, column__board__owner=request.user)

    try:
        
        if 'file' not in request.FILES:
            return json_error('No file was provided')
        
        uploaded_file = request.FILES['file']
        
        if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
            return json_error('File size exceeds the limit')

        ext = os.path.splitext(uploaded_file.name)[1].lower()
        declared_mime = uploaded_file.content_type.lower().split(';')[0].strip()
        allowed_mimes = ALLOWED_ATTACHMENT_TYPES.get(ext)
        if not allowed_mimes or declared_mime not in allowed_mimes:
            return json_error('File type not allowed')

        file_type = declared_mime
        
        attachment = CardAttachment.objects.create(
            card=card,
            file=uploaded_file,
            filename=uploaded_file.name,
            file_type=file_type,
            file_size=uploaded_file.size
        )
        
        return JsonResponse({
            'status': 'success',
            'attachment_id': attachment.id,
            'filename': attachment.filename,
            'file_type': attachment.file_type,
            'file_size': attachment.file_size,
            'icon_class': attachment.get_icon_class(),
            'upload_date': attachment.upload_date.strftime('%Y-%m-%d %H:%M')
        })
        
    except Exception:
        logger.exception("Attachment upload failed")
        return json_error('An unexpected error occurred', 500)


@login_required
@require_GET
def get_attachments(request, card_id):
    card = get_object_or_404(Card, pk=card_id, column__board__owner=request.user)

    try:
        attachments = card.attachments.all()
        
        return JsonResponse({
            'status': 'success',
            'attachments': [
                {
                    'id': attachment.id,
                    'filename': attachment.filename,
                    'file_type': attachment.file_type,
                    'file_size': attachment.file_size,
                    'icon_class': attachment.get_icon_class(),
                    'upload_date': attachment.upload_date.strftime('%Y-%m-%d %H:%M')
                }
                for attachment in attachments
            ]
        })
        
    except Exception:
        logger.exception("Get attachments failed")
        return json_error('An unexpected error occurred', 500)


@login_required
@require_GET
def view_attachment(request, attachment_id):
    attachment = get_object_or_404(CardAttachment, pk=attachment_id, card__column__board__owner=request.user)

    # Served here rather than from /media/ so only the owner can read it.
    # Allowed types open in the browser; anything else (e.g. files uploaded
    # before the type checks existed) is downloaded instead.
    inline = attachment.file_type in ALLOWED_ATTACHMENT_MIMES
    try:
        return FileResponse(
            attachment.file.open('rb'),
            as_attachment=not inline,
            filename=attachment.filename,
            content_type=attachment.file_type if inline else 'application/octet-stream',
        )
    except FileNotFoundError:
        raise Http404("Attachment file not found")
    except Exception:
        logger.exception("View attachment failed")
        return json_error('An unexpected error occurred', 500)


@login_required
@require_POST
def delete_attachment(request, attachment_id):
    attachment = get_object_or_404(CardAttachment, pk=attachment_id, card__column__board__owner=request.user)

    try:
        attachment.file.delete(save=False)
        attachment.delete()
        return JsonResponse({'status': 'success'})
    except Exception:
        logger.exception("Delete attachment failed")
        return json_error('An unexpected error occurred', 500)
