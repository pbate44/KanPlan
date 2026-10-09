"""Card changes shared by the board views and the board AI assistant."""

from django.db import transaction

from app.models import Card, CardLogEntry, Subtask, Swimlane, UserProfile
from app.views.helpers import MAX_CARDS_PER_BOARD

TITLE_MAX       = 100
DESCRIPTION_MAX = 16000


class CardError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.message = message
        self.code    = code


def card_field_error(title, description):
    """The validation message for a card's title and description, or None."""
    if not title:
        return "Title is required"
    if len(title) > TITLE_MAX:
        return f"Title must be {TITLE_MAX} characters or fewer"
    if not isinstance(description, str) or len(description) > DESCRIPTION_MAX:
        return "Description must be 16,000 characters or fewer"
    return None


def default_swimlane(board):
    return board.swimlanes.first() or Swimlane.objects.create(board=board, name="Default", position=0)


def create_card(user, column, swimlane=None, title="", description="", priority=0,
                color="", subtask_titles=()):
    """Create a card at the end of `column`. Raises CardError at the board's card limit."""
    board = column.board
    with transaction.atomic():
        # Serialises card creation per user so two requests can't both pass the limit check.
        UserProfile.objects.select_for_update().get(user=user)

        if Card.objects.filter(column__board=board).count() >= MAX_CARDS_PER_BOARD:
            raise CardError(f"A board can have up to {MAX_CARDS_PER_BOARD} cards.", code="limit_reached")

        create_kwargs = dict(
            column=column,
            swimlane=swimlane or default_swimlane(board),
            title=title,
            description=description,
            position=column.cards.count(),
            priority=priority,
        )
        if color:
            # Card.save() picks the matching css_class.
            create_kwargs['color'] = color

        card = Card.objects.create(**create_kwargs)
        Subtask.objects.bulk_create([Subtask(card=card, title=t) for t in subtask_titles])
    return card


def move_card(card, column, swimlane):
    """Move a card to the end of the cell at `column` and `swimlane`."""
    card.column   = column
    card.swimlane = swimlane
    card.position = column.cards.exclude(pk=card.pk).count()
    card.save(update_fields=['column', 'swimlane', 'position'])
    return card


def log_ai_change(card, text):
    """Record a change the board assistant made in the card's work log."""
    CardLogEntry.objects.create(card=card, source='ai', text=text)


def card_json(card):
    return {
        "id":          card.id,
        "title":       card.title,
        "description": card.description,
        "position":    card.position,
        "priority":    card.priority,
        "color":       card.color,
        "css_class":   card.css_class,
        "column_id":   card.column_id,
        "swimlane_id": card.swimlane_id,
    }
