
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.core.validators import MaxLengthValidator


class Board(models.Model):
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True, validators=[MaxLengthValidator(3000)])
    owner       = models.ForeignKey(User, related_name='boards', on_delete=models.CASCADE)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    image       = models.ImageField(
        upload_to='board_images/', blank=True, null=True,
        help_text='Board image (JPEG, PNG, GIF, WebP - Max 5MB)', max_length=255,
    )

    def __str__(self):
        return self.name


class Column(models.Model):
    board    = models.ForeignKey(Board, related_name='columns', on_delete=models.CASCADE)
    name     = models.CharField(max_length=50)
    position = models.PositiveIntegerField(default=0)
    color    = models.CharField(max_length=32, default="#f1f1f1")

    def __str__(self):
        return f"{self.name} ({self.board.name})"

    class Meta:
        ordering = ['position']


class Swimlane(models.Model):
    board    = models.ForeignKey(Board, related_name='swimlanes', on_delete=models.CASCADE)
    name     = models.CharField(max_length=100, default="New Swimlane")
    position = models.PositiveIntegerField(default=0)
    height   = models.PositiveIntegerField(default=300)

    def __str__(self):
        return f"{self.name} ({self.board.name})"

    class Meta:
        ordering = ['position']


class Card(models.Model):
    column      = models.ForeignKey(Column, related_name='cards', on_delete=models.CASCADE)
    swimlane    = models.ForeignKey(Swimlane, related_name='cards', on_delete=models.CASCADE, null=True, blank=True)
    title       = models.CharField(max_length=100)
    description = models.TextField(blank=True, validators=[MaxLengthValidator(16000)])
    position    = models.PositiveIntegerField(default=0)
    priority    = models.PositiveIntegerField(default=0, choices=[(i, i) for i in range(0, 11)])
    color       = models.CharField(max_length=20, default="#f1f1f1")
    css_class   = models.CharField(max_length=50, blank=True, null=True)
    created_at            = models.DateTimeField(auto_now_add=True)
    updated_at            = models.DateTimeField(auto_now=True)
    ai_context            = models.TextField(blank=True, default='')
    ai_context_updated_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            if not self.color or self.color == "#f1f1f1":
                self.color     = "rgb(240, 248, 255)"
                self.css_class = "card-color-default"
            elif not self.css_class:
                self.css_class = self.determine_css_class_from_color(self.color)
        super().save(*args, **kwargs)

    @classmethod
    def determine_css_class_from_color(cls, color):
        COLOR_CSS_MAP = {
            'rgb(240, 248, 255)': 'card-color-default',
            'rgb(241, 11, 11)':   'card-color-red',
            'rgb(247, 103, 7)':   'card-color-orange',
            'rgb(247, 243, 11)':  'card-color-yellow',
            'rgb(165, 231, 9)':   'card-color-light-green',
            'rgb(12, 133, 8)':    'card-color-dark-green',
            'rgb(13, 160, 111)':  'card-color-teal',
            'rgb(20, 197, 159)':  'card-color-cyan',
            'rgb(15, 41, 161)':   'card-color-blue',
            'rgb(118, 11, 240)':  'card-color-purple',
            'rgb(194, 8, 178)':   'card-color-magenta',
            'rgb(230, 20, 90)':   'card-color-pink',
            'rgb(2, 9, 15)':      'card-color-dark',
        }
        return COLOR_CSS_MAP.get(color, None)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['position']


class CardLogEntry(models.Model):
    LOG_SOURCES = (
        ('manual', 'Manual'),
        ('ai',     'AI Interaction'),
    )
    card       = models.ForeignKey(Card, related_name='log_entries', on_delete=models.CASCADE)
    text       = models.TextField(validators=[MaxLengthValidator(100000)])
    source     = models.CharField(max_length=20, choices=LOG_SOURCES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source} log for {self.card} at {self.created_at}"


class Subtask(models.Model):
    card        = models.ForeignKey(Card, related_name='subtasks', on_delete=models.CASCADE)
    title       = models.CharField(max_length=100)
    description = models.TextField(blank=True, validators=[MaxLengthValidator(10000)])
    is_complete = models.BooleanField(default=False)
    due_date    = models.DateField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


