from django.db import models

CATEGORY_ABBREV = {
    'onboarding': 'ONB',
    'user_management': 'UM',
    'product': 'PRD',
}


def product_choices():
    """Built from the registry so the dropdown can never drift from it."""
    from chatbot.services.product_registry import PRODUCT_REGISTRY

    return [('', '— none —')] + [
        (code, f'{code} — {data["name"]}')
        for code, data in sorted(PRODUCT_REGISTRY.items())
    ]


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

    code = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
        help_text='Generated automatically from product and category.',
    )
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    product_code = models.CharField(
        max_length=20,
        blank=True,
        choices=product_choices,
        help_text='Which product this article covers. Leave blank for general articles.',
    )
    summary = models.CharField(max_length=300, blank=True)
    content = models.TextField(
        help_text=(
            'Use section headings so the article chunks well for AI retrieval. '
            'Write each heading on its own line ending with a colon, for example '
            '"Symptom:", "Cause:", "Resolution:". Steps may also be written as '
            '"Step 1 - Do the thing". Without headings the article is split by '
            'paragraph, which retrieves less precisely.'
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        super().save(*args, **kwargs)

    def _generate_code(self):
        """Build a code like CCC-UM-001 from product and category.

        Authors never type this. Once set it is never changed, because
        chips and chat history reference it.
        """
        from chatbot.services.product_registry import canonical_code

        product = canonical_code(self.product_code) or 'GEN'
        category = CATEGORY_ABBREV.get(self.category, 'GEN')
        prefix = f'{product}-{category}-'

        highest = 0
        for existing in KnowledgeArticle.objects.filter(code__startswith=prefix):
            try:
                highest = max(highest, int(existing.code.rsplit('-', 1)[-1]))
            except (ValueError, IndexError):
                continue

        return f'{prefix}{highest + 1:03d}'

    def __str__(self):
        return f'{self.code} - {self.title}'

    @property
    def icon(self):
        return self.CATEGORY_META.get(self.category, {}).get('icon', 'bi-file-text')


class RelatedTicket(models.Model):
    """A past ticket linked from an article. Shown as a chip in AI responses."""

    article = models.ForeignKey(
        KnowledgeArticle,
        on_delete=models.CASCADE,
        related_name='tickets',
    )
    number = models.CharField(max_length=50)
    url = models.URLField()
    label = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.number} ({self.article.code})'