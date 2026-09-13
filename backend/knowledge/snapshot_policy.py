"""Pure request-time snapshot integrity policy (not the publication gate).

Adapters supply captured scalar projections and explicit Fact registries. No ORM or
planning snapshot construction belongs here. Equal-owner diagnostics retain check order.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import TypedDict

from planning.diagnostics import ValidationDiagnostic
from planning.facts import FACT_DEFINITIONS, FactDefinition
from planning.rules import Predicate, validate_rule_v1


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


@dataclass(frozen=True, slots=True)
class EvidenceInfo:
    """Shared scalar provenance summary; feature policies retain their own adequacy rules."""

    passage: str
    location: str
    applicability_context: str
    support_status: str
    verification_state: str
    sources: tuple[tuple[str, date | None, str], ...]


class EvidenceRow(TypedDict):
    id: int
    passage: str
    location: str
    applicability_context: str
    support_status: str
    verification_state: str


class EvidenceSourceRow(TypedDict):
    evidence_link_id: int
    source__classification: str
    source__observation_date: date | None
    source__observation_context: str


def summarize_evidence_rows(
    rows: Sequence[EvidenceRow], sources: Sequence[EvidenceSourceRow]
) -> Mapping[int, EvidenceInfo]:
    """Map captured scalar provenance without constructing planning DTOs or choosing owners."""
    by_link: dict[int, list[tuple[str, date | None, str]]] = {}
    for source in sources:
        by_link.setdefault(source["evidence_link_id"], []).append(
            (
                source["source__classification"],
                source["source__observation_date"],
                source["source__observation_context"],
            )
        )
    return {
        row["id"]: EvidenceInfo(
            row["passage"],
            row["location"],
            row["applicability_context"],
            row["support_status"],
            row["verification_state"],
            tuple(by_link.get(row["id"], ())),
        )
        for row in rows
    }


CORE_OWNER_FIELDS = ("checklist_item", "step", "fee", "warning")


def core_evidence_owner(row: Mapping[str, object]) -> tuple[str, int] | None:
    """First core owner only; independent feature and routing owners are not normalized."""
    for field in CORE_OWNER_FIELDS:
        owner_id = row[f"{field}_id"]
        if owner_id is not None:
            assert isinstance(owner_id, int)
            return field, owner_id
    return None


def routing_evidence_owner(row: Mapping[str, object]) -> tuple[str, int] | None:
    """Association wins over material; unrelated to workflow owner validation."""
    for field in ("procedure_service_point_association", "service_point_version"):
        owner_id = row[f"{field}_id"]
        if owner_id is not None:
            assert isinstance(owner_id, int)
            return field, owner_id
    return None


class ServiceRow(TypedDict):
    semantic_id: str
    is_active: bool


class ClaimRow(TypedDict):
    id: int
    procedure_version__semantic_id: str
    semantic_id: str
    applicability: object
    verification_state: str


class StepRow(ClaimRow):
    scope: str
    eligibility_basis_id: int | None
    eligibility_basis__procedure_version_id: int | None
    procedure_version_id: int


class FeeRow(StepRow):
    currency: str
    fee_type: str
    value_state: str
    amount: int | None
    minimum_amount: int | None
    maximum_amount: int | None


class WarningRow(ClaimRow):
    kind: str


class CandidateRow(TypedDict):
    service__semantic_id: str
    procedure__semantic_id: str
    selection_predicate: object


class VersionRow(TypedDict):
    semantic_id: str
    applicability: object


class ContradictionRow(TypedDict):
    semantic_id: str
    service__semantic_id: str
    condition: object


class ContradictionFactRow(TypedDict):
    contradiction__semantic_id: str
    fact__key: str


class QuestionRow(TypedDict):
    semantic_id: str
    service__semantic_id: str
    fact__key: str


class QuestionFactRow(TypedDict):
    question__semantic_id: str
    fact__key: str


@dataclass(frozen=True, slots=True)
class CoreInputs:
    definitions: Mapping[str, FactDefinition]
    published_definitions: Mapping[str, FactDefinition]
    evidence: Mapping[tuple[str, int], tuple[EvidenceInfo, ...]]
    services: Sequence[ServiceRow] = ()
    checklist_items: Sequence[ClaimRow] = ()
    steps: Sequence[StepRow] = ()
    fees: Sequence[FeeRow] = ()
    warnings: Sequence[WarningRow] = ()
    candidates: Sequence[CandidateRow] = ()
    versions: Sequence[VersionRow] = ()
    contradictions: Sequence[ContradictionRow] = ()
    contradiction_facts: Sequence[ContradictionFactRow] = ()
    questions: Sequence[QuestionRow] = ()
    question_facts: Sequence[QuestionFactRow] = ()


def _adequate(links: tuple[EvidenceInfo, ...]) -> bool:
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


def _valid_fee_shape(row: FeeRow) -> bool:
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


@dataclass(frozen=True, slots=True)
class DecodedCoreRules:
    """Decoded rules keyed by structural identity, never formatted diagnostics."""

    checklist_items: Mapping[int, Predicate | None]
    steps: Mapping[int, Predicate | None]
    fees: Mapping[int, Predicate | None]
    warnings: Mapping[int, Predicate | None]
    candidates: Mapping[tuple[str, str], Predicate]
    versions: Mapping[str, Predicate]
    contradictions: Mapping[str, Predicate]


def validate_core(data: CoreInputs) -> DecodedCoreRules:
    """Validate the complete core stage, returning decoded predicates by stable identity.

    None denotes an omitted optional guidance rule, never a failed decode. Mandatory
    candidate/version/contradiction entries always contain a Predicate on success.
    """
    failures: list[StoredRuleLoadDiagnostic] = []
    checklist_items: dict[int, Predicate | None] = {}
    steps: dict[int, Predicate | None] = {}
    fees: dict[int, Predicate | None] = {}
    warnings: dict[int, Predicate | None] = {}
    candidates: dict[tuple[str, str], Predicate] = {}
    versions: dict[str, Predicate] = {}
    contradictions: dict[str, Predicate] = {}

    def fail(owner: str, code: str, path: tuple[str | int, ...]) -> None:
        failures.append(StoredRuleLoadDiagnostic(owner, (ValidationDiagnostic(code, path),)))

    def decode[K](
        owner: str,
        raw: object,
        definitions: Mapping[str, FactDefinition],
        target: dict[K, Predicate],
        key: K,
    ) -> bool:
        result = validate_rule_v1(raw, definitions=definitions)
        if result.predicate is None:
            failures.append(StoredRuleLoadDiagnostic(owner, result.diagnostics))
            return False
        target[key] = result.predicate
        return True

    def guidance(owner: str, row: ClaimRow, target: dict[int, Predicate | None]) -> bool:
        if row["applicability"] == {}:
            target[row["id"]] = None
            return True
        result = validate_rule_v1(row["applicability"], definitions=data.published_definitions)
        if result.predicate is None:
            failures.append(StoredRuleLoadDiagnostic(owner, result.diagnostics))
            return False
        target[row["id"]] = result.predicate
        return True

    def broken_basis(row: StepRow) -> bool:
        return row["scope"] == "eligibility_basis" and (
            row["eligibility_basis_id"] is None
            or row["eligibility_basis__procedure_version_id"] != row["procedure_version_id"]
        )

    def unpublished(owner: str, keys: Iterable[str]) -> None:
        missing = sorted(set(keys) - data.published_definitions.keys())
        if missing:
            failures.append(
                StoredRuleLoadDiagnostic(
                    owner,
                    tuple(
                        ValidationDiagnostic("unpublished_fact", ("facts", key)) for key in missing
                    ),
                )
            )

    for fact in data.published_definitions.values():
        if fact.derived and fact != FACT_DEFINITIONS.get(fact.key):
            fail(f"fact:{fact.key}", "unsupported_derived_fact", ("facts", fact.key))

    active = {row["semantic_id"] for row in data.services if row["is_active"]}
    for item in data.checklist_items:
        owner = f"checklist_item:{item['procedure_version__semantic_id']}:{item['semantic_id']}"
        if not guidance(owner, item, checklist_items):
            continue
        links = data.evidence.get(("checklist_item", item["id"]), ())
        if item["verification_state"] == "current" and not links:
            fail(owner, "missing_evidence_link", ("evidence",))
        elif any(not link.sources for link in links):
            fail(owner, "missing_evidence_source", ("evidence",))

    for step in data.steps:
        owner = f"step:{step['procedure_version__semantic_id']}:{step['semantic_id']}"
        valid_rule = guidance(owner, step, steps)
        if broken_basis(step):
            fail(owner, "invalid_basis_owner", ("scope",))
        elif (
            valid_rule
            and step["verification_state"] == "current"
            and not _adequate(data.evidence.get(("step", step["id"]), ()))
        ):
            fail(owner, "inadequate_evidence", ("evidence",))

    for fee in data.fees:
        owner = f"fee:{fee['procedure_version__semantic_id']}:{fee['semantic_id']}"
        if not guidance(owner, fee, fees):
            continue
        links = data.evidence.get(("fee", fee["id"]), ())
        evidence_required = fee["value_state"] in {"known", "range", "unverified"}
        current_support_required = (
            fee["value_state"] in {"known", "range"} and fee["verification_state"] == "current"
        )
        if broken_basis(fee):
            fail(owner, "invalid_basis_owner", ("scope",))
        elif not fee["currency"].strip():
            fail(owner, "missing_currency", ("currency",))
        elif not fee["fee_type"].strip():
            fail(owner, "missing_fee_type", ("fee_type",))
        elif not _valid_fee_shape(fee):
            fail(owner, "invalid_fee_value", ("value_state",))
        elif evidence_required and not links:
            fail(owner, "missing_evidence_link", ("evidence",))
        elif evidence_required and any(not link.sources for link in links):
            fail(owner, "missing_evidence_source", ("evidence",))
        elif current_support_required and not _adequate(links):
            fail(owner, "inadequate_evidence", ("evidence",))

    for warning in data.warnings:
        owner = f"warning:{warning['procedure_version__semantic_id']}:{warning['semantic_id']}"
        guidance(owner, warning, warnings)
        links = data.evidence.get(("warning", warning["id"]), ())
        if (warning["kind"] == "product" and bool(links)) or (
            warning["kind"] == "administrative"
            and warning["verification_state"] == "current"
            and not _adequate(links)
        ):
            fail(owner, "invalid_warning_evidence", ("evidence",))

    for candidate in data.candidates:
        service = candidate["service__semantic_id"]
        decode(
            f"candidate:{service}:{candidate['procedure__semantic_id']}",
            candidate["selection_predicate"],
            data.published_definitions if service in active else data.definitions,
            candidates,
            (service, candidate["procedure__semantic_id"]),
        )
    for version in data.versions:
        decode(
            f"procedure_version:{version['semantic_id']}",
            version["applicability"],
            data.published_definitions,
            versions,
            version["semantic_id"],
        )

    declared: dict[str, list[str]] = {}
    for link in data.contradiction_facts:
        declared.setdefault(link["contradiction__semantic_id"], []).append(link["fact__key"])
    for contradiction in data.contradictions:
        service = contradiction["service__semantic_id"]
        owner = f"contradiction:{contradiction['semantic_id']}"
        if (
            decode(
                owner,
                contradiction["condition"],
                data.published_definitions if service in active else data.definitions,
                contradictions,
                contradiction["semantic_id"],
            )
            and service in active
        ):
            unpublished(owner, declared.get(contradiction["semantic_id"], ()))

    resolved: dict[str, list[str]] = {}
    for question_link in data.question_facts:
        resolved.setdefault(question_link["question__semantic_id"], []).append(
            question_link["fact__key"]
        )
    for question in data.questions:
        if question["service__semantic_id"] in active:
            unpublished(
                f"question:{question['semantic_id']}",
                (question["fact__key"], *resolved.get(question["semantic_id"], ())),
            )
    if failures:
        raise KnowledgeSnapshotLoadError(failures)
    return DecodedCoreRules(
        MappingProxyType(checklist_items),
        MappingProxyType(steps),
        MappingProxyType(fees),
        MappingProxyType(warnings),
        MappingProxyType(candidates),
        MappingProxyType(versions),
        MappingProxyType(contradictions),
    )


class BasisRow(TypedDict):
    id: int
    procedure_version__semantic_id: str
    semantic_id: str
    text_ar: str
    text_en: str
    reachability: object
    qualification: object


class DependencyRow(TypedDict):
    id: int
    procedure_version__semantic_id: str
    procedure_version__procedure_id: int
    target_procedure_id: int
    semantic_id: str
    text_ar: str
    text_en: str
    relation: str
    applicability: object
    satisfied_when: object


class AssociationRow(ClaimRow):
    service_point_version_id: int


class MaterialRow(TypedDict):
    id: int
    semantic_id: str
    address_ar: str
    address_en: str
    availability: str
    verification_state: str


@dataclass(frozen=True, slots=True)
class DecodedBasisRules:
    reachability: Predicate | None
    qualification: Predicate


@dataclass(frozen=True, slots=True)
class DecodedDependencyRules:
    applicability: Predicate | None
    satisfied_when: Predicate


@dataclass(frozen=True, slots=True)
class DecodedRoutingRules:
    associations: Mapping[int, Predicate]


EvidenceIndex = Mapping[tuple[str, int], tuple[EvidenceInfo, ...]]


def _failure(owner: str, code: str, path: tuple[str | int, ...]) -> StoredRuleLoadDiagnostic:
    return StoredRuleLoadDiagnostic(owner, (ValidationDiagnostic(code, path),))


def validate_bases(
    rows: Sequence[BasisRow], definitions: Mapping[str, FactDefinition], evidence: EvidenceIndex
) -> Mapping[int, DecodedBasisRules]:
    """Reachability failure suppresses qualification, which suppresses evidence checks."""
    failures: list[StoredRuleLoadDiagnostic] = []
    rules: dict[int, DecodedBasisRules] = {}
    for row in rows:
        owner = f"eligibility_basis:{row['procedure_version__semantic_id']}:{row['semantic_id']}"
        reachability: Predicate | None = None
        if row["reachability"] != {}:
            decoded = validate_rule_v1(row["reachability"], definitions=definitions)
            if decoded.predicate is None:
                failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
                continue
            reachability = decoded.predicate
        if row["qualification"] == {}:
            failures.append(_failure(owner, "missing_qualification", ("qualification",)))
            continue
        decoded = validate_rule_v1(row["qualification"], definitions=definitions)
        if decoded.predicate is None:
            failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
            continue
        links = evidence.get(("eligibility_basis", row["id"]), ())
        if (
            not row["text_ar"].strip()
            or not row["text_en"].strip()
            or not links
            or any(not link.sources for link in links)
        ):
            failures.append(_failure(owner, "invalid_basis_evidence", ("evidence",)))
            continue
        rules[row["id"]] = DecodedBasisRules(reachability, decoded.predicate)
    if failures:
        raise KnowledgeSnapshotLoadError(failures)
    return MappingProxyType(rules)


def validate_dependencies(
    rows: Sequence[DependencyRow],
    definitions: Mapping[str, FactDefinition],
    evidence: EvidenceIndex,
) -> Mapping[int, DecodedDependencyRules]:
    failures: list[StoredRuleLoadDiagnostic] = []
    rules: dict[int, DecodedDependencyRules] = {}
    for row in rows:
        owner = f"procedure_dependency:{row['procedure_version__semantic_id']}:{row['semantic_id']}"
        if row["relation"] != "blocking_prerequisite":
            failures.append(_failure(owner, "unsupported_dependency_relation", ("relation",)))
            continue
        if row["procedure_version__procedure_id"] == row["target_procedure_id"]:
            failures.append(_failure(owner, "self_dependency", ("target_procedure",)))
            continue
        applicability: Predicate | None = None
        if row["applicability"] != {}:
            decoded = validate_rule_v1(row["applicability"], definitions=definitions)
            if decoded.predicate is None:
                failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
                continue
            applicability = decoded.predicate
        if row["satisfied_when"] == {}:
            failures.append(_failure(owner, "missing_satisfied_when", ("satisfied_when",)))
            continue
        decoded = validate_rule_v1(row["satisfied_when"], definitions=definitions)
        if decoded.predicate is None:
            failures.append(StoredRuleLoadDiagnostic(owner, decoded.diagnostics))
            continue
        links = evidence.get(("procedure_dependency", row["id"]), ())
        if (
            not row["text_ar"].strip()
            or not row["text_en"].strip()
            or not links
            or any(not link.sources for link in links)
        ):
            failures.append(_failure(owner, "invalid_dependency_evidence", ("evidence",)))
            continue
        rules[row["id"]] = DecodedDependencyRules(applicability, decoded.predicate)
    if failures:
        raise KnowledgeSnapshotLoadError(failures)
    return MappingProxyType(rules)


def _routing_evidence_is_adequate(links: tuple[EvidenceInfo, ...]) -> bool:
    # Unlike core adequacy, every extra link must have complete details, including
    # contextual Field Reports. Do not reuse the weaker core support predicate.
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


def validate_routing(
    associations: Sequence[AssociationRow],
    materials: Sequence[MaterialRow],
    definitions: Mapping[str, FactDefinition],
    evidence: EvidenceIndex,
) -> DecodedRoutingRules:
    failures: list[StoredRuleLoadDiagnostic] = []
    rules: dict[int, Predicate] = {}
    for row in associations:
        owner = (
            f"service_point_association:{row['procedure_version__semantic_id']}:"
            f"{row['semantic_id']}"
        )
        decoded = validate_rule_v1(row["applicability"], definitions=definitions)
        links = evidence.get(("procedure_service_point_association", row["id"]), ())
        if (
            decoded.predicate is None
            or not links
            or any(not link.sources for link in links)
            or (row["verification_state"] == "current" and not _routing_evidence_is_adequate(links))
        ):
            failures.append(
                StoredRuleLoadDiagnostic(
                    owner,
                    decoded.diagnostics
                    or (ValidationDiagnostic("invalid_routing_evidence", ("evidence",)),),
                )
            )
            continue
        rules[row["id"]] = decoded.predicate
    for material in materials:
        links = evidence.get(("service_point_version", material["id"]), ())
        if (
            not material["address_ar"].strip()
            or not material["address_en"].strip()
            or material["availability"] not in ("available", "unknown")
            or not links
            or any(not link.sources for link in links)
            or (
                material["verification_state"] == "current"
                and not _routing_evidence_is_adequate(links)
            )
        ):
            failures.append(
                _failure(
                    f"service_point_version:{material['semantic_id']}",
                    "invalid_service_point_material",
                    (),
                )
            )
    if failures:
        raise KnowledgeSnapshotLoadError(failures)
    return DecodedRoutingRules(MappingProxyType(rules))
