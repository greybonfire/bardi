from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping

from .contracts import (
    ClaimDefinition,
    EligibilityBasisDefinition,
    FeeDefinition,
    KnowledgeBundle,
    KnowledgeCatalog,
    ProcedureDependencyDefinition,
    ProcedureServicePointAssociationDefinition,
    ServicePointDefinition,
    ServicePointVersionDefinition,
    StepDefinition,
    UnknownDefinition,
    VerificationPathDefinition,
    WarningDefinition,
)
from .derivations import derive_facts
from .evaluator import RuleEvaluationRecord, TruthValue, evaluate, record_evaluation


@dataclass(frozen=True)
class SemanticDependency:
    definition: ProcedureDependencyDefinition
    status: str
    target_knowledge: KnowledgeBundle | None


@dataclass(frozen=True)
class SemanticServicePoint:
    point: ServicePointDefinition
    version: ServicePointVersionDefinition
    association: ProcedureServicePointAssociationDefinition


@dataclass(frozen=True)
class SemanticRouting:
    status: str
    service_points: tuple[SemanticServicePoint, ...]
    unresolved_association_ids: tuple[str, ...]
    unresolved_fact_keys: tuple[str, ...]
    verification_path: VerificationPathDefinition | None


@dataclass(frozen=True)
class SemanticPlan:
    knowledge: KnowledgeBundle
    facts: Mapping[str, object]
    evaluation_date: date
    generated_on: date
    claims: tuple[ClaimDefinition, ...]
    steps: tuple[StepDefinition, ...]
    fees: tuple[FeeDefinition, ...]
    service_points: tuple[SemanticServicePoint, ...]
    warnings: tuple[WarningDefinition, ...]
    unknowns: tuple[UnknownDefinition, ...]
    eligibility_bases: tuple[EligibilityBasisDefinition, ...]
    dependencies: tuple[SemanticDependency, ...]
    routing: SemanticRouting


@dataclass(frozen=True)
class PlanAssembly:
    plan: SemanticPlan | None
    missing_facts: frozenset[str] = frozenset()
    traces: tuple[RuleEvaluationRecord, ...] = ()


class KnownCaseIncomplete(Exception):
    """Compatibility name retained from the pre-#7 prototype."""


class ProcedureNotApplicable(Exception):
    def __init__(
        self,
        procedure_id: str,
        traces: tuple[RuleEvaluationRecord, ...] = (),
    ) -> None:
        super().__init__(procedure_id)
        self.procedure_id = procedure_id
        self.traces = traces


class NoApplicableBasis(Exception):
    def __init__(
        self,
        procedure_id: str,
        text,
        verification_path: VerificationPathDefinition,
        traces: tuple[RuleEvaluationRecord, ...] = (),
    ) -> None:
        super().__init__(procedure_id)
        self.procedure_id = procedure_id
        self.text = text
        self.verification_path = verification_path
        self.traces = traces


def _current_items(items):
    return tuple(
        item
        for item in items
        if getattr(item, "verification_state", "current") == "current"
    )


def _select_bases(
    knowledge: KnowledgeBundle,
    facts: Mapping[str, object],
    submitted_keys: frozenset[str],
):
    selected: list[EligibilityBasisDefinition] = []
    missing: set[str] = set()
    traces: list[RuleEvaluationRecord] = []
    for basis in knowledge.eligibility_bases:
        result = evaluate(
            basis.applicability,
            facts,
            submitted_keys=submitted_keys,
        )
        traces.append(
            record_evaluation(
                f"eligibility_basis:{basis.id}",
                result,
                consequential_to_planning=True,
            )
        )
        if result.value is TruthValue.TRUE:
            selected.append(basis)
        elif result.value is TruthValue.UNKNOWN:
            missing.update(result.missing_facts)
    return (
        tuple(sorted(selected, key=lambda item: (item.display_order, item.id))),
        frozenset(missing),
        tuple(traces),
    )


def _belongs_to_matched_basis(item, matched_basis_ids: frozenset[str]) -> bool:
    if getattr(item, "scope", "shared") != "eligibility_basis":
        return True
    return getattr(item, "eligibility_basis_id", None) in matched_basis_ids


def _select_items(
    items,
    facts: Mapping[str, object],
    submitted_keys: frozenset[str],
    *,
    context_prefix: str,
    consequential: bool,
    matched_basis_ids: frozenset[str] = frozenset(),
):
    selected = []
    missing: set[str] = set()
    traces: list[RuleEvaluationRecord] = []
    for item in _current_items(items):
        if not _belongs_to_matched_basis(item, matched_basis_ids):
            continue
        result = evaluate(
            item.applicability,
            facts,
            submitted_keys=submitted_keys,
        )
        traces.append(
            record_evaluation(
                f"{context_prefix}:{item.id}",
                result,
                consequential_to_planning=consequential,
            )
        )
        if result.value is TruthValue.TRUE:
            selected.append(item)
        elif result.value is TruthValue.UNKNOWN and consequential:
            missing.update(result.missing_facts)
    return tuple(selected), frozenset(missing), tuple(traces)


