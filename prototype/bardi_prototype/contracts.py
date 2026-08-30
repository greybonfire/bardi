from __future__ import annotations
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Literal, Mapping

Locale = Literal["ar", "en"]
VerificationState = Literal["current", "needs_reverification", "unknown"]
FactKind = Literal["enum", "integer", "boolean", "date", "string"]
ChecklistClassification = Literal[
    "official_requirement",
    "practical_preparation",
    "official_requirement_candidate",
    "legal_basis_candidate",
]
ChecklistScope = Literal["shared", "eligibility_basis"]
FeeValueState = Literal["known", "range", "unknown", "unverified"]
WarningKind = Literal["administrative", "product"]
WarningRole = Literal["general", "regeneration", "limitation"]
DependencyRelation = Literal["blocking_prerequisite"]
DependencyStatus = Literal["satisfied", "blocking", "unsupported_target"]
ServicePointAvailability = Literal["available", "unknown"]
RoutingStatus = Literal["resolved", "partially_resolved", "unresolved"]


@dataclass(frozen=True)
class LocalizedText:
    ar: str
    en: str

    def render(self, locale: Locale) -> str:
        return self.ar if locale == "ar" else self.en


@dataclass(frozen=True)
class NamedDefinition:
    id: str
    text: LocalizedText


@dataclass(frozen=True)
class GoalDefinition(NamedDefinition):
    procedure_ids: tuple[str, ...]


@dataclass(frozen=True)
class Source:
    id: str
    authority: str
    title: str
    retrieved_on: date


@dataclass(frozen=True)
class EvidenceLink:
    id: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class Predicate:
    op: str
    fact: str | None = None
    value: object | None = None
    children: tuple["Predicate", ...] = ()


@dataclass(frozen=True)
class FactDefinition:
    key: str
    kind: FactKind
    enum_values: tuple[str, ...] = ()
    minimum: int | None = None
    derived: bool = False


@dataclass(frozen=True)
class ProcedureVersionDefinition:
    procedure_id: str
    version_id: str
    text: LocalizedText
    applicability: Predicate
    verified_on: date


@dataclass(frozen=True)
class VerificationPathDefinition:
    id: str
    text: LocalizedText
    evidence_link_ids: tuple[str, ...]


@dataclass(frozen=True)
class EligibilityBasisDefinition:
    id: str
    text: LocalizedText
    applicability: Predicate
    evidence_link_ids: tuple[str, ...]
    verification_state: VerificationState
    display_order: int


@dataclass(frozen=True)
class ClaimDefinition:
    id: str
    text: LocalizedText
    classification: ChecklistClassification
    applicability: Predicate | None
    evidence_link_ids: tuple[str, ...]
    verification_state: VerificationState
    display_order: int
    quantity: int | None = None
    document_type_id: str | None = None
    original_quantity: int | None = None
    copy_quantity: int | None = None
    scope: ChecklistScope = "shared"
    eligibility_basis_id: str | None = None


@dataclass(frozen=True)
class StepDefinition:
    id: str
    text: LocalizedText
    phase: str
    slot: int
    applicability: Predicate | None
    evidence_link_ids: tuple[str, ...]
    verification_state: VerificationState
    phase_order: int = 0
    scope: ChecklistScope = "shared"
    eligibility_basis_id: str | None = None


@dataclass(frozen=True)
class FeeDefinition:
    id: str
    text: LocalizedText
    amount: int | None
    currency: str
    applicability: Predicate | None
    evidence_link_ids: tuple[str, ...]
    verification_state: VerificationState
    value_state: FeeValueState = "known"
    minimum_amount: int | None = None
    maximum_amount: int | None = None
    fee_type: str = "service_fee"


@dataclass(frozen=True)
class ProcedureDependencyDefinition:
    id: str
    text: LocalizedText
    target_procedure_id: str
    relation: DependencyRelation
    applicability: Predicate | None
    satisfied_when: Predicate
    evidence_link_ids: tuple[str, ...]
    verification_state: VerificationState
    verification_path: VerificationPathDefinition


@dataclass(frozen=True)
class ServicePointDefinition:
    """Stable Service Point identity only; material details are versioned separately."""

    id: str
    text: LocalizedText


