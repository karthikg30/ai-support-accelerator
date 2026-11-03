from django.apps import AppConfig


class KnowledgebaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knowledgebase'

    def ready(self):
        from . import signals  # noqa: F401