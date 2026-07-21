from django.contrib import admin

from .models import Attachment, Case


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'account_name', 'priority', 'status', 'created_by', 'created_at')
    list_filter = ('priority', 'status', 'account_name')
    search_fields = ('subject', 'description')
    inlines = [AttachmentInline]


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'case', 'file', 'uploaded_at')