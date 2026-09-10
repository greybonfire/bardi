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
from planning.facts import FACT_DEFINITIONS

from .domain import (
    KnowledgeSnapshotLoadError,
    StoredRuleLoadDiagnostic,
    compatibility_errors,
    decode_stored_rule,
    to_domain_fact,
)

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
class _EvidenceInfo:
    passage: str
    location: str
    applicability_context: str
    support_status: str
    verification_state: str
    sources: tuple[tuple[str, Any, str], ...]


@dataclass(frozen=True, slots=True)
class _ValidationData:
    fact_rows: tuple[Any, ...]
    definitions: Mapping[str, Any]
    published_definitions: Mapping[str, Any]
    evidence: Mapping[tuple[str, int], tuple[_EvidenceInfo, ...]]


def _failure(owner: str, code: str, path: tuple[str | int, ...]) -> StoredRuleLoadDiagnostic:
    from planning.diagnostics import ValidationDiagnostic

    return StoredRuleLoadDiagnostic(owner, (ValidationDiagnostic(code, path),))


def _raise(failures: list[StoredRuleLoadDiagnostic]) -> None:
    if failures:
        raise KnowledgeSnapshotLoadError(failures)


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
    sources_by_link: dict[int, list[tuple[str, Any, str]]] = {}
    for row in source_rows:
        sources_by_link.setdefault(row["evidence_link_id"], []).append(
            (
                row["source__classification"],
                row["source__observation_date"],
                row["source__observation_context"],
            )
        )

    evidence: dict[tuple[str, int], list[_EvidenceInfo]] = {}
    for row in link_rows:
        owner = next(
            (
                (field, row[f"{field}_id"])
                for field in _OWNER_FIELDS
                if row[f"{field}_id"] is not None
            ),
            None,
        )
        if owner is None:
            # The workflow adapter retains the historical owner-resolution failure.  The
            # semantic loader itself ignored malformed orphan links unless they were used.
            continue
        evidence.setdefault(owner, []).append(
            _EvidenceInfo(
                row["passage"],
                row["location"],
                row["applicability_context"],
                row["support_status"],
                row["verification_state"],
                tuple(sources_by_link.get(row["id"], ())),
            )
        )
    return _ValidationData(
        fact_rows,
        definitions,
        published_definitions,
        {key: tuple(value) for key, value in evidence.items()},
    )


def _has_adequate_core_evidence(links: tuple[_EvidenceInfo, ...]) -> bool:
    """Match domain._materialize_core_knowledge_snapshot exactly."""

    return any(
        link.verification_state == "current"
        and link.support_status == "supports"
        and bool(link.sources)
        and bool(link.passage.strip())
        and bool(link.location.strip())
        and bool(link.applicability_context.strip())
        for link in links
    ) and not any(
        link.verification_state == "current" and link.support_status == "contradicts"
        for link in links
    )


def _valid_fee_shape(row: Mapping[str, Any]) -> bool:
    amount = row["amount"]
    minimum = row["minimum_amount"]
    maximum = row["maximum_amount"]
    amount_ok = type(amount) is int and amount >= 0
    range_ok = type(minimum) is int and type(maximum) is int and minimum >= 0 and maximum >= minimum
    if row["value_state"] == "known":
        return amount_ok and minimum is None and maximum is None
    if row["value_state"] == "range":
        return amount is None and range_ok
    if row["value_state"] == "unknown":
        return amount is None and minimum is None and maximum is None
    if row["value_state"] == "unverified":
        return (
            (amount_ok and minimum is None and maximum is None) or (amount is None and range_ok)
        ) and row["verification_state"] in {"needs_reverification", "stale", "disputed"}
    return False


