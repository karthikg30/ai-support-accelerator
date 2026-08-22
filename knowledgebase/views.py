from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required

from .models import KnowledgeArticle


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

    categories = []
    for key, label in KnowledgeArticle.CATEGORY_CHOICES:
        meta = KnowledgeArticle.CATEGORY_META[key]
        categories.append({
            'key': key,
            'label': label,
            'icon': meta['icon'],
            'blurb': meta['blurb'],
            'count': counts.get(key, 0),
        })

    return render(request, 'knowledgebase/kb_home.html', {
        'categories': categories,
    })


@login_required
def kb_category(request, category):
    valid = dict(KnowledgeArticle.CATEGORY_CHOICES)
    if category not in valid:
        articles = KnowledgeArticle.objects.none()
        label = 'Unknown category'
        meta = {'icon': 'bi-file-text', 'blurb': ''}
    else:
        articles = KnowledgeArticle.objects.filter(category=category)
        label = valid[category]
        meta = KnowledgeArticle.CATEGORY_META[category]

    return render(request, 'knowledgebase/kb_category.html', {
        'articles': articles,
        'label': label,
        'icon': meta['icon'],
        'blurb': meta['blurb'],
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