@dataclass(frozen=True)
class ServicePointVersionDefinition:
    id: str
    service_point_id: str
    address: LocalizedText
    availability: ServicePointAvailability
    effective_from: date | None
    effective_to: date | None
    evidence_link_ids: tuple[str, ...]
    verification_state: VerificationState


@dataclass(frozen=True)
class ProcedureServicePointAssociationDefinition:
    id: str
    service_point_version_id: str
    applicability: Predicate
    effective_from: date | None
    effective_to: date | None
    evidence_link_ids: tuple[str, ...]
    verification_state: VerificationState
    procedure_version_id: str | None = None


@dataclass(frozen=True)
class WarningDefinition:
    id: str
    text: LocalizedText
    severity: Literal["info", "important"]
    evidence_link_ids: tuple[str, ...] = ()
    kind: WarningKind = "administrative"
    role: WarningRole = "general"


@dataclass(frozen=True)
class UnknownDefinition:
    id: str
    text: LocalizedText
    applicability: Predicate | None = None


@dataclass(frozen=True)
class KnowledgeBundle:
    id: str
    goal: GoalDefinition
    procedure: ProcedureVersionDefinition
    sources: Mapping[str, Source]
    evidence_links: Mapping[str, EvidenceLink]
    claims: tuple[ClaimDefinition, ...]
    steps: tuple[StepDefinition, ...]
    fees: tuple[FeeDefinition, ...]
    service_points: tuple[ServicePointDefinition, ...]
    warnings: tuple[WarningDefinition, ...]
    unknowns: tuple[UnknownDefinition, ...]
    eligibility_bases: tuple[EligibilityBasisDefinition, ...] = ()
    dependencies: tuple[ProcedureDependencyDefinition, ...] = ()
    service_point_versions: tuple[ServicePointVersionDefinition, ...] = ()
    service_point_associations: tuple[ProcedureServicePointAssociationDefinition, ...] = ()
    basis_verification_path: VerificationPathDefinition | None = None
    no_applicable_basis_text: LocalizedText | None = None
    routing_verification_path: VerificationPathDefinition | None = None

    def __post_init__(self) -> None:
        if any(
            association.procedure_version_id is None
            for association in self.service_point_associations
        ):
            object.__setattr__(
                self,
                "service_point_associations",
                tuple(
                    replace(
                        association,
                        procedure_version_id=self.procedure.version_id,
                    )
                    if association.procedure_version_id is None
                    else association
                    for association in self.service_point_associations
                ),
            )


@dataclass(frozen=True)
class ProcedureCandidateDefinition:
    procedure_id: str
    text: LocalizedText
    applicability: Predicate
    fixture_id: str | None = None


@dataclass(frozen=True)
class GoalCatalogDefinition:
    goal: GoalDefinition
    candidates: tuple[ProcedureCandidateDefinition, ...]


@dataclass(frozen=True)
class QuestionDefinition:
    id: str
    goal_id: str
    fact_key: str
    text: LocalizedText
    priority: int
    resolves_fact_keys: tuple[str, ...] = ()

    @property
    def resolved_keys(self) -> tuple[str, ...]:
        return self.resolves_fact_keys or (self.fact_key,)


@dataclass(frozen=True)
class ContradictionDefinition:
    """A fixture-authored cross-Fact invariant whose TRUE condition is invalid."""

    id: str
    goal_id: str
    fact_keys: tuple[str, ...]
    condition: Predicate


@dataclass(frozen=True)
class KnowledgeCatalog:
    id: str
    goals: Mapping[str, GoalCatalogDefinition]
    fixtures: Mapping[str, KnowledgeBundle]
    questions: tuple[QuestionDefinition, ...]
    fact_definitions: Mapping[str, FactDefinition] = field(default_factory=dict)
    contradictions: tuple[ContradictionDefinition, ...] = ()


@dataclass(frozen=True)
class EvidenceSummary:
    source_id: str
    authority: str
    title: str
    verified_on: date


@dataclass(frozen=True)
class RenderedVerificationPath:
    id: str
    text: str
    sources: tuple[EvidenceSummary, ...]


@dataclass(frozen=True)
class RenderedChecklistItem:
    id: str
    text: str
    classification: str
    classification_label: str
    quantity: int | None
    original_quantity: int | None
    copy_quantity: int | None
    document_type_id: str | None
    scope: ChecklistScope
    eligibility_basis_id: str | None
    sources: tuple[EvidenceSummary, ...]


