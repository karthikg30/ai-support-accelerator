from django.contrib import admin

from .models import ChatHistory


@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'message', 'suggested_category',
                    'suggested_priority', 'source', 'engine', 'created_at')
    list_filter = ('source', 'engine', 'suggested_category')
    search_fields = ('message', 'response')
    readonly_fields = ('created_at',)