def _select_fees(
    items,
    facts: Mapping[str, object],
    submitted_keys: frozenset[str],
):
    """Select all explicit fee states, including unknown/unverified values."""
    selected = []
    missing: set[str] = set()
    traces: list[RuleEvaluationRecord] = []
    for item in items:
        result = evaluate(
            item.applicability,
            facts,
            submitted_keys=submitted_keys,
        )
        traces.append(
            record_evaluation(
                f"fee:{item.id}",
                result,
                consequential_to_planning=True,
            )
        )
        if result.value is TruthValue.TRUE:
            selected.append(item)
        elif result.value is TruthValue.UNKNOWN:
            missing.update(result.missing_facts)
    return tuple(selected), frozenset(missing), tuple(traces)


def _select_dependencies(
    knowledge: KnowledgeBundle,
    catalog: KnowledgeCatalog | None,
    facts: Mapping[str, object],
    submitted_keys: frozenset[str],
):
    selected: list[SemanticDependency] = []
    missing: set[str] = set()
    traces: list[RuleEvaluationRecord] = []
    for dependency in _current_items(knowledge.dependencies):
        applies = evaluate(
            dependency.applicability,
            facts,
            submitted_keys=submitted_keys,
        )
        traces.append(
            record_evaluation(
                f"dependency_applicability:{dependency.id}",
                applies,
                consequential_to_planning=True,
            )
        )
        if applies.value is TruthValue.FALSE:
            continue
        if applies.value is TruthValue.UNKNOWN:
            missing.update(applies.missing_facts)
            continue

        satisfied = evaluate(
            dependency.satisfied_when,
            facts,
            submitted_keys=submitted_keys,
        )
        traces.append(
            record_evaluation(
                f"dependency_satisfied:{dependency.id}",
                satisfied,
                consequential_to_planning=True,
            )
        )
        if satisfied.value is TruthValue.UNKNOWN:
            missing.update(satisfied.missing_facts)
            continue

        target = None if catalog is None else catalog.fixtures.get(dependency.target_procedure_id)
        if satisfied.value is TruthValue.TRUE:
            status = "satisfied"
        elif target is None:
            status = "unsupported_target"
        else:
            status = "blocking"
        selected.append(SemanticDependency(dependency, status, target))

    return tuple(sorted(selected, key=lambda item: item.definition.id)), frozenset(missing), tuple(traces)


def _date_applies(
    evaluation_date: date,
    effective_from: date | None,
    effective_to: date | None,
) -> bool:
    if effective_from is not None and evaluation_date < effective_from:
        return False
    if effective_to is not None and evaluation_date > effective_to:
        return False
    return True


def _select_routing(
    knowledge: KnowledgeBundle,
    facts: Mapping[str, object],
    submitted_keys: frozenset[str],
    evaluation_date: date,
):
    point_by_id = {point.id: point for point in knowledge.service_points}
    version_by_id = {version.id: version for version in knowledge.service_point_versions}
    selected: list[SemanticServicePoint] = []
    unresolved_associations: set[str] = set()
    unresolved_facts: set[str] = set()
    traces: list[RuleEvaluationRecord] = []

    for association in knowledge.service_point_associations:
        if association.verification_state != "current":
            continue
        if not _date_applies(
            evaluation_date,
            association.effective_from,
            association.effective_to,
        ):
            continue

        result = evaluate(
            association.applicability,
            facts,
            submitted_keys=submitted_keys,
        )
        traces.append(
            record_evaluation(
                f"service_point_association:{association.id}",
                result,
                consequential_to_planning=False,
            )
        )
        if result.value is TruthValue.FALSE:
            continue
        if result.value is TruthValue.UNKNOWN:
            unresolved_associations.add(association.id)
            unresolved_facts.update(result.missing_facts)
            continue

        version = version_by_id.get(association.service_point_version_id)
        if (
            version is None
            or version.verification_state != "current"
            or not _date_applies(
                evaluation_date,
                version.effective_from,
                version.effective_to,
            )
        ):
            unresolved_associations.add(association.id)
            continue
        point = point_by_id.get(version.service_point_id)
        if point is None:
            unresolved_associations.add(association.id)
            continue
        selected.append(SemanticServicePoint(point, version, association))

    selected = sorted(
        selected,
        key=lambda item: (item.point.id, item.version.id, item.association.id),
    )
    if selected and unresolved_associations:
        status = "partially_resolved"
    elif selected:
        status = "resolved"
    else:
        status = "unresolved"

    routing = SemanticRouting(
        status=status,
        service_points=tuple(selected),
        unresolved_association_ids=tuple(sorted(unresolved_associations)),
        unresolved_fact_keys=tuple(sorted(unresolved_facts)),
        verification_path=knowledge.routing_verification_path,
    )
    return routing, tuple(traces)


