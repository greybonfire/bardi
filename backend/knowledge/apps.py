from importlib import import_module

from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "knowledge"
    verbose_name = "Knowledge catalog"

    def import_models(self) -> None:
        # Focused feature modules extend the knowledge model graph during Django's model
        # loading phase so migrations, the app registry, and static analysis observe one
        # final EvidenceLink owner union before models_ready is set. Owner-extending modules
        # are imported in dependency order so each sees the complete graph installed before it.
        super().import_models()
        fees = import_module(".fees", package=__package__)
        eligibility_bases = import_module(".eligibility_bases", package=__package__)
        procedure_dependencies = import_module(".procedure_dependencies", package=__package__)
        service_point_routing = import_module(".service_point_routing", package=__package__)
        service_point_routing_contract = import_module(
            ".service_point_routing_contract", package=__package__
        )
        evidence_workflow = import_module(".evidence_workflow", package=__package__)

        assert fees.Fee is not None
        assert eligibility_bases.EligibilityBasisPublicationGate is not None
        assert procedure_dependencies.ProcedureDependency is not None
        assert service_point_routing.ServicePointVersion is not None
        assert service_point_routing_contract.install_service_point_temporal_contract is not None
        assert evidence_workflow.EvidenceDiscrepancy is not None

    def ready(self) -> None:
        from . import eligibility_basis_admin as _eligibility_basis_admin
        from . import evidence_workflow_admin as _evidence_workflow_admin
        from . import fee_admin as _fee_admin
        from . import procedure_dependency_admin as _procedure_dependency_admin
        from . import service_point_routing_admin as _service_point_routing_admin
        from .aggregate_guard import connect_aggregate_relation_guards

        assert _fee_admin.FeeAdmin is not None
        assert _eligibility_basis_admin.EligibilityBasisAdmin is not None
        assert _procedure_dependency_admin.ProcedureDependencyAdmin is not None
        assert _service_point_routing_admin.ServicePointVersionAdmin is not None
        assert _evidence_workflow_admin.EvidenceDiscrepancyAdmin is not None
        connect_aggregate_relation_guards()
