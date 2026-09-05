from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "knowledge"
    verbose_name = "Knowledge catalog"

    def ready(self) -> None:
        # Fees extend the shared EvidenceLink owner union and must be installed before
        # aggregate guards/Admin use the final model graph.
        from . import fee_admin as _fee_admin
        from . import fees as _fees
        from .aggregate_guard import connect_aggregate_relation_guards

        assert _fees.Fee is not None and _fee_admin.FeeAdmin is not None
        connect_aggregate_relation_guards()