def _validate_core(data: _ValidationData) -> list[StoredRuleLoadDiagnostic]:
    from .fees import Fee
    from .models import (
        ChecklistItem,
        ProcedureVersion,
        Service,
        ServiceContradiction,
        ServiceQuestion,
    )

    failures: list[StoredRuleLoadDiagnostic] = []
    for fact_row in data.fact_rows:
        if not fact_row.is_published or not fact_row.derived:
            continue
        expected = FACT_DEFINITIONS.get(fact_row.key)
        if expected is None or not expected.derived or compatibility_errors((fact_row,)):
            failures.append(
                _failure(
                    f"fact:{fact_row.key}", "unsupported_derived_fact", ("facts", fact_row.key)
                )
            )

    service_rows = cast(
        list[dict[str, Any]],
        list(Service.objects.order_by("semantic_id").values("semantic_id", "is_active")),
    )
    active_service_ids = {row["semantic_id"] for row in service_rows if row["is_active"]}

    item_rows = cast(
        list[dict[str, Any]],
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
    for row in item_rows:
        owner = f"checklist_item:{row['procedure_version__semantic_id']}:{row['semantic_id']}"
        raw_rule = row["applicability"]
        if raw_rule != {}:
            decoded = decode_stored_rule(raw_rule, data.published_definitions)
            if decoded.predicate is None:
                failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
                continue
        links = data.evidence.get(("checklist_item", row["id"]), ())
        if row["verification_state"] == "current" and not links:
            failures.append(_failure(owner, "missing_evidence_link", ("evidence",)))
            continue
        if any(not link.sources for link in links):
            failures.append(_failure(owner, "missing_evidence_source", ("evidence",)))

    from .models import (
        ServiceContradictionFact,
        ServiceProcedureCandidate,
        ServiceQuestionResolvedFact,
        Step,
        Warning,
    )

    step_rows = cast(
        list[dict[str, Any]],
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
    for row in step_rows:
        owner = f"step:{row['procedure_version__semantic_id']}:{row['semantic_id']}"
        predicate_is_invalid = False
        if row["applicability"] != {}:
            decoded = decode_stored_rule(row["applicability"], data.published_definitions)
            if decoded.predicate is None:
                failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
                predicate_is_invalid = True
        links = data.evidence.get(("step", row["id"]), ())
        basis_broken = row["scope"] == "eligibility_basis" and (
            row["eligibility_basis_id"] is None
            or row["eligibility_basis__procedure_version_id"] != row["procedure_version_id"]
        )
        if predicate_is_invalid:
            if basis_broken:
                failures.append(_failure(owner, "invalid_basis_owner", ("scope",)))
            continue
        if basis_broken:
            failures.append(_failure(owner, "invalid_basis_owner", ("scope",)))
        elif row["verification_state"] == "current" and not _has_adequate_core_evidence(links):
            failures.append(_failure(owner, "inadequate_evidence", ("evidence",)))

    fee_rows = cast(
        list[dict[str, Any]],
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
    for row in fee_rows:
        owner = f"fee:{row['procedure_version__semantic_id']}:{row['semantic_id']}"
        predicate_is_invalid = False
        if row["applicability"] != {}:
            decoded = decode_stored_rule(row["applicability"], data.published_definitions)
            if decoded.predicate is None:
                failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
                predicate_is_invalid = True
        if predicate_is_invalid:
            continue
        links = data.evidence.get(("fee", row["id"]), ())
        basis_broken = row["scope"] == "eligibility_basis" and (
            row["eligibility_basis_id"] is None
            or row["eligibility_basis__procedure_version_id"] != row["procedure_version_id"]
        )
        evidence_required = row["value_state"] in {"known", "range", "unverified"}
        current_support_required = (
            row["value_state"] in {"known", "range"} and row["verification_state"] == "current"
        )
        if basis_broken:
            failures.append(_failure(owner, "invalid_basis_owner", ("scope",)))
        elif not row["currency"].strip():
            failures.append(_failure(owner, "missing_currency", ("currency",)))
        elif not row["fee_type"].strip():
            failures.append(_failure(owner, "missing_fee_type", ("fee_type",)))
        elif not _valid_fee_shape(row):
            failures.append(_failure(owner, "invalid_fee_value", ("value_state",)))
        elif evidence_required and not links:
            failures.append(_failure(owner, "missing_evidence_link", ("evidence",)))
        elif evidence_required and any(not link.sources for link in links):
            failures.append(_failure(owner, "missing_evidence_source", ("evidence",)))
        elif current_support_required and not _has_adequate_core_evidence(links):
            failures.append(_failure(owner, "inadequate_evidence", ("evidence",)))

    warning_rows = cast(
        list[dict[str, Any]],
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
    for row in warning_rows:
        owner = f"warning:{row['procedure_version__semantic_id']}:{row['semantic_id']}"
        if row["applicability"] != {}:
            decoded = decode_stored_rule(row["applicability"], data.published_definitions)
            if decoded.predicate is None:
                failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
        links = data.evidence.get(("warning", row["id"]), ())
        invalid = (row["kind"] == "product" and bool(links)) or (
            row["kind"] == "administrative"
            and row["verification_state"] == "current"
            and not _has_adequate_core_evidence(links)
        )
        if invalid:
            failures.append(_failure(owner, "invalid_warning_evidence", ("evidence",)))

    candidate_rows = cast(
        list[dict[str, Any]],
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
    for row in candidate_rows:
        service_id = row["service__semantic_id"]
        definitions = (
            data.published_definitions if service_id in active_service_ids else data.definitions
        )
        decoded = decode_stored_rule(row["selection_predicate"], definitions)
        if decoded.predicate is None:
            failures.append(
                StoredRuleLoadDiagnostic(
                    f"candidate:{service_id}:{row['procedure__semantic_id']}", decoded.diagnostics
                )
            )

    version_rows = cast(
        list[dict[str, Any]],
        list(
            ProcedureVersion.objects.filter(
                state__in=(ProcedureVersion.State.PUBLISHED, ProcedureVersion.State.WITHDRAWN)
            ).values("semantic_id", "applicability")
        ),
    )
    for row in version_rows:
        decoded = decode_stored_rule(row["applicability"], data.published_definitions)
        if decoded.predicate is None:
            failures.append(
                StoredRuleLoadDiagnostic(
                    f"procedure_version:{row['semantic_id']}", decoded.diagnostics
                )
            )

    contradiction_rows = cast(
        list[dict[str, Any]],
        list(
            ServiceContradiction.objects.order_by("service__semantic_id", "semantic_id").values(
                "semantic_id", "service__semantic_id", "condition"
            )
        ),
    )
    contradiction_links = cast(
        list[dict[str, Any]],
        list(
            ServiceContradictionFact.objects.order_by(
                "contradiction__semantic_id", "position", "fact__key"
            ).values("contradiction__semantic_id", "fact__key")
        ),
    )
    contradiction_facts: dict[str, list[str]] = {}
    for row in contradiction_links:
        contradiction_facts.setdefault(row["contradiction__semantic_id"], []).append(
            row["fact__key"]
        )
    for row in contradiction_rows:
        service_id = row["service__semantic_id"]
        definitions = (
            data.published_definitions if service_id in active_service_ids else data.definitions
        )
        decoded = decode_stored_rule(row["condition"], definitions)
        owner = f"contradiction:{row['semantic_id']}"
        if decoded.predicate is None:
            failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
            continue
        if service_id in active_service_ids:
            unpublished = sorted(
                set(contradiction_facts.get(row["semantic_id"], ()))
                - data.published_definitions.keys()
            )
            if unpublished:
                from planning.diagnostics import ValidationDiagnostic

                failures.append(
                    StoredRuleLoadDiagnostic(
                        owner,
                        tuple(
                            ValidationDiagnostic("unpublished_fact", ("facts", key))
                            for key in unpublished
                        ),
                    )
                )

    question_rows = cast(
        list[dict[str, Any]],
        list(
            ServiceQuestion.objects.order_by("service__semantic_id", "semantic_id").values(
                "semantic_id", "service__semantic_id", "fact__key"
            )
        ),
    )
    question_links = cast(
        list[dict[str, Any]],
        list(
            ServiceQuestionResolvedFact.objects.order_by(
                "question__semantic_id", "position", "fact__key"
            ).values("question__semantic_id", "fact__key")
        ),
    )
    resolved: dict[str, list[str]] = {}
    for row in question_links:
        resolved.setdefault(row["question__semantic_id"], []).append(row["fact__key"])
    for row in question_rows:
        service_id = row["service__semantic_id"]
        if service_id not in active_service_ids:
            continue
        keys = {row["fact__key"], *resolved.get(row["semantic_id"], ())}
        unpublished = sorted(keys - data.published_definitions.keys())
        if unpublished:
            from planning.diagnostics import ValidationDiagnostic

            failures.append(
                StoredRuleLoadDiagnostic(
                    f"question:{row['semantic_id']}",
                    tuple(
                        ValidationDiagnostic("unpublished_fact", ("facts", key))
                        for key in unpublished
                    ),
                )
            )
    return failures


def _source_presence(data: _ValidationData, field: str, owner_id: int) -> tuple[_EvidenceInfo, ...]:
    return data.evidence.get((field, owner_id), ())


def _validate_bases(data: _ValidationData) -> list[StoredRuleLoadDiagnostic]:
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
    failures: list[StoredRuleLoadDiagnostic] = []
    for row in rows:
        owner = f"eligibility_basis:{row['procedure_version__semantic_id']}:{row['semantic_id']}"
        if row["reachability"] != {}:
            decoded = decode_stored_rule(row["reachability"], data.published_definitions)
            if decoded.predicate is None:
                failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
                continue
        if row["qualification"] == {}:
            failures.append(_failure(owner, "missing_qualification", ("qualification",)))
            continue
        decoded = decode_stored_rule(row["qualification"], data.published_definitions)
        if decoded.predicate is None:
            failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
            continue
        links = _source_presence(data, "eligibility_basis", row["id"])
        if (
            not row["text_ar"].strip()
            or not row["text_en"].strip()
            or not links
            or any(not link.sources for link in links)
        ):
            failures.append(_failure(owner, "invalid_basis_evidence", ("evidence",)))
    return failures


def _validate_dependencies(data: _ValidationData) -> list[StoredRuleLoadDiagnostic]:
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
    failures: list[StoredRuleLoadDiagnostic] = []
    for row in rows:
        owner = f"procedure_dependency:{row['procedure_version__semantic_id']}:{row['semantic_id']}"
        if row["relation"] != ProcedureDependency.Relation.BLOCKING_PREREQUISITE:
            failures.append(_failure(owner, "unsupported_dependency_relation", ("relation",)))
            continue
        if row["procedure_version__procedure_id"] == row["target_procedure_id"]:
            failures.append(_failure(owner, "self_dependency", ("target_procedure",)))
            continue
        if row["applicability"] != {}:
            decoded = decode_stored_rule(row["applicability"], data.published_definitions)
            if decoded.predicate is None:
                failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
                continue
        if row["satisfied_when"] == {}:
            failures.append(_failure(owner, "missing_satisfied_when", ("satisfied_when",)))
            continue
        decoded = decode_stored_rule(row["satisfied_when"], data.published_definitions)
        if decoded.predicate is None:
            failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
            continue
        links = _source_presence(data, "procedure_dependency", row["id"])
        if (
            not row["text_ar"].strip()
            or not row["text_en"].strip()
            or not links
            or any(not link.sources for link in links)
        ):
            failures.append(_failure(owner, "invalid_dependency_evidence", ("evidence",)))
    return failures


def _snapshot_evidence_is_adequate(links: tuple[_EvidenceInfo, ...]) -> bool:
    adequate = False
    for link in links:
        if (
            not link.passage.strip()
            or not link.location.strip()
            or not link.applicability_context.strip()
        ):
            return False
        if any(
            classification == "field_report" and (observation_date is None or not context.strip())
            for classification, observation_date, context in link.sources
        ):
            return False
        if link.verification_state == "current" and link.support_status == "contradicts":
            return False
        adequate |= (
            link.verification_state == "current"
            and link.support_status == "supports"
            and bool(link.sources)
        )
    return adequate


def _validate_routing(data: _ValidationData) -> list[StoredRuleLoadDiagnostic]:
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
    failures: list[StoredRuleLoadDiagnostic] = []
    for row in associations:
        owner = (
            f"service_point_association:{row['procedure_version__semantic_id']}:"
            f"{row['semantic_id']}"
        )
        decoded = decode_stored_rule(row["applicability"], data.published_definitions)
        links = _source_presence(data, "procedure_service_point_association", row["id"])
        if (
            decoded.predicate is None
            or not links
            or any(not link.sources for link in links)
            or (
                row["verification_state"] == "current" and not _snapshot_evidence_is_adequate(links)
            )
        ):
            failures.append(
                StoredRuleLoadDiagnostic(
                    owner,
                    decoded.diagnostics
                    or (_diagnostic("invalid_routing_evidence", ("evidence",)),),
                )
            )
    for row in materials:
        owner = f"service_point_version:{row['semantic_id']}"
        links = _source_presence(data, "service_point_version", row["id"])
        if (
            not row["address_ar"].strip()
            or not row["address_en"].strip()
            or row["availability"] not in ServicePointVersion.Availability.values
            or not links
            or any(not link.sources for link in links)
            or (
                row["verification_state"] == "current" and not _snapshot_evidence_is_adequate(links)
            )
        ):
            failures.append(_failure(owner, "invalid_service_point_material", ()))
    return failures


def _diagnostic(code: str, path: tuple[str | int, ...]) -> Any:
    from planning.diagnostics import ValidationDiagnostic

    return ValidationDiagnostic(code, path)


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
    _raise(_validate_core(data))
    _raise(_validate_bases(data))
    _raise(_validate_dependencies(data))
    _raise(_validate_routing(data))
    if evaluation_date is not None:
        _validate_workflow_owners(evaluation_date)


__all__ = ("validate_global_catalog", "validation_row_counts")
