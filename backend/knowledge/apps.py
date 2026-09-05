from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "knowledge"
    verbose_name = "Knowledge catalog"

    def import_models(self) -> None:
        # Fee is a first-class model in this app, but lives in a focused module. Import it
        # during Django's model-loading phase so the app registry, migration state, and
        # static-analysis plugins all observe the final EvidenceLink owner graph before
        # models_ready is set. Late model mutation from ready() is intentionally avoided.
        super().import_models()
        from . import fees as _fees

        assert _fees.Fee is not None

    def ready(self) -> None:
        from . import fee_admin as _fee_admin
        from .aggregate_guard import connect_aggregate_relation_guards

        assert _fee_admin.FeeAdmin is not None
        connect_aggregate_relation_guards()
