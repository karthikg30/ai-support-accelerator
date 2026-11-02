from django.db import models


class KnowledgeArticle(models.Model):
    CATEGORY_CHOICES = [
        ('onboarding', 'Onboarding Documentation'),
        ('user_management', 'User Management'),
        ('product', 'Product Articles'),
    ]

    CATEGORY_META = {
        'onboarding': {
            'icon': 'bi-box-arrow-in-right',
            'blurb': 'Access requests, environment setup, and policy for new agents.',
        },
        'user_management': {
            'icon': 'bi-person-gear',
            'blurb': 'Login problems, password resets, and permission provisioning.',
        },
        'product': {
            'icon': 'bi-hospital',
            'blurb': 'Product overviews and healthcare domain reference.',
        },
    }

    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    product_code = models.CharField(max_length=20, blank=True)
    related_tickets = models.JSONField(default=list, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} — {self.title}"

    @property
    def icon(self):
        return self.CATEGORY_META.get(self.category, {}).get('icon', 'bi-file-text')