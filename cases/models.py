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

    SUPPORT_TYPE_CHOICES = [
        ('ECC Support', 'ECC Support'),
        ('Internal', 'Internal'),
    ]

    # Form fields
    support_type = models.CharField(max_length=20, choices=SUPPORT_TYPE_CHOICES)
    account_name = models.CharField(max_length=100, choices=ACCOUNT_CHOICES)
    contact_name = models.CharField(max_length=100, choices=CONTACT_CHOICES)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
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
        # External ticketing
    SYNC_STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Pending', 'Pending'),
        ('Synced', 'Synced'),
        ('Failed', 'Failed'),
    ]

    SERVICENOW_STATUS_CHOICES = [
        ('Not requested', 'Not requested'),
        ('Created', 'Created'),
        ('Failed', 'Failed'),
    ]

    # Salesforce — always created on submit
    salesforce_case_number = models.CharField(max_length=50, blank=True)
    salesforce_case_url = models.URLField(blank=True)
    sync_status = models.CharField(
        max_length=10, choices=SYNC_STATUS_CHOICES, default='Draft'
    )
    sync_error = models.TextField(blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    # ServiceNow — optional additional incident
    servicenow_requested = models.BooleanField(default=False)
    servicenow_ticket_number = models.CharField(max_length=50, blank=True)
    servicenow_ticket_url = models.URLField(blank=True)
    servicenow_status = models.CharField(
        max_length=20, choices=SERVICENOW_STATUS_CHOICES, default='Not requested'
    )
    servicenow_error = models.TextField(blank=True)


    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Case #{self.pk} — {self.subject}"
    
    @property
    def is_draft(self):
        return self.sync_status == 'Draft'

    @property
    def is_synced(self):
        return self.sync_status == 'Synced'

    @property
    def stage(self):
        return 'Draft' if self.sync_status == 'Draft' else 'Submitted'


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