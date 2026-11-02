from django.core.management.base import BaseCommand

from chatbot.services import kb_index
from knowledgebase.models import KnowledgeArticle


class Command(BaseCommand):
    help = 'Build the knowledge base vector index from KnowledgeArticle rows.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--code',
            help='Index only this article code, e.g. KB1016',
        )
        parser.add_argument(
            '--rebuild',
            action='store_true',
            help='Clear the whole index before building',
        )

    def handle(self, *args, **options):
        if options['rebuild']:
            kb_index.clear_index()
            self.stdout.write('Index cleared.')

        queryset = KnowledgeArticle.objects.all()
        if options['code']:
            queryset = queryset.filter(code__iexact=options['code'])

        if not queryset.exists():
            self.stdout.write(self.style.WARNING('No articles matched.'))
            return

        total_chunks = 0
        for article in queryset:
            chunks = kb_index.index_article(article)
            total_chunks += chunks
            self.stdout.write(f'  {article.code}: {chunks} chunks')

        self.stdout.write(self.style.SUCCESS(
            f'Indexed {queryset.count()} articles, {total_chunks} chunks.'
        ))