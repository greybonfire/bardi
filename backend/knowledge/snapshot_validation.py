"""Global, lightweight request-loader integrity validation.

The full snapshot adapter historically validated the whole catalog while constructing DTOs.
Service-scoped planning keeps those fail-closed checks, but performs them here as scalar
rows and evidence summaries before constructing the requested graph.  This module is not a
publication validator and intentionally does not change publication-only gates.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any, cast

from django.core.exceptions import ValidationError
from django.db.models import Q
from planning.facts import FactDefinition as DomainFactDefinition

from .domain import to_domain_fact
from .snapshot_policy import (
    AssociationRow,
    BasisRow,
    CandidateRow,
    ClaimRow,
    ContradictionFactRow,
    ContradictionRow,
    CoreInputs,
    DependencyRow,
    EvidenceRow,
    FeeRow,
    MaterialRow,
    QuestionFactRow,
    QuestionRow,
    ServiceRow,
    StepRow,
    VersionRow,
    WarningRow,
    core_evidence_owner,
    routing_evidence_owner,
    summarize_evidence_rows,
    validate_bases,
    validate_core,
    validate_dependencies,
    validate_routing,
)
from .snapshot_policy import EvidenceInfo as _EvidenceInfo

_OWNER_FIELDS = (
    "checklist_item",
    "step",
    "warning",
    "fee",
    "eligibility_basis",
    "procedure_dependency",
    "service_point_version",
    "procedure_service_point_association",
)
# These are materializer families, not the workflow's single-owner resolution order.
# Core and routing each choose their first non-null owner; basis and dependency adapters
# independently read their reverse relation, even when a malformed link spans families.
_MATERIALIZER_OWNER_GROUPS = (
    ("eligibility_basis",),
    ("procedure_dependency",),
)
_PUBLIC_VERSION_STATES = ("published", "withdrawn")


def _validation_evidence_queryset() -> Any:
    """Return exactly the EvidenceLink owner universe read by the full loaders.

    Core and feature snapshot adapters first select published/withdrawn semantic owners.  Routing
    additionally selects material versions referenced by those public associations.  Draft,
    orphaned, and routing-material-only rows outside that graph are not part of request-time
    catalog validation and must not pull their provenance into the scoped loader.
    """

    from .models import EvidenceLink
    from .procedure_dependencies import ProcedureDependency
    from .service_point_routing import ProcedureServicePointAssociation

    public_dependencies = ProcedureDependency.objects.filter(
        procedure_version__state__in=_PUBLIC_VERSION_STATES
    ).values("pk")
    public_associations = ProcedureServicePointAssociation.objects.filter(
        procedure_version__state__in=_PUBLIC_VERSION_STATES
    ).values("pk")
    public_materials = ProcedureServicePointAssociation.objects.filter(
        procedure_version__state__in=_PUBLIC_VERSION_STATES
    ).values("service_point_version_id")
    owner_filter = (
        Q(checklist_item__procedure_version__state__in=_PUBLIC_VERSION_STATES)
        | Q(step__procedure_version__state__in=_PUBLIC_VERSION_STATES)
        | Q(warning__procedure_version__state__in=_PUBLIC_VERSION_STATES)
        | Q(fee__procedure_version__state__in=_PUBLIC_VERSION_STATES)
        | Q(eligibility_basis__procedure_version__state__in=_PUBLIC_VERSION_STATES)
        | Q(procedure_dependency_id__in=public_dependencies)
        | Q(procedure_service_point_association_id__in=public_associations)
        | Q(service_point_version_id__in=public_materials)
    )
    return EvidenceLink.objects.filter(owner_filter).distinct()


@dataclass(frozen=True, slots=True)
class _ValidationData:
    definitions: Mapping[str, DomainFactDefinition]
    published_definitions: Mapping[str, DomainFactDefinition]
    evidence: Mapping[tuple[str, int], tuple[_EvidenceInfo, ...]]


def _load_validation_data() -> _ValidationData:
    from .models import EvidenceLinkSource, FactDefinition

    # Fact model instances are the one intentionally complete global registry exception.
    fact_rows = tuple(FactDefinition.objects.order_by("key"))
    definitions = MappingProxyType({row.key: to_domain_fact(row) for row in fact_rows})
    published_definitions = MappingProxyType(
        {row.key: to_domain_fact(row) for row in fact_rows if row.is_published}
    )

    owner_fields = tuple(f"{field}_id" for field in _OWNER_FIELDS)
    validation_evidence = _validation_evidence_queryset()
    link_rows = list(
        validation_evidence.order_by("pk").values(
            "id",
            *owner_fields,
            "passage",
            "location",
            "applicability_context",
            "support_status",
            "verification_state",
        )
    )
    source_rows = list(
        EvidenceLinkSource.objects.filter(evidence_link_id__in=[row["id"] for row in link_rows])
        .order_by("evidence_link_id", "position", "source__semantic_id")
        .values(
            "evidence_link_id",
            "source__classification",
            "source__observation_date",
            "source__observation_context",
        )
    )
    summaries = summarize_evidence_rows(cast(list[EvidenceRow], link_rows), source_rows)
    evidence: dict[tuple[str, int], list[_EvidenceInfo]] = {}
    for row in link_rows:
        info = summaries[row["id"]]
        core_owner = core_evidence_owner(row)
        if core_owner is not None:
            evidence.setdefault(core_owner, []).append(info)
        routing_owner = routing_evidence_owner(row)
        if routing_owner is not None:
            evidence.setdefault(routing_owner, []).append(info)
        for fields in _MATERIALIZER_OWNER_GROUPS:
            owner = next(
                ((field, row[f"{field}_id"]) for field in fields if row[f"{field}_id"] is not None),
                None,
            )
            if owner is not None:
                evidence.setdefault(owner, []).append(info)
    return _ValidationData(
        definitions,
        published_definitions,
        {key: tuple(value) for key, value in evidence.items()},
    )


def _load_core_inputs(data: _ValidationData) -> CoreInputs:
    """Capture the original scalar query sequence; all core decisions live in the policy."""
    from .fees import Fee
    from .models import (
        ChecklistItem,
        ProcedureVersion,
        Service,
        ServiceContradiction,
        ServiceQuestion,
    )

    service_rows = cast(
        list[ServiceRow],
        list(Service.objects.order_by("semantic_id").values("semantic_id", "is_active")),
    )

    item_rows = cast(
        list[ClaimRow],
        list(
            ChecklistItem.objects.filter(
                procedure_version__state__in=("published", "withdrawn")
            ).values(
                "id",
                "procedure_version__semantic_id",
                "semantic_id",
                "text_ar",
                "text_en",
                "applicability",
                "verification_state",
            )
        ),
    )
    from .models import (
        ServiceContradictionFact,
        ServiceProcedureCandidate,
        ServiceQuestionResolvedFact,
        Step,
        Warning,
    )

    step_rows = cast(
        list[StepRow],
        list(
            Step.objects.filter(procedure_version__state__in=("published", "withdrawn")).values(
                "id",
                "procedure_version__semantic_id",
                "semantic_id",
                "applicability",
                "scope",
                "eligibility_basis_id",
                "eligibility_basis__procedure_version_id",
                "procedure_version_id",
                "verification_state",
            )
        ),
    )
    fee_rows = cast(
        list[FeeRow],
        list(
            Fee.objects.filter(procedure_version__state__in=("published", "withdrawn")).values(
                "id",
                "procedure_version__semantic_id",
                "semantic_id",
                "applicability",
                "scope",
                "eligibility_basis_id",
                "eligibility_basis__procedure_version_id",
                "procedure_version_id",
                "currency",
                "fee_type",
                "value_state",
                "amount",
                "minimum_amount",
                "maximum_amount",
                "verification_state",
            )
        ),
    )
    warning_rows = cast(
        list[WarningRow],
        list(
            Warning.objects.filter(procedure_version__state__in=("published", "withdrawn")).values(
                "id",
                "procedure_version__semantic_id",
                "semantic_id",
                "applicability",
                "kind",
                "verification_state",
            )
        ),
    )
    candidate_rows = cast(
        list[CandidateRow],
        list(
            ServiceProcedureCandidate.objects.order_by(
                "service__semantic_id", "procedure__semantic_id"
            ).values(
                "service__semantic_id",
                "procedure__semantic_id",
                "selection_predicate",
            )
        ),
    )
    version_rows = cast(
        list[VersionRow],
        list(
            ProcedureVersion.objects.filter(
                state__in=(ProcedureVersion.State.PUBLISHED, ProcedureVersion.State.WITHDRAWN)
            ).values("semantic_id", "applicability")
        ),
    )
    contradiction_rows = cast(
        list[ContradictionRow],
        list(
            ServiceContradiction.objects.order_by("service__semantic_id", "semantic_id").values(
                "semantic_id", "service__semantic_id", "condition"
            )
        ),
    )
    contradiction_links = cast(
        list[ContradictionFactRow],
        list(
            ServiceContradictionFact.objects.order_by(
                "contradiction__semantic_id", "position", "fact__key"
            ).values("contradiction__semantic_id", "fact__key")
        ),
    )
    question_rows = cast(
        list[QuestionRow],
        list(
            ServiceQuestion.objects.order_by("service__semantic_id", "semantic_id").values(
                "semantic_id", "service__semantic_id", "fact__key"
            )
        ),
    )
    question_links = cast(
        list[QuestionFactRow],
        list(
            ServiceQuestionResolvedFact.objects.order_by(
                "question__semantic_id", "position", "fact__key"
            ).values("question__semantic_id", "fact__key")
        ),
    )
    return CoreInputs(
        data.definitions,
        data.published_definitions,
        data.evidence,
        services=service_rows,
        checklist_items=item_rows,
        steps=step_rows,
        fees=fee_rows,
        warnings=warning_rows,
        candidates=candidate_rows,
        versions=version_rows,
        contradictions=contradiction_rows,
        contradiction_facts=contradiction_links,
        questions=question_rows,
        question_facts=question_links,
    )


def _validate_bases(data: _ValidationData) -> None:
    from .models import EligibilityBasis, ProcedureVersion

    rows = list(
        EligibilityBasis.objects.filter(
            procedure_version__state__in=(
                ProcedureVersion.State.PUBLISHED,
                ProcedureVersion.State.WITHDRAWN,
            )
        ).values(
            "id",
            "procedure_version__semantic_id",
            "semantic_id",
            "text_ar",
            "text_en",
            "reachability",
            "qualification",
        )
    )
    validate_bases(cast(list[BasisRow], rows), data.published_definitions, data.evidence)


def _validate_dependencies(data: _ValidationData) -> None:
    from .models import ProcedureVersion
    from .procedure_dependencies import ProcedureDependency

    rows = list(
        ProcedureDependency.objects.filter(
            procedure_version__state__in=(
                ProcedureVersion.State.PUBLISHED,
                ProcedureVersion.State.WITHDRAWN,
            )
        ).values(
            "id",
            "procedure_version__semantic_id",
            "procedure_version__procedure_id",
            "target_procedure_id",
            "semantic_id",
            "text_ar",
            "text_en",
            "relation",
            "applicability",
            "satisfied_when",
        )
    )
    validate_dependencies(
        cast(list[DependencyRow], rows), data.published_definitions, data.evidence
    )


def _validate_routing(data: _ValidationData) -> None:
    from .models import ProcedureVersion
    from .service_point_routing import ProcedureServicePointAssociation, ServicePointVersion

    associations = cast(
        list[dict[str, Any]],
        list(
            ProcedureServicePointAssociation.objects.filter(
                procedure_version__state__in=(
                    ProcedureVersion.State.PUBLISHED,
                    ProcedureVersion.State.WITHDRAWN,
                )
            ).values(
                "id",
                "procedure_version__semantic_id",
                "semantic_id",
                "service_point_version_id",
                "applicability",
                "verification_state",
            )
        ),
    )
    material_ids = {row["service_point_version_id"] for row in associations}
    materials = cast(
        list[dict[str, Any]],
        list(
            ServicePointVersion.objects.filter(pk__in=material_ids).values(
                "id",
                "semantic_id",
                "address_ar",
                "address_en",
                "availability",
                "verification_state",
            )
        ),
    )
    validate_routing(
        cast(list[AssociationRow], associations),
        cast(list[MaterialRow], materials),
        data.published_definitions,
        data.evidence,
    )


def _validate_workflow_owners(evaluation_date: date) -> None:
    """Match full-loader owner resolution for history visible at this date."""

    from . import evidence_workflow as workflow
    from .evidence_workflow_temporal import EvidenceDiscrepancyTransition
    from .models import EvidenceLink

    transition_ids = set(
        EvidenceDiscrepancyTransition.objects.filter(
            occurred_at__date__lte=evaluation_date,
        ).values_list("discrepancy__anchor_evidence_link_id", flat=True)
    )
    review_ids = set(
        workflow.EvidenceReverificationEvent.objects.filter(
            meaning_changed=False,
            occurred_at__date__lte=evaluation_date,
        ).values_list("anchor_evidence_link_id", flat=True)
    )
    anchor_ids = transition_ids | review_ids
    if not anchor_ids:
        return

    owner_fields = tuple(f"{field}_id" for _, field in workflow._OWNER_FIELDS)
    rows = list(EvidenceLink.objects.filter(pk__in=anchor_ids).values(*owner_fields))
    # Match workflow._owner_key: the first supported owner wins, while an ownerless
    # anchor remains malformed.  Multiple persisted owner fields are legacy data that the
    # full loader already accepts; this validation must not impose a stronger policy.
    if len(rows) != len(anchor_ids) or any(
        not any(row[field] is not None for field in owner_fields) for row in rows
    ):
        raise ValidationError("Evidence must have exactly one supported claim owner.")


def validation_row_counts(evaluation_date: date | None = None) -> dict[str, int]:
    """Count the exact row sets consumed by ``validate_global_catalog``.

    The measurement probe uses this accounting rather than broad table counts.  Keep these
    filters beside the validator so draft and unreachable routing provenance cannot be reported
    as request-time validation work by accident.
    """

    from . import evidence_workflow as workflow
    from .eligibility_bases import EligibilityBasis
    from .evidence_workflow_temporal import EvidenceDiscrepancyTransition
    from .fees import Fee
    from .models import (
        ChecklistItem,
        EvidenceLink,
        EvidenceLinkSource,
        FactDefinition,
        ProcedureVersion,
        Service,
        ServiceContradiction,
        ServiceContradictionFact,
        ServiceProcedureCandidate,
        ServiceQuestion,
        ServiceQuestionResolvedFact,
        Step,
        Warning,
    )
    from .procedure_dependencies import ProcedureDependency
    from .service_point_routing import ProcedureServicePointAssociation, ServicePointVersion

    public_versions = {ProcedureVersion.State.PUBLISHED, ProcedureVersion.State.WITHDRAWN}
    association_rows = ProcedureServicePointAssociation.objects.filter(
        procedure_version__state__in=public_versions
    )
    material_ids = association_rows.values("service_point_version_id")
    evidence_rows = _validation_evidence_queryset()
    evidence_ids = list(evidence_rows.values_list("pk", flat=True))
    counts = {
        "fact_definitions": FactDefinition.objects.order_by("key").count(),
        "validation_evidence_links": evidence_rows.count(),
        "validation_evidence_sources": EvidenceLinkSource.objects.filter(
            evidence_link_id__in=evidence_ids
        ).count(),
        "services": Service.objects.order_by("semantic_id").count(),
        "checklist_items": ChecklistItem.objects.filter(
            procedure_version__state__in=public_versions
        ).count(),
        "steps": Step.objects.filter(procedure_version__state__in=public_versions).count(),
        "fees": Fee.objects.filter(procedure_version__state__in=public_versions).count(),
        "warnings": Warning.objects.filter(procedure_version__state__in=public_versions).count(),
        "service_procedure_candidates": ServiceProcedureCandidate.objects.count(),
        "procedure_versions": ProcedureVersion.objects.filter(state__in=public_versions).count(),
        "service_contradictions": ServiceContradiction.objects.count(),
        "service_contradiction_facts": ServiceContradictionFact.objects.count(),
        "service_questions": ServiceQuestion.objects.count(),
        "service_question_resolved_facts": ServiceQuestionResolvedFact.objects.count(),
        "eligibility_bases": EligibilityBasis.objects.filter(
            procedure_version__state__in=public_versions
        ).count(),
        "procedure_dependencies": ProcedureDependency.objects.filter(
            procedure_version__state__in=public_versions
        ).count(),
        "procedure_service_point_associations": association_rows.count(),
        "service_point_versions": ServicePointVersion.objects.filter(pk__in=material_ids).count(),
    }
    if evaluation_date is not None:
        transition_rows = EvidenceDiscrepancyTransition.objects.filter(
            occurred_at__date__lte=evaluation_date,
        )
        review_rows = workflow.EvidenceReverificationEvent.objects.filter(
            meaning_changed=False,
            occurred_at__date__lte=evaluation_date,
        )
        # Event counts are row counts, not counts of their deduplicated anchor links.  The
        # owner read is intentionally separate and counts each unique anchor once.
        transition_anchor_ids = set(
            transition_rows.values_list("discrepancy__anchor_evidence_link_id", flat=True)
        )
        review_anchor_ids = set(review_rows.values_list("anchor_evidence_link_id", flat=True))
        anchor_ids = transition_anchor_ids | review_anchor_ids
        counts["workflow_discrepancy_transitions"] = transition_rows.count()
        counts["workflow_reverification_events"] = review_rows.count()
        counts["workflow_owner_rows"] = (
            EvidenceLink.objects.filter(pk__in=anchor_ids).count() if anchor_ids else 0
        )
    return counts


def validate_global_catalog(evaluation_date: date | None = None) -> None:
    """Run the request-time global integrity ledger without making a full DTO graph."""

    data = _load_validation_data()
    validate_core(_load_core_inputs(data))
    _validate_bases(data)
    _validate_dependencies(data)
    _validate_routing(data)
    if evaluation_date is not None:
        _validate_workflow_owners(evaluation_date)


__all__ = ("validate_global_catalog", "validation_row_counts")
