from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from chatbot.services.product_registry import (
    PRODUCT_REGISTRY,
    canonical_code,
    get_product,
)

from .models import KBCategory, KBProduct, KnowledgeArticle


def _categories():
    """Active categories as {key: {label, icon, blurb}}, in admin order.

    Falls back to the built-in list if the KBCategory table is empty.
    """
    if not KBCategory.objects.exists():
        return {
            key: {
                'label': label,
                'icon': KnowledgeArticle.CATEGORY_META[key]['icon'],
                'blurb': KnowledgeArticle.CATEGORY_META[key]['blurb'],
            }
            for key, label in KnowledgeArticle.CATEGORY_CHOICES
        }
    return {
        row.key: {'label': row.label, 'icon': row.icon, 'blurb': row.blurb}
        for row in KBCategory.objects.filter(active=True)
    }


def _active_products():
    """Registry entries for active products, as {code: {name, aliases}}."""
    registry = dict(PRODUCT_REGISTRY.items())
    if not KBProduct.objects.exists():
        return registry
    inactive = set(
        KBProduct.objects.filter(active=False).values_list('code', flat=True)
    )
    return {c: d for c, d in registry.items() if c not in inactive}


@login_required
def kb_home(request):
    query = request.GET.get('q', '').strip()

    if query:
        results = KnowledgeArticle.objects.filter(
            Q(title__icontains=query)
            | Q(content__icontains=query)
            | Q(summary__icontains=query)
            | Q(code__icontains=query)
        )
        return render(request, 'knowledgebase/kb_search.html', {
            'query': query,
            'results': results,
        })

    counts = dict(
        KnowledgeArticle.objects.values_list('category')
        .annotate(n=Count('id'))
    )

    categories = [
        {
            'key': key,
            'label': meta['label'],
            'icon': meta['icon'],
            'blurb': meta['blurb'],
            'count': counts.get(key, 0),
        }
        for key, meta in _categories().items()
    ]

    return render(request, 'knowledgebase/kb_home.html', {
        'categories': categories,
    })


@login_required
def kb_category(request, category):
    """Level 2: product tiles within a category."""
    valid = _categories()

    if category not in valid:
        raise Http404('Unknown category')

    # Count articles per product, normalising stored codes so a row saved
    # as 'occ' still lands on the 'OCC' tile.
    counts = {}
    rows = (
        KnowledgeArticle.objects.filter(category=category)
        .values_list('product_code')
        .annotate(n=Count('id'))
    )
    for stored_code, n in rows:
        key = canonical_code(stored_code)
        if key:
            counts[key] = counts.get(key, 0) + n

    products = [
        {
            'code': code,
            'name': data['name'],
            'count': counts.get(code, 0),
        }
        for code, data in sorted(_active_products().items())
    ]

    meta = valid[category]

    return render(request, 'knowledgebase/kb_category.html', {
        'category': category,
        'label': meta['label'],
        'icon': meta['icon'],
        'blurb': meta['blurb'],
        'products': products,
        'total': sum(counts.values()),
    })


@login_required
def kb_product(request, category, product_code):
    """Level 3: articles for one product within a category."""
    valid = _categories()
    code = canonical_code(product_code)

    if category not in valid:
        raise Http404('Unknown category')
    if not code or code not in _active_products():
        raise Http404('Unknown product')

    articles = KnowledgeArticle.objects.filter(
        category=category,
        product_code__iexact=code,
    ).order_by('code')

    meta = valid[category]
    product = get_product(code)

    return render(request, 'knowledgebase/kb_product.html', {
        'category': category,
        'category_label': meta['label'],
        'icon': meta['icon'],
        'product_code': code,
        'product_name': product['name'],
        'articles': articles,
    })


@login_required
def kb_article(request, code):
    article = get_object_or_404(KnowledgeArticle, code__iexact=code)
    related = KnowledgeArticle.objects.filter(
        category=article.category
    ).exclude(pk=article.pk)[:4]

    return render(request, 'knowledgebase/kb_article.html', {
        'article': article,
        'related': related,
    })