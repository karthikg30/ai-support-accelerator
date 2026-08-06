from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models


class ChatHistory(models.Model):
    """One question/answer exchange with the AI assistant."""

    SOURCE_CHOICES = [
        ('panel', 'Create Case panel'),
        ('page', 'AI Assistant page'),
        ('rephrase', 'Description rephrase'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_history',
    )
    message = models.TextField()
    response = models.TextField()
    suggested_category = models.CharField(max_length=100, blank=True)
    suggested_priority = models.CharField(max_length=20, blank=True)
    suggested_request_type = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='panel')
    engine = models.CharField(max_length=20, default='mock')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Chat history'

    def __str__(self):
        return f"{self.user.username}: {self.message[:50]}"

