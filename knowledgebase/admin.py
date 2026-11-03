from django.contrib import admin

from .models import KnowledgeArticle, RelatedTicket


class RelatedTicketInline(admin.TabularInline):
    model = RelatedTicket
    extra = 1
    fields = ('number', 'url', 'label')


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'category', 'product_code', 'updated_at')
    list_filter = ('category', 'product_code')
    search_fields = ('code', 'title', 'content')
    inlines = [RelatedTicketInline]
    actions = ['reindex_selected']

    def get_fieldsets(self, request, obj=None):
        classification = ('Classification', {
            'fields': ('category', 'product_code'),
            'description': (
                'Category and product decide where this article appears, '
                'and are used to filter AI retrieval.'
            ),
        })
        content = ('Content', {'fields': ('content',)})

        if obj is None:
            return (
                (None, {
                    'fields': ('title', 'summary'),
                    'description': 'The article code is generated on save.',
                }),
                classification,
                content,
            )

        return (
            (None, {'fields': ('code', 'title', 'summary')}),
            classification,
            content,
        )

    def get_readonly_fields(self, request, obj=None):
        return ('code',) if obj else ()

    @admin.action(description='Rebuild search index for selected articles')
    def reindex_selected(self, request, queryset):
        from chatbot.services import kb_index

        total = 0
        for article in queryset:
            total += kb_index.index_article(article)

        self.message_user(
            request,
            f'Reindexed {queryset.count()} articles, {total} chunks.',
        )


@admin.register(RelatedTicket)
class RelatedTicketAdmin(admin.ModelAdmin):
    list_display = ('number', 'article', 'label')
    search_fields = ('number', 'label')