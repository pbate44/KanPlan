
import json
import logging

from PIL import Image as PilImage

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from .helpers import (
    MAX_BOARDS_PER_USER,
    MAX_CARDS_PER_BOARD,
    MAX_COLUMNS_PER_BOARD,
    MAX_SWIMLANES_PER_BOARD,
    create_board_with_defaults,
    json_error,
)
from app.models import Board, Card, Swimlane, UserProfile
from app.services import ai_service

logger = logging.getLogger(__name__)

MAX_BOARD_IMAGE_SIZE = 5 * 1024 * 1024


def _validate_image_file(file):
    allowed_formats = {"JPEG", "PNG", "GIF", "WEBP"}
    try:
        img = PilImage.open(file)
        fmt = img.format
        img.load()
    except Exception:
        return False, "File is not a valid image."
    finally:
        file.seek(0)

    if fmt not in allowed_formats:
        return False, "Invalid image type. Please upload a JPEG, PNG, GIF, or WebP image."
    return True, None


def _board_json(board):
    return {
        "id":          board.id,
        "name":        board.name,
        "description": board.description,
        "image_url":   board.image.url if board.image else None,
        "created_at":  board.created_at.isoformat(),
        "updated_at":  board.updated_at.isoformat(),
    }


@login_required
def board_detail(request, board_id):
    board = get_object_or_404(Board, pk=board_id, owner=request.user)
    columns = list(
        board.columns.all()
        .prefetch_related(Prefetch("cards", queryset=Card.objects.order_by("position")))
    )

    swimlanes = board.swimlanes.all()
    card_count = sum(len(col.cards.all()) for col in columns)

    user_boards = Board.objects.filter(owner=request.user).only("id", "name").order_by("name")

    profile = request.user.profile
    ai_conn = ai_service.connection_for(profile)

    return render(request, "board_detail.html", {
        "board": board,
        "columns": columns,
        "swimlanes": swimlanes,
        "max_swimlanes": MAX_SWIMLANES_PER_BOARD,
        "max_columns": MAX_COLUMNS_PER_BOARD,
        "max_cards": MAX_CARDS_PER_BOARD,
        "card_count": card_count,
        "user_boards": user_boards,
        "ai_model_display": ai_service.model_display_name(profile.ai_model, ai_conn),
        "ai_web_search": ai_service.is_openrouter(ai_conn),
    })


@login_required
@require_POST
def create_board(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return json_error("Invalid JSON")

    name = data.get("name", "").strip()
    description = data.get("description", "").strip()

    if not name:
        return json_error("Board name is required")

    if len(name) > 100:
        return json_error("Board name must be 100 characters or fewer")

    if len(description) > 3000:
        return json_error("Board description must be 3,000 characters or fewer")

    try:
        with transaction.atomic():
            UserProfile.objects.select_for_update().get(user=request.user)
            current_board_count = Board.objects.filter(owner=request.user).count()

            if current_board_count >= MAX_BOARDS_PER_USER:
                return json_error(
                    f"You can have up to {MAX_BOARDS_PER_USER} boards.", code="limit_reached",
                )

            board = create_board_with_defaults(request.user, name, description)

    except Exception:
        logger.exception("Error creating board for user %s", request.user.pk)
        return json_error("An error occurred while creating the board.", 500)

    return JsonResponse({"status": "success", "board": _board_json(board)})


@login_required
@require_POST
def update_board(request, board_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return json_error("Invalid JSON")

    name = data.get("name", "").strip()
    description = data.get("description", "").strip()

    if not name:
        return json_error("Board name is required")

    if len(name) > 100:
        return json_error("Board name must be 100 characters or fewer")

    if len(description) > 3000:
        return json_error("Board description must be 3,000 characters or fewer")

    board = get_object_or_404(Board, pk=board_id, owner=request.user)

    try:
        board.name = name
        board.description = description
        board.save()
    except Exception:
        logger.exception("Error updating board %s for user %s", board_id, request.user.pk)
        return json_error("An error occurred while updating the board.", 500)

    return JsonResponse({"status": "success", "board": _board_json(board)})


@login_required
@require_POST
def delete_board(request, board_id):
    board = get_object_or_404(Board, pk=board_id, owner=request.user)

    try:
        user_board_count = Board.objects.filter(owner=request.user).count()
        if user_board_count <= 1:
            return json_error("Cannot delete your last board. Create another board first.")

        board_name = board.name
        board.delete()
    except Exception:
        logger.exception("Error deleting board %s for user %s", board_id, request.user.pk)
        return json_error("An error occurred while deleting the board.", 500)

    return JsonResponse({
        "status": "success",
        "message": f'Board "{board_name}" deleted successfully',
    })


@login_required
@require_POST
def upload_board_image(request, board_id):
    board = get_object_or_404(Board, pk=board_id, owner=request.user)

    try:
        if "image" not in request.FILES:
            return json_error("No image file provided")

        uploaded_file = request.FILES["image"]

        if uploaded_file.size > MAX_BOARD_IMAGE_SIZE:
            return json_error("File size too large. Maximum size is 5MB.")

        valid, error_msg = _validate_image_file(uploaded_file)
        if not valid:
            return json_error(error_msg)

        if board.image:
            board.image.delete(save=False)

        board.image = uploaded_file
        board.save()

    except Exception:
        logger.exception("Error uploading image for board %s", board_id)
        return json_error("An error occurred while uploading the image.", 500)

    return JsonResponse({
        "status": "success",
        "image_url": board.image.url,
        "message": "Image uploaded successfully",
    })


@login_required
@require_POST
def remove_board_image(request, board_id):
    board = get_object_or_404(Board, pk=board_id, owner=request.user)

    try:
        if not board.image:
            return json_error("No image to remove")

        board.image.delete(save=False)
        board.image = None
        board.save()

    except Exception:
        logger.exception("Error removing image for board %s", board_id)
        return json_error("An error occurred while removing the image.", 500)

    return JsonResponse({"status": "success", "message": "Image removed successfully"})


@login_required
@require_GET
def get_board_details(request, board_id):
    board = get_object_or_404(Board, pk=board_id, owner=request.user)
    return JsonResponse({"status": "success", "board": _board_json(board)})



@login_required
@require_POST
def update_board_title(request, board_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return json_error("Invalid JSON")

    title = data.get("title", "").strip()

    if not title:
        return json_error("Title is required")

    if len(title) > 100:
        return json_error("Title must be 100 characters or fewer")

    board = get_object_or_404(Board, pk=board_id, owner=request.user)

    try:
        board.name = title
        board.save()
    except Exception:
        logger.exception("Error updating title for board %s", board_id)
        return json_error("An error occurred while updating the board title", 500)

    return JsonResponse({"status": "success", "title": board.name})
