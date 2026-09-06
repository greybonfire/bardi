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
        evidence_workflow_temporal = import_module(
            ".evidence_workflow_temporal", package=__package__
        )
        planning_scenarios = import_module(".planning_scenarios", package=__package__)
        review_workflow = import_module(".review_workflow", package=__package__)

        assert fees.Fee is not None
        assert eligibility_bases.EligibilityBasisPublicationGate is not None
        assert procedure_dependencies.ProcedureDependency is not None
        assert service_point_routing.ServicePointVersion is not None
        assert service_point_routing_contract.install_service_point_temporal_contract is not None
        assert evidence_workflow.EvidenceDiscrepancy is not None
        assert evidence_workflow_temporal.EvidenceDiscrepancyTransition is not None
        assert planning_scenarios.PlanningScenario is not None
        assert review_workflow.ProcedureVersionReviewApproval is not None

        # Evidence identifiers are intentionally owner-scoped. Feature modules install
        # additional owner fields dynamically, so their constraints can only be attached
        # after the complete owner union has loaded.
        from django.db import models
        from django.db.models import Q

        from .models import NONBLANK_PATTERN, EvidenceLink

        existing = {constraint.name for constraint in EvidenceLink._meta.constraints}
        if "evidence_semantic_id_blank_or_nonblank" not in existing:
            EvidenceLink._meta.constraints = [
                *EvidenceLink._meta.constraints,
                models.CheckConstraint(
                    condition=Q(semantic_id="") | Q(semantic_id__regex=NONBLANK_PATTERN),
                    name="evidence_semantic_id_blank_or_nonblank",
                ),
            ]
        for field_name, constraint_name in (
            ("fee", "unique_evidence_id_fee_owner"),
            ("eligibility_basis", "unique_evidence_id_basis_owner"),
            ("procedure_dependency", "unique_evidence_id_dependency_owner"),
            ("service_point_version", "unique_evidence_id_point_version_owner"),
            (
                "procedure_service_point_association",
                "unique_evidence_id_point_association_owner",
            ),
        ):
            if constraint_name not in existing:
                EvidenceLink._meta.constraints = [
                    *EvidenceLink._meta.constraints,
                    models.UniqueConstraint(
                        fields=(field_name, "semantic_id"),
                        condition=Q(**{f"{field_name}__isnull": False}) & ~Q(semantic_id=""),
                        name=constraint_name,
                    ),
                ]

    def ready(self) -> None:
        from . import admin_lifecycle_admin as _admin_lifecycle_admin
        from . import eligibility_basis_admin as _eligibility_basis_admin
        from . import evidence_workflow_admin as _evidence_workflow_admin
        from . import fee_admin as _fee_admin
        from . import planning_scenario_admin as _planning_scenario_admin
        from . import procedure_dependency_admin as _procedure_dependency_admin
        from . import review_workflow_admin as _review_workflow_admin
        from . import service_point_routing_admin as _service_point_routing_admin
        from .aggregate_guard import connect_aggregate_relation_guards
        from .runtime_integrity import (
            install_evidence_identity_validation,
            install_national_id_renewal_integrity_verification,
            install_passport_renewal_integrity_verification,
            install_temporary_family_exemption_integrity_verification,
        )

        assert _fee_admin.FeeAdmin is not None
        assert _eligibility_basis_admin.EligibilityBasisAdmin is not None
        assert _procedure_dependency_admin.ProcedureDependencyAdmin is not None
        assert _service_point_routing_admin.ServicePointVersionAdmin is not None
        assert _evidence_workflow_admin.EvidenceDiscrepancyAdmin is not None
        assert _planning_scenario_admin.PlanningScenarioAdmin is not None
        assert _review_workflow_admin.ProcedureVersionReviewPolicyAdmin is not None
        assert _admin_lifecycle_admin.clone_selected_to_draft is not None
        install_evidence_identity_validation()
        install_passport_renewal_integrity_verification()
        install_national_id_renewal_integrity_verification()
        install_temporary_family_exemption_integrity_verification()
        connect_aggregate_relation_guards()
