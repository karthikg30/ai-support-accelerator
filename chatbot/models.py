from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models

class Conversation(models.Model):
    """A single chat thread between an agent and the assistant."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations',
    )
    title = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f"Conversation {self.pk}"

    def display_title(self):
        if self.title:
            return self.title
        first = self.messages.order_by('created_at').first()
        if first:
            return first.message[:60]
        return 'New conversation'

    def set_title_from(self, message):
        """Title the thread from its first message."""
        if not self.title and message:
            self.title = message[:120]
            self.save(update_fields=['title', 'updated_at'])

class ChatHistory(models.Model):
    """One question/answer exchange with the AI assistant."""

    SOURCE_CHOICES = [
        ('panel', 'Create Case panel'),
        ('page', 'AI Assistant page'),
        ('assistant', 'Assistant landing page'),
        ('rephrase', 'Description rephrase'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_history',
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        null=True,
        blank=True,
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

class PHIBlockEvent(models.Model):
    """Records that a PHI guardrail fired. Deliberately stores no content."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='phi_blocks',
    )
    source = models.CharField(max_length=20)
    detected_types = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.source} — {self.detected_types}"