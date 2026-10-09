
from django.contrib import admin

from .models import (
    AIChatMessage,
    Board,
    Card,
    CardAttachment,
    CardLogEntry,
    Column,
    Subtask,
    Swimlane,
    UserProfile,
)


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display  = ['name', 'owner', 'created_at', 'updated_at']
    search_fields = ['name', 'owner__username', 'owner__email']
    list_filter   = ['created_at']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields   = ['owner']


@admin.register(Column)
class ColumnAdmin(admin.ModelAdmin):
    list_display  = ['name', 'board', 'position', 'color']
    search_fields = ['name', 'board__name', 'board__owner__username']
    list_filter   = ['board']
    raw_id_fields = ['board']


@admin.register(Swimlane)
class SwimlaneAdmin(admin.ModelAdmin):
    list_display  = ['name', 'board', 'position', 'height']
    search_fields = ['name', 'board__name', 'board__owner__username']
    raw_id_fields = ['board']


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display    = ['title', 'column', 'swimlane', 'priority', 'position', 'created_at']
    search_fields   = ['title', 'description', 'column__board__owner__username']
    list_filter     = ['priority', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields   = ['column', 'swimlane']


@admin.register(Subtask)
class SubtaskAdmin(admin.ModelAdmin):
    list_display  = ['title', 'card', 'is_complete', 'due_date', 'created_at']
    search_fields = ['title', 'card__title', 'card__column__board__owner__username']
    list_filter   = ['is_complete', 'due_date']
    raw_id_fields = ['card']


@admin.register(CardLogEntry)
class CardLogEntryAdmin(admin.ModelAdmin):
    list_display  = ['card', 'source', 'created_at']
    search_fields = ['card__title', 'text']
    list_filter   = ['source', 'created_at']
    readonly_fields = ['created_at']
    raw_id_fields = ['card']


@admin.register(CardAttachment)
class CardAttachmentAdmin(admin.ModelAdmin):
    list_display  = ['filename', 'card', 'file_type', 'file_size', 'upload_date']
    search_fields = ['filename', 'card__title']
    list_filter   = ['file_type', 'upload_date']
    readonly_fields = ['upload_date']
    raw_id_fields   = ['card']


@admin.register(AIChatMessage)
class AIChatMessageAdmin(admin.ModelAdmin):
    list_display  = ['card', 'board', 'role', 'created_at']
    search_fields = ['card__title', 'board__name', 'content']
    list_filter   = ['role', 'created_at']
    readonly_fields = ['created_at']
    raw_id_fields   = ['card', 'board', 'session']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display  = ['user', 'ai_model', 'theme']
    search_fields = ['user__username', 'user__email']
    raw_id_fields = ['user']
