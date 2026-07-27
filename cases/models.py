from django.conf import settings
from django.db import models


class Case(models.Model):
    """A support case created by an agent."""

    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical'),
    ]

    REPLY_VIA_CHOICES = [
        ('Email', 'Email'),
        ('Phone', 'Phone'),
        ('Case', 'Case'),
    ]

    STATUS_CHOICES = [
        ('New', 'New'),
        ('In Progress', 'In Progress'),
        ('Escalated', 'Escalated'),
        ('Resolved', 'Resolved'),
        ('Closed', 'Closed'),
    ]

    ACCOUNT_CHOICES = [
        ('Sunrise Health Group', 'Sunrise Health Group'),
        ('Lakeside Medical Center', 'Lakeside Medical Center'),
        ('Fairview Clinics', 'Fairview Clinics'),
        ('Summit Care Partners', 'Summit Care Partners'),
    ]

    CONTACT_CHOICES = [
        ('John Miller', 'John Miller'),
        ('Priya Sharma', 'Priya Sharma'),
        ('Emily Chen', 'Emily Chen'),
        ('David Thompson', 'David Thompson'),
    ]

    # Form fields
    account_name = models.CharField(max_length=100, choices=ACCOUNT_CHOICES)
    contact_name = models.CharField(max_length=100, choices=CONTACT_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Medium')
    reply_via = models.CharField(max_length=10, choices=REPLY_VIA_CHOICES, default='Email')
    subject = models.CharField(max_length=200)
    description = models.TextField(max_length=4000)
    product_request_type = models.CharField(max_length=100, blank=True)
    product_category = models.CharField(max_length=100, blank=True)
    includes_phi = models.BooleanField(default=False)

    # System fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='New')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='cases',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Salesforce sync
    SYNC_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Synced', 'Synced'),
        ('Failed', 'Failed'),
    ]

    salesforce_case_number = models.CharField(max_length=50, blank=True)
    salesforce_case_url = models.URLField(blank=True)
    sync_status = models.CharField(
        max_length=10, choices=SYNC_STATUS_CHOICES, default='Pending'
    )
    sync_error = models.TextField(blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)


    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Case #{self.pk} — {self.subject}"
    
    @property
    def is_synced(self):
        return self.sync_status == 'Synced'


class Attachment(models.Model):
    """A file attached to a case."""

    case = models.ForeignKey(
        Case,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(upload_to='case_attachments/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for Case #{self.case_id}"