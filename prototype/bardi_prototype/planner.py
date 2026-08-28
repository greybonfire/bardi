from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping

from .contracts import (
    ClaimDefinition,
    FeeDefinition,
    KnowledgeBundle,
    ServicePointDefinition,
    StepDefinition,
    UnknownDefinition,
    WarningDefinition,
)
from .derivations import derive_facts
from .evaluator import RuleEvaluationRecord, TruthValue, evaluate, record_evaluation


@dataclass(frozen=True)
class SemanticPlan:
    knowledge: KnowledgeBundle
    facts: Mapping[str, object]
    evaluation_date: date
    generated_on: date
    claims: tuple[ClaimDefinition, ...]
    steps: tuple[StepDefinition, ...]
    fees: tuple[FeeDefinition, ...]
    service_points: tuple[ServicePointDefinition, ...]
    warnings: tuple[WarningDefinition, ...]
    unknowns: tuple[UnknownDefinition, ...]


@dataclass(frozen=True)
class PlanAssembly:
    plan: SemanticPlan | None
    missing_facts: frozenset[str] = frozenset()
    traces: tuple[RuleEvaluationRecord, ...] = ()


class KnownCaseIncomplete(Exception):
    """Compatibility name retained from the pre-#7 prototype."""


class ProcedureNotApplicable(Exception):
    def __init__(self, procedure_id: str, traces: tuple[RuleEvaluationRecord, ...] = ()) -> None:
        super().__init__(procedure_id)
        self.procedure_id = procedure_id
        self.traces = traces


def _current_items(items):
    return tuple(item for item in items if getattr(item, "verification_state", "current") == "current")


def _select_items(items, facts: Mapping[str, object], submitted_keys: frozenset[str], *, context_prefix: str, consequential: bool):
    selected = []
    missing: set[str] = set()
    traces: list[RuleEvaluationRecord] = []
    for item in _current_items(items):
        result = evaluate(item.applicability, facts, submitted_keys=submitted_keys)
        traces.append(record_evaluation(f"{context_prefix}:{item.id}", result, consequential_to_planning=consequential))
        if result.value is TruthValue.TRUE:
            selected.append(item)
        elif result.value is TruthValue.UNKNOWN and consequential:
            missing.update(result.missing_facts)
    return tuple(selected), frozenset(missing), tuple(traces)


def _select_fees(items, facts: Mapping[str, object], submitted_keys: frozenset[str]):
    selected = []
    missing: set[str] = set()
    traces: list[RuleEvaluationRecord] = []
    for item in items:
        result = evaluate(item.applicability, facts, submitted_keys=submitted_keys)
        traces.append(record_evaluation(f"fee:{item.id}", result, consequential_to_planning=True))
        if result.value is TruthValue.TRUE:
            selected.append(item)
        elif result.value is TruthValue.UNKNOWN:
            missing.update(result.missing_facts)
    return tuple(selected), frozenset(missing), tuple(traces)


def assemble_plan(
    knowledge: KnowledgeBundle,
    facts: Mapping[str, object],
    evaluation_date: date,
    *,
    submitted_keys: frozenset[str] | None = None,
    generated_on: date | None = None,
) -> PlanAssembly:
    submitted = frozenset(facts) if submitted_keys is None else submitted_keys
    generated = evaluation_date if generated_on is None else generated_on
    derived = derive_facts(dict(facts), evaluation_date)
    traces: list[RuleEvaluationRecord] = []

    procedure_result = evaluate(knowledge.procedure.applicability, derived, submitted_keys=submitted)
    traces.append(record_evaluation(f"procedure_applicability:{knowledge.procedure.procedure_id}", procedure_result, consequential_to_planning=True))
    if procedure_result.value is TruthValue.FALSE:
        raise ProcedureNotApplicable(knowledge.procedure.procedure_id, tuple(traces))
    if procedure_result.value is TruthValue.UNKNOWN:
        return PlanAssembly(None, procedure_result.missing_facts, tuple(traces))

    claims, claim_missing, claim_traces = _select_items(knowledge.claims, derived, submitted, context_prefix="claim", consequential=True)
    traces.extend(claim_traces)
    steps, step_missing, step_traces = _select_items(knowledge.steps, derived, submitted, context_prefix="step", consequential=True)
    traces.extend(step_traces)
    fees, fee_missing, fee_traces = _select_fees(knowledge.fees, derived, submitted)
    traces.extend(fee_traces)
    service_points, _, service_point_traces = _select_items(knowledge.service_points, derived, submitted, context_prefix="service_point", consequential=False)
    traces.extend(service_point_traces)

    unknowns: list[UnknownDefinition] = []
    for item in knowledge.unknowns:
        result = evaluate(item.applicability, derived, submitted_keys=submitted)
        traces.append(record_evaluation(f"unknown:{item.id}", result, consequential_to_planning=False))
        if result.value is TruthValue.TRUE:
            unknowns.append(item)

    missing = claim_missing | step_missing | fee_missing
    if missing:
        return PlanAssembly(None, missing, tuple(traces))

    semantic_plan = SemanticPlan(
        knowledge=knowledge,
        facts=derived,
        evaluation_date=evaluation_date,
        generated_on=generated,
        claims=tuple(sorted(claims, key=lambda item: (item.display_order, item.id))),
        steps=tuple(sorted(steps, key=lambda item: (item.phase_order, item.slot, item.id))),
        fees=tuple(sorted(fees, key=lambda item: item.id)),
        service_points=tuple(sorted(service_points, key=lambda item: item.id)),
        warnings=knowledge.warnings,
        unknowns=tuple(sorted(unknowns, key=lambda item: item.id)),
    )
    return PlanAssembly(semantic_plan, traces=tuple(traces))


def assemble_known_case_plan(knowledge: KnowledgeBundle, facts: Mapping[str, object], evaluation_date: date) -> SemanticPlan:
    assembly = assemble_plan(knowledge, facts, evaluation_date, submitted_keys=frozenset(facts))
    if assembly.plan is None:
        raise KnownCaseIncomplete(",".join(sorted(assembly.missing_facts)))
    return assembly.plan
