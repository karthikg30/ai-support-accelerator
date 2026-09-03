from django.contrib import admin

from .models import ChatHistory
from .models import PHIBlockEvent
from .models import Conversation

@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'message', 'suggested_category',
                    'suggested_priority', 'source', 'engine', 'created_at')
    list_filter = ('source', 'engine', 'suggested_category')
    search_fields = ('message', 'response')
    readonly_fields = ('created_at',)

@admin.register(PHIBlockEvent)
class PHIBlockEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'source', 'detected_types', 'created_at')
    list_filter = ('source',)
    readonly_fields = ('user', 'source', 'detected_types', 'created_at')

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'display_title', 'user', 'created_at', 'updated_at')
    list_filter = ('user',)