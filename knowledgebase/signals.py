"""Keep the vector index in step with article edits."""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import KnowledgeArticle

logger = logging.getLogger(__name__)


@receiver(post_save, sender=KnowledgeArticle)
def reindex_on_save(sender, instance, **kwargs):
    """Re-chunk and re-embed after an edit.

    Failures are logged, never raised — a broken index must not stop
    someone saving an article.
    """
    from chatbot.services import kb_index

    try:
        chunks = kb_index.index_article(instance)
        logger.info('Reindexed %s: %d chunks', instance.code, chunks)
    except Exception as exc:
        logger.error('Could not reindex %s: %s', instance.code, exc)


@receiver(post_delete, sender=KnowledgeArticle)
def remove_from_index(sender, instance, **kwargs):
    from chatbot.services import kb_index

    try:
        kb_index.get_collection().delete(where={'article_code': instance.code})
        logger.info('Removed %s from index', instance.code)
    except Exception as exc:
        logger.error('Could not remove %s from index: %s', instance.code, exc)