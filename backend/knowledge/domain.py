"""Adapters between persisted catalog rows and the ORM-free planning domain."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from planning.catalog import (
    ContradictionSnapshot,
    KnowledgeSnapshot,
    LocalizedText,
    ProcedureCandidateSnapshot,
    ProcedureVersionSnapshot,
    QuestionSnapshot,
    ServiceSnapshot,
)
from planning.diagnostics import ValidationDiagnostic
from planning.facts import FACT_DEFINITIONS, FactKind
from planning.facts import FactDefinition as DomainFactDefinition
from planning.rules import Predicate, RuleValidationResult, validate_rule_v1

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


@dataclass(frozen=True, slots=True)
class StoredRuleLoadDiagnostic:
    owner_id: str
    diagnostics: tuple[ValidationDiagnostic, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


class KnowledgeSnapshotLoadError(Exception):
    """A deterministic failure to decode one or more persisted catalog rules."""

    def __init__(self, rule_diagnostics: Iterable[StoredRuleLoadDiagnostic]) -> None:
        ordered = tuple(sorted(rule_diagnostics, key=lambda item: item.owner_id))
        self.rule_diagnostics = ordered
        self.owner_ids = tuple(item.owner_id for item in ordered)
        super().__init__(", ".join(self.owner_ids))


def _materialize_knowledge_snapshot() -> KnowledgeSnapshot:
    """Fully evaluate ORM reads, then return an immutable, ORM-free catalog graph."""

    from .models import (
        FactDefinition,
        ProcedureVersion,
        Service,
        ServiceContradiction,
        ServiceContradictionFact,
        ServiceProcedureCandidate,
        ServiceQuestion,
        ServiceQuestionResolvedFact,
    )

    # Every queryset is explicitly ordered and immediately materialized.  The remaining
    # work below uses only plain values and planning-domain objects.
    fact_rows = list(FactDefinition.objects.order_by("key"))
    service_rows = list(
        Service.objects.order_by("semantic_id").values(
            "semantic_id", "text_ar", "text_en", "is_active"
        )
    )
    candidate_rows = list(
        ServiceProcedureCandidate.objects.order_by(
            "service__semantic_id", "procedure__semantic_id"
        ).values(
            "service__semantic_id",
            "procedure__semantic_id",
            "procedure__text_ar",
            "procedure__text_en",
            "selection_predicate",
        )
    )
    version_rows = list(
        ProcedureVersion.objects.filter(
            state__in=(ProcedureVersion.State.PUBLISHED, ProcedureVersion.State.WITHDRAWN)
        )
        .order_by("procedure__semantic_id", "semantic_id")
        .values(
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
    question_rows = list(
        ServiceQuestion.objects.order_by("service__semantic_id", "semantic_id").values(
            "service__semantic_id",
            "semantic_id",
            "text_ar",
            "text_en",
            "priority",
            "fact__key",
        )
    )
    question_link_rows = list(
        ServiceQuestionResolvedFact.objects.order_by(
            "question__semantic_id", "position", "fact__key"
        ).values("question__semantic_id", "fact__key")
    )
    contradiction_rows = list(
        ServiceContradiction.objects.order_by("service__semantic_id", "semantic_id").values(
            "service__semantic_id", "semantic_id", "condition"
        )
    )
    contradiction_link_rows = list(
        ServiceContradictionFact.objects.order_by(
            "contradiction__semantic_id", "position", "fact__key"
        ).values("contradiction__semantic_id", "fact__key")
    )

    # Authoring adapters decode against every definition, but request-time planning crosses
    # a stricter publication boundary.  Unpublished definitions must neither validate caller
    # input nor make active public knowledge appear usable.
    definitions = MappingProxyType({row.key: to_domain_fact(row) for row in fact_rows})
    published_definitions = MappingProxyType(
        {row.key: to_domain_fact(row) for row in fact_rows if row.is_published}
    )
    active_service_ids = {row["semantic_id"] for row in service_rows if row["is_active"]}
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
    failures: list[StoredRuleLoadDiagnostic] = []
    # Database bypasses must not turn catalog-authored metadata into executable derivation.
    # Only exact, production-pinned derived definitions may cross the public snapshot boundary.
    for row in fact_rows:
        if not row.is_published or not row.derived:
            continue
        expected = FACT_DEFINITIONS.get(row.key)
        if expected is None or not expected.derived or compatibility_errors((row,)):
            failures.append(
                StoredRuleLoadDiagnostic(
                    f"fact:{row.key}",
                    (ValidationDiagnostic("unsupported_derived_fact", ("facts", row.key)),),
                )
            )

    for candidate_row in candidate_rows:
        service_id = candidate_row["service__semantic_id"]
        procedure_id = candidate_row["procedure__semantic_id"]
        owner_definitions = (
            published_definitions if service_id in active_service_ids else definitions
        )
        decoded = decode_stored_rule(candidate_row["selection_predicate"], owner_definitions)
        if decoded.predicate is None:
            failures.append(
                StoredRuleLoadDiagnostic(
                    f"candidate:{service_id}:{procedure_id}", decoded.diagnostics
                )
            )
            continue
        candidates[service_id].append(
            ProcedureCandidateSnapshot(
                procedure_id,
                LocalizedText(
                    candidate_row["procedure__text_ar"],
                    candidate_row["procedure__text_en"],
                ),
                decoded.predicate,
            )
        )
    for version_row in version_rows:
        semantic_id = version_row["semantic_id"]
        decoded = decode_stored_rule(version_row["applicability"], published_definitions)
        if decoded.predicate is None:
            failures.append(
                StoredRuleLoadDiagnostic(f"procedure_version:{semantic_id}", decoded.diagnostics)
            )
            continue
        versions.append(
            ProcedureVersionSnapshot(
                semantic_id,
                version_row["procedure__semantic_id"],
                LocalizedText(version_row["text_ar"], version_row["text_en"]),
                decoded.predicate,
                version_row["rules_contract_version"],
                version_row["state"],
                version_row["effective_from"],
                version_row["effective_to"],
                version_row["published_at"],
                version_row["published_by_id"],
            )
        )
    for contradiction_row in contradiction_rows:
        service_id = contradiction_row["service__semantic_id"]
        semantic_id = contradiction_row["semantic_id"]
        owner_definitions = (
            published_definitions if service_id in active_service_ids else definitions
        )
        decoded = decode_stored_rule(contradiction_row["condition"], owner_definitions)
        if decoded.predicate is None:
            failures.append(
                StoredRuleLoadDiagnostic(f"contradiction:{semantic_id}", decoded.diagnostics)
            )
            continue
        declared_keys = tuple(contradiction_links[semantic_id])
        if service_id in active_service_ids:
            unpublished_keys = sorted(set(declared_keys) - published_definitions.keys())
            if unpublished_keys:
                failures.append(
                    StoredRuleLoadDiagnostic(
                        f"contradiction:{semantic_id}",
                        tuple(
                            ValidationDiagnostic("unpublished_fact", ("facts", key))
                            for key in unpublished_keys
                        ),
                    )
                )
                continue
        contradictions[service_id].append(
            ContradictionSnapshot(semantic_id, decoded.predicate, declared_keys)
        )

    questions: dict[str, list[QuestionSnapshot]] = defaultdict(list)
    for question_row in question_rows:
        service_id = question_row["service__semantic_id"]
        semantic_id = question_row["semantic_id"]
        primary_key = question_row["fact__key"]
        explicit_keys = question_links.get(semantic_id)
        resolved_keys = tuple(explicit_keys) if explicit_keys else (primary_key,)
        if service_id in active_service_ids:
            unpublished_keys = sorted({primary_key, *resolved_keys} - published_definitions.keys())
            if unpublished_keys:
                failures.append(
                    StoredRuleLoadDiagnostic(
                        f"question:{semantic_id}",
                        tuple(
                            ValidationDiagnostic("unpublished_fact", ("facts", key))
                            for key in unpublished_keys
                        ),
                    )
                )
                continue
        questions[service_id].append(
            QuestionSnapshot(
                semantic_id,
                LocalizedText(question_row["text_ar"], question_row["text_en"]),
                question_row["priority"],
                primary_key,
                resolved_keys,
            )
        )

    if failures:
        raise KnowledgeSnapshotLoadError(failures)

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
