from django.http import JsonResponse




MAX_BOARDS_PER_USER     = 30
MAX_COLUMNS_PER_BOARD   = 7
MAX_SWIMLANES_PER_BOARD = 7
MAX_CARDS_PER_BOARD     = 200

def create_board_with_defaults(owner, name, description=""):
    """Create a board with the standard starter columns and a default swimlane."""
    from app.models import Board, Column, Swimlane

    board = Board.objects.create(name=name, description=description, owner=owner)
    Column.objects.bulk_create([
        Column(board=board, name="To Do", position=0),
        Column(board=board, name="In Progress", position=1),
        Column(board=board, name="Done", position=2),
    ])
    Swimlane.objects.create(board=board, name="Default", position=0, height=300)
    return board


def json_error(message, status=400, **extra):
    """The standard JSON error response: {"status": "error", "message": ...}."""
    return JsonResponse({"status": "error", "message": message, **extra}, status=status)