def assemble_plan(
    knowledge: KnowledgeBundle,
    facts: Mapping[str, object],
    evaluation_date: date,
    *,
    submitted_keys: frozenset[str] | None = None,
    generated_on: date | None = None,
    catalog: KnowledgeCatalog | None = None,
) -> PlanAssembly:
    """Assemble one Procedure plan while preserving local routing uncertainty."""
    submitted = frozenset(facts) if submitted_keys is None else submitted_keys
    generated = evaluation_date if generated_on is None else generated_on
    derived = derive_facts(dict(facts), evaluation_date)
    traces: list[RuleEvaluationRecord] = []

    procedure_result = evaluate(
        knowledge.procedure.applicability,
        derived,
        submitted_keys=submitted,
    )
    traces.append(
        record_evaluation(
            f"procedure_applicability:{knowledge.procedure.procedure_id}",
            procedure_result,
            consequential_to_planning=True,
        )
    )
    if procedure_result.value is TruthValue.FALSE:
        raise ProcedureNotApplicable(
            knowledge.procedure.procedure_id,
            tuple(traces),
        )
    if procedure_result.value is TruthValue.UNKNOWN:
        return PlanAssembly(
            None,
            procedure_result.missing_facts,
            tuple(traces),
        )

    bases, basis_missing, basis_traces = _select_bases(
        knowledge,
        derived,
        submitted,
    )
    traces.extend(basis_traces)
    if basis_missing:
        return PlanAssembly(None, basis_missing, tuple(traces))
    if knowledge.eligibility_bases and not bases:
        assert knowledge.no_applicable_basis_text is not None
        assert knowledge.basis_verification_path is not None
        raise NoApplicableBasis(
            knowledge.procedure.procedure_id,
            knowledge.no_applicable_basis_text,
            knowledge.basis_verification_path,
            tuple(traces),
        )
    matched_basis_ids = frozenset(basis.id for basis in bases)

    claims, claim_missing, claim_traces = _select_items(
        knowledge.claims,
        derived,
        submitted,
        context_prefix="claim",
        consequential=True,
        matched_basis_ids=matched_basis_ids,
    )
    traces.extend(claim_traces)

    steps, step_missing, step_traces = _select_items(
        knowledge.steps,
        derived,
        submitted,
        context_prefix="step",
        consequential=True,
        matched_basis_ids=matched_basis_ids,
    )
    traces.extend(step_traces)

    fees, fee_missing, fee_traces = _select_fees(
        knowledge.fees,
        derived,
        submitted,
    )
    traces.extend(fee_traces)

    dependencies, dependency_missing, dependency_traces = _select_dependencies(
        knowledge,
        catalog,
        derived,
        submitted,
    )
    traces.extend(dependency_traces)

    routing, routing_traces = _select_routing(
        knowledge,
        derived,
        submitted,
        evaluation_date,
    )
    traces.extend(routing_traces)

    unknowns: list[UnknownDefinition] = []
    for item in knowledge.unknowns:
        result = evaluate(
            item.applicability,
            derived,
            submitted_keys=submitted,
        )
        traces.append(
            record_evaluation(
                f"unknown:{item.id}",
                result,
                consequential_to_planning=False,
            )
        )
        if result.value is TruthValue.TRUE:
            unknowns.append(item)

    missing = claim_missing | step_missing | fee_missing | dependency_missing
    if missing:
        return PlanAssembly(None, missing, tuple(traces))

    semantic_plan = SemanticPlan(
        knowledge=knowledge,
        facts=derived,
        evaluation_date=evaluation_date,
        generated_on=generated,
        claims=tuple(
            sorted(claims, key=lambda item: (item.display_order, item.id))
        ),
        steps=tuple(
            sorted(
                steps,
                key=lambda item: (item.phase_order, item.slot, item.id),
            )
        ),
        fees=tuple(sorted(fees, key=lambda item: item.id)),
        service_points=routing.service_points,
        warnings=knowledge.warnings,
        unknowns=tuple(sorted(unknowns, key=lambda item: item.id)),
        eligibility_bases=bases,
        dependencies=dependencies,
        routing=routing,
    )
    return PlanAssembly(semantic_plan, traces=tuple(traces))


def assemble_known_case_plan(
    knowledge: KnowledgeBundle,
    facts: Mapping[str, object],
    evaluation_date: date,
) -> SemanticPlan:
    """Compatibility wrapper for the complete-input issue #5 API."""
    assembly = assemble_plan(
        knowledge,
        facts,
        evaluation_date,
        submitted_keys=frozenset(facts),
    )
    if assembly.plan is None:
        raise KnownCaseIncomplete(",".join(sorted(assembly.missing_facts)))
    return assembly.plan
