"""Adapters between persisted catalog rows and the ORM-free planning domain."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from planning.catalog import (
    AuthoritySnapshot,
    ChecklistItemSnapshot,
    ContradictionSnapshot,
    EligibilityBasisSnapshot,
    EvidenceLinkSnapshot,
    FeeSnapshot,
    KnowledgeSnapshot,
    LocalizedText,
    ProcedureCandidateSnapshot,
    ProcedureVersionSnapshot,
    QuestionSnapshot,
    ServiceSnapshot,
    SourceSnapshot,
    StepSnapshot,
    WarningSnapshot,
)
from planning.facts import FACT_DEFINITIONS, FactKind
from planning.facts import FactDefinition as DomainFactDefinition
from planning.rules import Predicate, RuleValidationResult, validate_rule_v1
from planning.trust import VerificationState

from .snapshot_policy import (
    CandidateRow,
    ClaimRow,
    ContradictionRow,
    CoreInputs,
    EvidenceInfo,
    FeeRow,
    QuestionRow,
    ServiceRow,
    StepRow,
    VersionRow,
    WarningRow,
    core_evidence_owner,
    validate_core,
)
from .snapshot_policy import KnowledgeSnapshotLoadError as KnowledgeSnapshotLoadError
from .snapshot_policy import StoredRuleLoadDiagnostic as StoredRuleLoadDiagnostic

if TYPE_CHECKING:
    from .models import FactDefinition


def to_domain_fact(row: FactDefinition) -> DomainFactDefinition:
    return DomainFactDefinition(
        key=row.key,
        kind=cast(FactKind, row.kind),
        enum_values=tuple(row.enum_values),
        minimum=row.minimum,
        derived=row.derived,
    )


def load_fact_definitions() -> Mapping[str, DomainFactDefinition]:
    from .models import FactDefinition

    values = {row.key: to_domain_fact(row) for row in FactDefinition.objects.order_by("key")}
    return MappingProxyType(values)


def compatibility_errors(
    rows: Iterable[FactDefinition],
    registry: Mapping[str, DomainFactDefinition] = FACT_DEFINITIONS,
) -> tuple[str, ...]:
    errors: list[str] = []
    for row in sorted(rows, key=lambda item: item.key):
        expected = registry.get(row.key)
        if expected is None:
            errors.append(f"{row.key}:key")
            continue
        actual = to_domain_fact(row)
        for field in ("kind", "enum_values", "minimum", "derived"):
            if getattr(actual, field) != getattr(expected, field):
                errors.append(f"{row.key}:{field}")
    return tuple(errors)


def decode_stored_rule(
    raw: object,
    definitions: Mapping[str, DomainFactDefinition] | None = None,
) -> RuleValidationResult:
    """Decode using persisted definitions, never the planning default implicitly."""
    mapping = load_fact_definitions() if definitions is None else definitions
    return validate_rule_v1(raw, definitions=mapping)


def referenced_fact_keys(predicate: Predicate) -> frozenset[str]:
    keys: set[str] = set()
    stack = [predicate]
    while stack:
        current = stack.pop()
        if current.fact is not None:
            keys.add(current.fact)
        stack.extend(current.children)
    return frozenset(keys)


def diagnostic_messages(result: RuleValidationResult) -> list[str]:
    return [
        f"{diagnostic.code} at {'.'.join(str(part) for part in diagnostic.path)}"
        for diagnostic in result.diagnostics
    ]


def _materialize_core_knowledge_snapshot(scope: Any | None = None) -> KnowledgeSnapshot:
    """Build the internal ORM-free core graph, not a fully featured snapshot.

    This stable callable excludes feature composition; use the public loaders for
    complete snapshots and their documented transaction policies.
    """

    from django.db.models import Q

    from .fees import Fee
    from .models import (
        ChecklistItem,
        EligibilityBasis,
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

    # Every queryset is explicitly ordered and immediately materialized.  The remaining
    # work below uses only plain values and planning-domain objects.
    fact_rows = list(FactDefinition.objects.order_by("key"))
    service_queryset = Service.objects.order_by("semantic_id")
    candidate_queryset = ServiceProcedureCandidate.objects.order_by(
        "service__semantic_id", "procedure__semantic_id"
    )
    if scope is not None:
        service_queryset = service_queryset.filter(semantic_id=scope.service_id)
        candidate_queryset = candidate_queryset.filter(service__semantic_id=scope.service_id)
    service_rows = list(service_queryset.values("semantic_id", "text_ar", "text_en", "is_active"))
    candidate_rows = list(
        candidate_queryset.values(
            "service__semantic_id",
            "procedure__semantic_id",
            "procedure__text_ar",
            "procedure__text_en",
            "selection_predicate",
        )
    )
    version_queryset = ProcedureVersion.objects.filter(
        state__in=(ProcedureVersion.State.PUBLISHED, ProcedureVersion.State.WITHDRAWN)
    )
    if scope is not None:
        version_queryset = version_queryset.filter(procedure_id__in=scope.procedure_ids)
    version_rows = list(
        version_queryset.order_by("procedure__semantic_id", "semantic_id").values(
            "semantic_id",
            "procedure__semantic_id",
            "text_ar",
            "text_en",
            "applicability",
            "rules_contract_version",
            "state",
            "effective_from",
            "effective_to",
            "published_at",
            "published_by_id",
        )
    )
    checklist_queryset = ChecklistItem.objects.filter(
        procedure_version__state__in=(
            ProcedureVersion.State.PUBLISHED,
            ProcedureVersion.State.WITHDRAWN,
        )
    )
    if scope is not None:
        checklist_queryset = checklist_queryset.filter(procedure_version_id__in=scope.version_ids)
    checklist_rows = list(
        checklist_queryset.order_by(
            "procedure_version__semantic_id", "display_order", "semantic_id"
        ).values(
            "id",
            "procedure_version__semantic_id",
            "semantic_id",
            "text_ar",
            "text_en",
            "classification",
            "document_type__semantic_id",
            "quantity",
            "original_quantity",
            "copy_quantity",
            "display_order",
            "applicability",
            "scope",
            "scope_reference",
            "effective_from",
            "effective_to",
            "verification_state",
            "verified_on",
            "reverify_on",
        )
    )
    basis_queryset = EligibilityBasis.objects.filter(
        procedure_version__state__in=("published", "withdrawn")
    )
    if scope is not None:
        basis_queryset = basis_queryset.filter(procedure_version_id__in=scope.version_ids)
    basis_rows = list(
        basis_queryset.order_by("procedure_version__semantic_id", "semantic_id").values(
            "id", "procedure_version__semantic_id", "semantic_id"
        )
    )
    step_queryset = Step.objects.filter(procedure_version__state__in=("published", "withdrawn"))
    if scope is not None:
        step_queryset = step_queryset.filter(procedure_version_id__in=scope.version_ids)
    step_rows = list(
        step_queryset.order_by(
            "procedure_version__semantic_id", "phase_order", "slot", "semantic_id"
        ).values(
            "id",
            "procedure_version__semantic_id",
            "semantic_id",
            "text_ar",
            "text_en",
            "phase",
            "phase_order",
            "slot",
            "applicability",
            "scope",
            "eligibility_basis_id",
            "eligibility_basis__semantic_id",
            "eligibility_basis__procedure_version_id",
            "procedure_version_id",
            "effective_from",
            "effective_to",
            "verification_state",
            "verified_on",
            "reverify_on",
        )
    )
    fee_queryset = Fee.objects.filter(procedure_version__state__in=("published", "withdrawn"))
    if scope is not None:
        fee_queryset = fee_queryset.filter(procedure_version_id__in=scope.version_ids)
    fee_rows = list(
        fee_queryset.order_by(
            "procedure_version__semantic_id", "display_order", "semantic_id"
        ).values(
            "id",
            "procedure_version__semantic_id",
            "semantic_id",
            "text_ar",
            "text_en",
            "value_state",
            "amount",
            "minimum_amount",
            "maximum_amount",
            "currency",
            "fee_type",
            "display_order",
            "applicability",
            "scope",
            "eligibility_basis_id",
            "eligibility_basis__semantic_id",
            "eligibility_basis__procedure_version_id",
            "procedure_version_id",
            "effective_from",
            "effective_to",
            "verification_state",
            "verified_on",
            "reverify_on",
        )
    )
    warning_queryset = Warning.objects.filter(
        procedure_version__state__in=("published", "withdrawn")
    )
    if scope is not None:
        warning_queryset = warning_queryset.filter(procedure_version_id__in=scope.version_ids)
    warning_rows = list(
        warning_queryset.order_by(
            "procedure_version__semantic_id", "display_order", "semantic_id"
        ).values(
            "id",
            "procedure_version__semantic_id",
            "semantic_id",
            "text_ar",
            "text_en",
            "severity",
            "kind",
            "role",
            "display_order",
            "applicability",
            "effective_from",
            "effective_to",
            "verification_state",
            "verified_on",
            "reverify_on",
        )
    )
    evidence_rows = list(
        EvidenceLink.objects.filter(
            Q(checklist_item_id__in=[row["id"] for row in checklist_rows])
            | Q(step_id__in=[row["id"] for row in step_rows])
            | Q(fee_id__in=[row["id"] for row in fee_rows])
            | Q(warning_id__in=[row["id"] for row in warning_rows])
        )
        .order_by("id")
        .values(
            "id",
            "semantic_id",
            "checklist_item_id",
            "step_id",
            "fee_id",
            "warning_id",
            "passage",
            "location",
            "applicability_context",
            "support_status",
            "verification_state",
            "effective_from",
            "effective_to",
            "retrieved_on",
            "verified_on",
            "reverify_on",
        )
    )
    evidence_source_rows = list(
        EvidenceLinkSource.objects.filter(evidence_link_id__in=[row["id"] for row in evidence_rows])
        .order_by("evidence_link_id", "position", "source__semantic_id")
        .values(
            "evidence_link_id",
            "source__semantic_id",
            "source__title",
            "source__locator",
            "source__classification",
            "source__retrieved_on",
            "source__published_on",
            "source__effective_from",
            "source__effective_to",
            "source__reverify_on",
            "source__observation_date",
            "source__observation_context",
            "source__authority__semantic_id",
            "source__authority__name_ar",
            "source__authority__name_en",
        )
    )
    question_queryset = ServiceQuestion.objects.order_by("service__semantic_id", "semantic_id")
    if scope is not None:
        question_queryset = question_queryset.filter(service__semantic_id=scope.service_id)
    question_rows = list(
        question_queryset.values(
            "service__semantic_id",
            "semantic_id",
            "text_ar",
            "text_en",
            "priority",
            "fact__key",
        )
    )
    question_link_queryset = ServiceQuestionResolvedFact.objects.order_by(
        "question__semantic_id", "position", "fact__key"
    )
    if scope is not None:
        question_link_queryset = question_link_queryset.filter(
            question__service__semantic_id=scope.service_id
        )
    question_link_rows = list(question_link_queryset.values("question__semantic_id", "fact__key"))
    contradiction_queryset = ServiceContradiction.objects.order_by(
        "service__semantic_id", "semantic_id"
    )
    if scope is not None:
        contradiction_queryset = contradiction_queryset.filter(
            service__semantic_id=scope.service_id
        )
    contradiction_rows = list(
        contradiction_queryset.values("service__semantic_id", "semantic_id", "condition")
    )
    contradiction_link_queryset = ServiceContradictionFact.objects.order_by(
        "contradiction__semantic_id", "position", "fact__key"
    )
    if scope is not None:
        contradiction_link_queryset = contradiction_link_queryset.filter(
            contradiction__service__semantic_id=scope.service_id
        )
    contradiction_link_rows = list(
        contradiction_link_queryset.values("contradiction__semantic_id", "fact__key")
    )

    # Authoring adapters decode against every definition, but request-time planning crosses
    # a stricter publication boundary.  Unpublished definitions must neither validate caller
    # input nor make active public knowledge appear usable.
    definitions = MappingProxyType({row.key: to_domain_fact(row) for row in fact_rows})
    published_definitions = MappingProxyType(
        {row.key: to_domain_fact(row) for row in fact_rows if row.is_published}
    )
    question_links: dict[str, list[str]] = defaultdict(list)
    for question_link_row in question_link_rows:
        question_links[question_link_row["question__semantic_id"]].append(
            question_link_row["fact__key"]
        )
    contradiction_links: dict[str, list[str]] = defaultdict(list)
    for contradiction_link_row in contradiction_link_rows:
        contradiction_links[contradiction_link_row["contradiction__semantic_id"]].append(
            contradiction_link_row["fact__key"]
        )

    candidates: dict[str, list[ProcedureCandidateSnapshot]] = defaultdict(list)
    contradictions: dict[str, list[ContradictionSnapshot]] = defaultdict(list)
    versions: list[ProcedureVersionSnapshot] = []
    source_snapshots: dict[str, SourceSnapshot] = {}
    evidence_sources: dict[int, list[SourceSnapshot]] = defaultdict(list)
    for source_row in evidence_source_rows:
        source_id = source_row["source__semantic_id"]
        source = source_snapshots.setdefault(
            source_id,
            SourceSnapshot(
                source_id,
                AuthoritySnapshot(
                    source_row["source__authority__semantic_id"],
                    LocalizedText(
                        source_row["source__authority__name_ar"],
                        source_row["source__authority__name_en"],
                    ),
                ),
                source_row["source__title"],
                source_row["source__locator"],
                source_row["source__classification"],
                source_row["source__retrieved_on"],
                source_row["source__published_on"],
                source_row["source__effective_from"],
                source_row["source__effective_to"],
                source_row["source__reverify_on"],
                source_row["source__observation_date"],
                source_row["source__observation_context"],
            ),
        )
        evidence_sources[source_row["evidence_link_id"]].append(source)
    evidence_by_owner: dict[tuple[str, int], list[EvidenceLinkSnapshot]] = defaultdict(list)
    for evidence_row in cast(list[dict[str, Any]], evidence_rows):
        sources = tuple(evidence_sources[evidence_row["id"]])
        evidence_owner = core_evidence_owner(evidence_row)
        if evidence_owner is None:
            continue
        evidence_by_owner[evidence_owner].append(
            EvidenceLinkSnapshot(
                evidence_row["passage"],
                evidence_row["location"],
                evidence_row["applicability_context"],
                evidence_row["support_status"],
                cast(VerificationState, evidence_row["verification_state"]),
                sources,
                evidence_row["effective_from"],
                evidence_row["effective_to"],
                evidence_row["retrieved_on"],
                evidence_row["verified_on"],
                evidence_row["reverify_on"],
                semantic_id=evidence_row["semantic_id"],
            )
        )
    # Validate the captured graph once; construction below only consumes decoded rules.
    core_evidence = {
        owner: tuple(
            EvidenceInfo(
                link.passage,
                link.location,
                link.applicability_context,
                link.support_status,
                link.verification_state,
                tuple(
                    (source.classification, source.observation_date, source.observation_context)
                    for source in link.sources
                ),
            )
            for link in links
        )
        for owner, links in evidence_by_owner.items()
    }
    predicates = validate_core(
        CoreInputs(
            definitions,
            published_definitions,
            core_evidence,
            services=cast(list[ServiceRow], service_rows),
            checklist_items=cast(list[ClaimRow], checklist_rows),
            steps=cast(list[StepRow], step_rows),
            fees=cast(list[FeeRow], fee_rows),
            warnings=cast(list[WarningRow], warning_rows),
            candidates=cast(list[CandidateRow], candidate_rows),
            versions=cast(list[VersionRow], version_rows),
            contradictions=cast(list[ContradictionRow], contradiction_rows),
            contradiction_facts=contradiction_link_rows,
            questions=cast(list[QuestionRow], question_rows),
            question_facts=question_link_rows,
        )
    )
    checklist_by_version: dict[str, list[ChecklistItemSnapshot]] = defaultdict(list)
    for item_row in checklist_rows:
        version_id = item_row["procedure_version__semantic_id"]
        predicate = predicates.checklist_items[item_row["id"]]
        links = tuple(evidence_by_owner[("checklist_item", item_row["id"])])
        checklist_by_version[version_id].append(
            ChecklistItemSnapshot(
                item_row["semantic_id"],
                LocalizedText(item_row["text_ar"], item_row["text_en"]),
                item_row["classification"],
                item_row["document_type__semantic_id"],
                item_row["quantity"],
                item_row["original_quantity"],
                item_row["copy_quantity"],
                item_row["display_order"],
                predicate,
                item_row["scope"],
                item_row["scope_reference"],
                item_row["effective_from"],
                item_row["effective_to"],
                cast(VerificationState, item_row["verification_state"]),
                item_row["verified_on"],
                item_row["reverify_on"],
                links,
            )
        )

    bases_by_version: dict[str, list[EligibilityBasisSnapshot]] = defaultdict(list)
    for basis_row in basis_rows:
        bases_by_version[basis_row["procedure_version__semantic_id"]].append(
            EligibilityBasisSnapshot(basis_row["semantic_id"])
        )
    steps_by_version: dict[str, list[StepSnapshot]] = defaultdict(list)
    fees_by_version: dict[str, list[FeeSnapshot]] = defaultdict(list)
    warnings_by_version: dict[str, list[WarningSnapshot]] = defaultdict(list)

    for row in cast(list[dict[str, Any]], step_rows):
        guidance_predicate = predicates.steps[row["id"]]
        links = tuple(evidence_by_owner[("step", row["id"])])
        steps_by_version[row["procedure_version__semantic_id"]].append(
            StepSnapshot(
                row["semantic_id"],
                LocalizedText(row["text_ar"], row["text_en"]),
                row["phase"],
                row["phase_order"],
                row["slot"],
                guidance_predicate,
                row["scope"],
                row["eligibility_basis__semantic_id"],
                row["effective_from"],
                row["effective_to"],
                cast(VerificationState, row["verification_state"]),
                row["verified_on"],
                row["reverify_on"],
                links,
            )
        )

    for row in cast(list[dict[str, Any]], fee_rows):
        fee_predicate = predicates.fees[row["id"]]
        links = tuple(evidence_by_owner[("fee", row["id"])])
        fees_by_version[row["procedure_version__semantic_id"]].append(
            FeeSnapshot(
                row["semantic_id"],
                LocalizedText(row["text_ar"], row["text_en"]),
                row["value_state"],
                row["amount"],
                row["minimum_amount"],
                row["maximum_amount"],
                row["currency"],
                row["fee_type"],
                row["display_order"],
                fee_predicate,
                row["scope"],
                row["eligibility_basis__semantic_id"],
                row["effective_from"],
                row["effective_to"],
                cast(VerificationState, row["verification_state"]),
                row["verified_on"],
                row["reverify_on"],
                links,
            )
        )

    for row in cast(list[dict[str, Any]], warning_rows):
        guidance_predicate = predicates.warnings[row["id"]]
        links = tuple(evidence_by_owner[("warning", row["id"])])
        warnings_by_version[row["procedure_version__semantic_id"]].append(
            WarningSnapshot(
                row["semantic_id"],
                LocalizedText(row["text_ar"], row["text_en"]),
                row["severity"],
                row["kind"],
                row["role"],
                row["display_order"],
                guidance_predicate,
                row["effective_from"],
                row["effective_to"],
                cast(VerificationState, row["verification_state"]),
                row["verified_on"],
                row["reverify_on"],
                links,
            )
        )

    for candidate_row in candidate_rows:
        service_id = candidate_row["service__semantic_id"]
        procedure_id = candidate_row["procedure__semantic_id"]
        candidate_predicate = predicates.candidates[(service_id, procedure_id)]
        candidates[service_id].append(
            ProcedureCandidateSnapshot(
                procedure_id,
                LocalizedText(
                    candidate_row["procedure__text_ar"],
                    candidate_row["procedure__text_en"],
                ),
                candidate_predicate,
            )
        )
    for version_row in version_rows:
        semantic_id = version_row["semantic_id"]
        version_predicate = predicates.versions[semantic_id]
        versions.append(
            ProcedureVersionSnapshot(
                semantic_id,
                version_row["procedure__semantic_id"],
                LocalizedText(version_row["text_ar"], version_row["text_en"]),
                version_predicate,
                version_row["rules_contract_version"],
                version_row["state"],
                version_row["effective_from"],
                version_row["effective_to"],
                version_row["published_at"],
                version_row["published_by_id"],
                checklist_items=tuple(checklist_by_version[semantic_id]),
                eligibility_bases=tuple(bases_by_version[semantic_id]),
                steps=tuple(steps_by_version[semantic_id]),
                fees=tuple(fees_by_version[semantic_id]),
                warnings=tuple(warnings_by_version[semantic_id]),
            )
        )
    for contradiction_row in contradiction_rows:
        service_id = contradiction_row["service__semantic_id"]
        semantic_id = contradiction_row["semantic_id"]
        contradiction_predicate = predicates.contradictions[semantic_id]
        declared_keys = tuple(contradiction_links[semantic_id])
        contradictions[service_id].append(
            ContradictionSnapshot(semantic_id, contradiction_predicate, declared_keys)
        )

    questions: dict[str, list[QuestionSnapshot]] = defaultdict(list)
    for question_row in question_rows:
        service_id = question_row["service__semantic_id"]
        semantic_id = question_row["semantic_id"]
        primary_key = question_row["fact__key"]
        explicit_keys = question_links.get(semantic_id)
        resolved_keys = tuple(explicit_keys) if explicit_keys else (primary_key,)
        questions[service_id].append(
            QuestionSnapshot(
                semantic_id,
                LocalizedText(question_row["text_ar"], question_row["text_en"]),
                question_row["priority"],
                primary_key,
                resolved_keys,
            )
        )

    services = tuple(
        ServiceSnapshot(
            service_row["semantic_id"],
            LocalizedText(service_row["text_ar"], service_row["text_en"]),
            tuple(candidates[service_row["semantic_id"]]),
            tuple(questions[service_row["semantic_id"]]),
            tuple(contradictions[service_row["semantic_id"]]),
            is_active=service_row["is_active"],
        )
        for service_row in service_rows
    )
    return KnowledgeSnapshot(published_definitions, services, tuple(versions))


def _materialize_knowledge_snapshot(
    scope: Any | None = None, *, evaluation_date: date | None = None
) -> KnowledgeSnapshot:
    """Compose a complete or explicitly service-scoped semantic snapshot."""

    # Import at call time to avoid cycles during Django's feature-model registration.
    from .eligibility_bases import _basis_snapshots
    from .procedure_dependencies import _dependency_snapshots
    from .service_point_routing import _routing_snapshots

    if scope is not None:
        # Scoped materialization retains the full request-time integrity ledger, but never
        # constructs and discards unrelated semantic DTOs.
        from .snapshot_validation import validate_global_catalog

        validate_global_catalog(evaluation_date)
    snapshot = _materialize_core_knowledge_snapshot(scope)
    snapshot = _basis_snapshots(snapshot, scope=scope)
    snapshot = _dependency_snapshots(snapshot, scope=scope)
    return _routing_snapshots(snapshot, scope=scope)


def load_knowledge_snapshot() -> KnowledgeSnapshot:
    """Load a detached snapshot without imposing a transaction policy."""

    return _materialize_knowledge_snapshot()


def load_consistent_knowledge_snapshot() -> KnowledgeSnapshot:
    """Load all published knowledge in one outermost read-only repeatable-read transaction."""

    from django.db import connection, transaction

    if connection.in_atomic_block:
        raise RuntimeError("a consistent knowledge snapshot requires an outermost transaction")
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        return _materialize_knowledge_snapshot()
