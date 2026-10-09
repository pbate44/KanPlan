
import json
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .helpers import MAX_COLUMNS_PER_BOARD, json_error
from app.models import Board, Card, Column, Swimlane, UserProfile

logger = logging.getLogger(__name__)


@login_required
@require_POST
def add_column(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return json_error("Invalid JSON")

    board_id = data.get('board_id')
    name = data.get('name', '').strip()

    if not board_id or not name:
        return json_error("Board ID and name are required")

    if len(name) > 50:
        return json_error("Column name must be 50 characters or fewer")

    board = get_object_or_404(Board, pk=board_id, owner=request.user)

    try:
        with transaction.atomic():
            UserProfile.objects.select_for_update().get(user=request.user)

            current_column_count = board.columns.count()

            if current_column_count >= MAX_COLUMNS_PER_BOARD:
                return json_error(
                    f"A board can have up to {MAX_COLUMNS_PER_BOARD} columns.", code="limit_reached",
                )

            column = Column.objects.create(
                board=board,
                name=name,
                position=current_column_count,
            )
    except Exception:
        logger.exception("Error creating column on board %s for user %s", board_id, request.user.pk)
        return json_error("An error occurred while creating the column.", 500)

    return JsonResponse({
        "status": "success",
        "column": {
            "id":       column.id,
            "name":     column.name,
            "position": column.position,
            "board_id": column.board_id,
        },
    })


@login_required
@require_POST
def update_column_name(request, column_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return json_error("Invalid JSON")

    name = data.get('name', '').strip()

    if not name:
        return json_error("Column name is required")

    if len(name) > 50:
        return json_error("Column name must be 50 characters or fewer")

    column = get_object_or_404(Column, pk=column_id, board__owner=request.user)

    try:
        column.name = name
        column.save(update_fields=['name'])
    except Exception:
        logger.exception("Error updating column %s", column_id)
        return json_error("An error occurred while updating the column name", 500)

    return JsonResponse({"status": "success", "name": column.name})


@login_required
@require_POST
def delete_column(request, column_id):
    column = get_object_or_404(Column, pk=column_id, board__owner=request.user)

    if Column.objects.filter(board_id=column.board_id).count() <= 1:
        return json_error("Cannot delete the last column on a board")

    try:
        column.delete()
    except Exception:
        logger.exception("Error deleting column %s", column_id)
        return json_error("An error occurred while deleting the column.", 500)

    return JsonResponse({"status": "success", "message": "Column deleted successfully"})


@login_required
@require_POST
def save_column_sort_order(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return json_error("Invalid JSON")

    column_id   = data.get('column_id')
    card_orders = data.get('card_orders')

    if not column_id or card_orders is None:
        return json_error("Column ID and card orders are required")

    try:
        card_ids = [int(cid) for cid in card_orders]
    except (ValueError, TypeError):
        return json_error("card_orders must be a list of integer card IDs")

    column = get_object_or_404(Column, pk=column_id, board__owner=request.user)

    try:
        Card.objects.filter(id__in=card_ids, column=column).update(
            position=Case(
                *[When(id=cid, then=Value(i)) for i, cid in enumerate(card_ids)],
                output_field=IntegerField(),
            )
        )
    except Exception:
        logger.exception("Error saving sort order for column %s", column_id)
        return json_error("An error occurred while saving the sort order.", 500)

    return JsonResponse({
        "status": "success",
        "message": f"Updated positions for {len(card_ids)} cards",
    })


@login_required
@require_POST
def update_card_position_manual(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return json_error("Invalid JSON")

    card_id         = data.get('card_id')
    new_pos         = data.get('position')
    new_col_id      = data.get('column')
    new_swimlane_id = data.get('swimlane_id')

    if card_id is None or new_pos is None or new_col_id is None:
        return json_error("Missing required parameters")

    try:
        new_pos         = int(new_pos)
        new_col_id      = int(new_col_id)
        new_swimlane_id = int(new_swimlane_id) if new_swimlane_id not in (None, '') else None
    except (TypeError, ValueError):
        return json_error("Position, column and swimlane must be integers")

    card = get_object_or_404(
        Card.objects.select_related('column'),
        pk=card_id,
        column__board__owner=request.user,
    )
    board = card.column.board
    card.column   = get_object_or_404(Column, pk=new_col_id, board=board)
    card.position = new_pos
    update_fields = ['column', 'position']

    if new_swimlane_id is not None:
        card.swimlane = get_object_or_404(Swimlane, pk=new_swimlane_id, board=board)
        update_fields.append('swimlane')

    try:
        card.save(update_fields=update_fields)
    except Exception:
        logger.exception("Error updating card position for card %s", card_id)
        return json_error("An error occurred while updating the card position", 500)

    return JsonResponse({
        "status": "success",
        "card": {
            "id":       card.id,
            "column":   card.column_id,
            "position": card.position,
            "title":    card.title,
        },
        "cleared_sorting": True,
    })