@dataclass(frozen=True)
class RenderedChecklistGroup:
    id: str
    document_type_id: str | None
    items: tuple[RenderedChecklistItem, ...]


@dataclass(frozen=True)
class RenderedStep:
    id: str
    text: str
    phase: str
    phase_order: int
    slot: int
    scope: ChecklistScope
    eligibility_basis_id: str | None
    sources: tuple[EvidenceSummary, ...]


@dataclass(frozen=True)
class RenderedFee:
    id: str
    text: str
    value_state: FeeValueState
    amount: int | None
    minimum_amount: int | None
    maximum_amount: int | None
    currency: str
    fee_type: str
    verification_state: VerificationState
    sources: tuple[EvidenceSummary, ...]


@dataclass(frozen=True)
class RenderedEligibilityBasis:
    id: str
    text: str
    verification_state: VerificationState
    checklist_item_ids: tuple[str, ...]
    step_ids: tuple[str, ...]
    sources: tuple[EvidenceSummary, ...]


@dataclass(frozen=True)
class RenderedDependency:
    id: str
    text: str
    relation: DependencyRelation
    status: DependencyStatus
    target_procedure_id: str
    target_procedure: str
    target_procedure_version_id: str | None
    sources: tuple[EvidenceSummary, ...]
    verification_path: RenderedVerificationPath


@dataclass(frozen=True)
class RenderedServicePoint:
    id: str
    version_id: str
    association_id: str
    text: str
    address: str
    availability: ServicePointAvailability
    effective_from: date | None
    effective_to: date | None
    sources: tuple[EvidenceSummary, ...]


@dataclass(frozen=True)
class RenderedRouting:
    status: RoutingStatus
    service_points: tuple[RenderedServicePoint, ...]
    unresolved_association_ids: tuple[str, ...]
    unresolved_fact_keys: tuple[str, ...]
    verification_path: RenderedVerificationPath | None


@dataclass(frozen=True)
class RenderedWarning:
    id: str
    text: str
    severity: str
    kind: WarningKind
    role: WarningRole
    sources: tuple[EvidenceSummary, ...]


@dataclass(frozen=True)
class Freshness:
    procedure_version_id: str
    last_verified_on: date
    evaluation_date: date
    generated_on: date

    @property
    def verified_on(self) -> date:
        """Compatibility alias retained for issue #5-#8 tests/callers."""
        return self.last_verified_on


@dataclass(frozen=True)
class PersonalizedPlan:
    goal_id: str
    goal: str
    procedure_id: str
    procedure: str
    procedure_version_id: str
    locale: Locale
    checklist: tuple[RenderedChecklistItem, ...]
    checklist_groups: tuple[RenderedChecklistGroup, ...]
    steps: tuple[RenderedStep, ...]
    fees: tuple[RenderedFee, ...]
    service_points: tuple[RenderedServicePoint, ...]
    warnings: tuple[RenderedWarning, ...]
    regeneration_warning: RenderedWarning
    unknowns: tuple[str, ...]
    freshness: Freshness
    eligibility_bases: tuple[RenderedEligibilityBasis, ...] = ()
    basis_verification_path: RenderedVerificationPath | None = None
    dependencies: tuple[RenderedDependency, ...] = ()
    routing: RenderedRouting | None = None


@dataclass(frozen=True)
class PlanResult:
    plan: PersonalizedPlan
    kind: Literal["plan"] = field(default="plan", init=False)


@dataclass(frozen=True)
class NextQuestionResult:
    question_id: str
    fact_key: str = ""
    question: str = ""
    kind: Literal["next_question"] = field(default="next_question", init=False)


@dataclass(frozen=True)
class InconclusiveResult:
    reason_code: str
    procedure_id: str | None = None
    diagnostic_codes: tuple[str, ...] = ()
    message: str = ""
    verification_path: RenderedVerificationPath | None = None
    kind: Literal["inconclusive"] = field(default="inconclusive", init=False)


@dataclass(frozen=True)
class InvalidResult:
    diagnostic_code: str
    diagnostic_codes: tuple[str, ...] = ()
    conflicting_fact_keys: tuple[str, ...] = ()
    kind: Literal["invalid"] = field(default="invalid", init=False)


PlanningResult = PlanResult | NextQuestionResult | InconclusiveResult | InvalidResult
