"""Immutable, framework-free snapshots of the persisted planning catalog.

Snapshots contain decoded planning-domain values only; loading and all ORM access belong
in the knowledge adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from types import MappingProxyType

from .facts import FactDefinition
from .rules import Predicate
from .trust import VerificationState


@dataclass(frozen=True, slots=True)
class LocalizedText:
    ar: str
    en: str


@dataclass(frozen=True, slots=True)
class ProcedureCandidateSnapshot:
    procedure_semantic_id: str
    text: LocalizedText
    selection_predicate: Predicate


@dataclass(frozen=True, slots=True)
class QuestionSnapshot:
    semantic_id: str
    text: LocalizedText
    priority: int
    primary_fact_key: str
    resolved_fact_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "resolved_fact_keys", tuple(self.resolved_fact_keys))


@dataclass(frozen=True, slots=True)
class ContradictionSnapshot:
    semantic_id: str
    condition: Predicate
    fact_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "fact_keys", tuple(self.fact_keys))


@dataclass(frozen=True, slots=True)
class ServiceSnapshot:
    semantic_id: str
    text: LocalizedText
    candidates: tuple[ProcedureCandidateSnapshot, ...]
    questions: tuple[QuestionSnapshot, ...]
    contradictions: tuple[ContradictionSnapshot, ...]
    is_active: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "questions", tuple(self.questions))
        object.__setattr__(self, "contradictions", tuple(self.contradictions))


@dataclass(frozen=True, slots=True)
class AuthoritySnapshot:
    semantic_id: str
    name: LocalizedText


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    semantic_id: str
    authority: AuthoritySnapshot
    title: str
    locator: str
    classification: str
    retrieved_on: date
    published_on: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    reverify_on: date | None = None
    observation_date: date | None = None
    observation_context: str = ""


@dataclass(frozen=True, slots=True)
class EvidenceLinkSnapshot:
    passage: str
    location: str
    applicability_context: str
    support_status: str
    verification_state: VerificationState
    sources: tuple[SourceSnapshot, ...]
    effective_from: date | None = None
    effective_to: date | None = None
    retrieved_on: date | None = None
    verified_on: date | None = None
    reverify_on: date | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))


@dataclass(frozen=True, slots=True)
class ChecklistItemSnapshot:
    semantic_id: str
    text: LocalizedText
    classification: str
    document_type_id: str | None
    quantity: int
    original_quantity: int
    copy_quantity: int
    display_order: int
    applicability: Predicate | None
    scope: str
    scope_reference: str
    effective_from: date | None
    effective_to: date | None
    verification_state: VerificationState
    verified_on: date | None
    reverify_on: date | None
    evidence_links: tuple[EvidenceLinkSnapshot, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


@dataclass(frozen=True, slots=True)
class EligibilityBasisSnapshot:
    semantic_id: str


@dataclass(frozen=True, slots=True)
class StepSnapshot:
    semantic_id: str
    text: LocalizedText
    phase: str
    phase_order: int
    slot: int
    applicability: Predicate | None
    scope: str
    eligibility_basis_id: str | None
    effective_from: date | None
    effective_to: date | None
    verification_state: VerificationState
    verified_on: date | None
    reverify_on: date | None
    evidence_links: tuple[EvidenceLinkSnapshot, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


@dataclass(frozen=True, slots=True)
class FeeSnapshot:
    semantic_id: str
    text: LocalizedText
    value_state: str
    amount: int | None
    minimum_amount: int | None
    maximum_amount: int | None
    currency: str
    fee_type: str
    display_order: int
    applicability: Predicate | None
    scope: str
    eligibility_basis_id: str | None
    effective_from: date | None
    effective_to: date | None
    verification_state: VerificationState
    verified_on: date | None
    reverify_on: date | None
    evidence_links: tuple[EvidenceLinkSnapshot, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


@dataclass(frozen=True, slots=True)
class WarningSnapshot:
    semantic_id: str
    text: LocalizedText
    severity: str
    kind: str
    role: str
    display_order: int
    applicability: Predicate | None
    effective_from: date | None
    effective_to: date | None
    verification_state: VerificationState
    verified_on: date | None
    reverify_on: date | None
    evidence_links: tuple[EvidenceLinkSnapshot, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_links", tuple(self.evidence_links))


@dataclass(frozen=True, slots=True)
class ProcedureVersionSnapshot:
    semantic_id: str
    procedure_semantic_id: str
    text: LocalizedText
    applicability: Predicate
    rules_contract_version: str
    state: str
    effective_from: date | None
    effective_to: date | None
    published_at: datetime | None = None
    published_by_id: int | None = None
    checklist_items: tuple[ChecklistItemSnapshot, ...] = ()
    eligibility_bases: tuple[EligibilityBasisSnapshot, ...] = ()
    steps: tuple[StepSnapshot, ...] = ()
    fees: tuple[FeeSnapshot, ...] = ()
    warnings: tuple[WarningSnapshot, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "checklist_items", tuple(self.checklist_items))
        object.__setattr__(self, "eligibility_bases", tuple(self.eligibility_bases))
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "fees", tuple(self.fees))
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True, slots=True)
class KnowledgeSnapshot:
    fact_definitions: Mapping[str, FactDefinition]
    services: tuple[ServiceSnapshot, ...]
    procedure_versions: tuple[ProcedureVersionSnapshot, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "fact_definitions", MappingProxyType(dict(self.fact_definitions)))
        object.__setattr__(self, "services", tuple(self.services))
        object.__setattr__(self, "procedure_versions", tuple(self.procedure_versions))
