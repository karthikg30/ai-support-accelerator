from django.contrib import admin

from .models import KnowledgeArticle


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'category', 'updated_at')
    list_filter = ('category',)
    search_fields = ('code', 'title', 'content')