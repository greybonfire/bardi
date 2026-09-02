from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "knowledge"
    verbose_name = "Knowledge catalog"

    def ready(self) -> None:
        from .aggregate_guard import connect_aggregate_relation_guards

        connect_aggregate_relation_guards()
