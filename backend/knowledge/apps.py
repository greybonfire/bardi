from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "knowledge"
    verbose_name = "Knowledge catalog"

    def import_models(self) -> None:
        # Focused feature modules extend the knowledge model graph during Django's model
        # loading phase so migrations, the app registry, and static analysis observe one
        # final EvidenceLink owner union before models_ready is set.
        super().import_models()
        from . import eligibility_bases as _eligibility_bases
        from . import fees as _fees

        assert _fees.Fee is not None
        assert _eligibility_bases.EligibilityBasisPublicationGate is not None

    def ready(self) -> None:
        from . import eligibility_basis_admin as _eligibility_basis_admin
        from . import fee_admin as _fee_admin
        from .aggregate_guard import connect_aggregate_relation_guards

        assert _fee_admin.FeeAdmin is not None
        assert _eligibility_basis_admin.EligibilityBasisAdmin is not None
        connect_aggregate_relation_guards()