# A chat belongs to either a card (the card assistant) or a board (the board assistant).
_CARD_XOR_BOARD = models.Q(card__isnull=False, board__isnull=True) | models.Q(card__isnull=True, board__isnull=False)


class AIChatSession(models.Model):
    card       = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='chat_sessions', null=True, blank=True)
    board      = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='chat_sessions', null=True, blank=True)
    title      = models.CharField(max_length=255, default='New Chat')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.CheckConstraint(condition=_CARD_XOR_BOARD, name='chat_session_card_xor_board'),
        ]

    def __str__(self):
        if self.board_id:
            return f"Session {self.id} – Board {self.board_id}"
        return f"Session {self.id} – Card {self.card_id}"


class AIChatMessage(models.Model):
    ROLE_CHOICES = (
        ('system',    'System'),
        ('user',      'User'),
        ('assistant', 'Assistant'),
        # A change the board assistant made or asked to make; details are in `data`.
        ('action',    'Action'),
    )
    card       = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='chat_messages', null=True, blank=True)
    board      = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='chat_messages', null=True, blank=True)
    session    = models.ForeignKey(AIChatSession, on_delete=models.CASCADE, null=True, blank=True, related_name='messages')
    role       = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content    = models.TextField(validators=[MaxLengthValidator(100000)])
    data       = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        constraints = [
            models.CheckConstraint(condition=_CARD_XOR_BOARD, name='chat_message_card_xor_board'),
        ]

    def __str__(self):
        if self.board_id:
            return f"{self.role} message for Board {self.board_id}"
        return f"{self.role} message for Card {self.card_id}"


class CardAttachment(models.Model):
    card        = models.ForeignKey(Card, related_name='attachments', on_delete=models.CASCADE)
    file        = models.FileField(upload_to='card_attachments/', max_length=255)
    filename    = models.CharField(max_length=255)
    file_type   = models.CharField(max_length=127)
    file_size   = models.IntegerField()
    upload_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filename} ({self.card.title})"

    # Exact MIME types, since substring checks misfire (the .xlsx type contains "document").
    KIND_BY_MIME = {
        'application/pdf': 'pdf',
        'application/msword': 'doc',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
        'application/vnd.ms-excel': 'spreadsheet',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'spreadsheet',
        'text/csv': 'csv',
        'application/csv': 'csv',
        'text/plain': 'text',
        'application/rtf': 'rtf',
        'text/rtf': 'rtf',
        'text/richtext': 'rtf',
        'image/png': 'image',
        'image/jpeg': 'image',
        'image/gif': 'image',
        'image/webp': 'image',
    }
    ICON_BY_KIND = {
        'pdf':         'bi-file-pdf',
        'doc':         'bi-file-word',
        'docx':        'bi-file-word',
        'spreadsheet': 'bi-file-excel',
        'csv':         'bi-file-excel',
        'text':        'bi-file-text',
        'rtf':         'bi-file-text',
        'image':       'bi-file-image',
    }

    @property
    def kind(self):
        return self.KIND_BY_MIME.get(self.file_type.lower().split(';')[0].strip(), 'other')

    def get_icon_class(self):
        return self.ICON_BY_KIND.get(self.kind, 'bi-file')


class UserProfile(models.Model):
    user                    = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    timezone                = models.CharField(max_length=64, default="UTC")
    ai_chat_always_open     = models.BooleanField(default=False)

    ai_model = models.CharField(max_length=150, blank=True, null=True)

    # AI connection chosen in Settings; blank provider = the server's .env config.
    AI_PROVIDER_CHOICES = [
        ('',           'Server default'),
        ('ollama',     'Ollama'),
        ('lmstudio',   'LM Studio'),
        ('openrouter', 'OpenRouter'),
        ('custom',     'Other'),
    ]
    ai_provider = models.CharField(max_length=20, choices=AI_PROVIDER_CHOICES, blank=True, default='')
    ai_base_url = models.CharField(max_length=200, blank=True, default='')
    ai_api_key  = models.CharField(max_length=300, blank=True, default='')

    THEME_CHOICES = [
        ('light',  'Light'),
        ('dark',   'Dark'),
        ('system', 'System Default'),
    ]
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='system')

    def __str__(self):
        return f"{self.user.username}'s Profile"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
