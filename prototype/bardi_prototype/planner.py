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
from .evaluator import TruthValue, evaluate


@dataclass(frozen=True)
class SemanticPlan:
    knowledge: KnowledgeBundle
    facts: Mapping[str, object]
    evaluation_date: date
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


class KnownCaseIncomplete(Exception):
    """Compatibility name retained from the pre-#7 prototype."""


class ProcedureNotApplicable(Exception):
    pass


def _current_items(items):
    return tuple(
        item
        for item in items
        if getattr(item, "verification_state", "current") == "current"
    )


def _select_items(
    items,
    facts: Mapping[str, object],
    submitted_keys: frozenset[str],
    *,
    consequential: bool,
):
    selected = []
    missing: set[str] = set()
    for item in _current_items(items):
        result = evaluate(item.applicability, facts, submitted_keys=submitted_keys)
        if result.value is TruthValue.TRUE:
            selected.append(item)
        elif result.value is TruthValue.UNKNOWN and consequential:
            missing.update(result.missing_facts)
    return tuple(selected), frozenset(missing)


def assemble_plan(
    knowledge: KnowledgeBundle,
    facts: Mapping[str, object],
    evaluation_date: date,
    *,
    submitted_keys: frozenset[str] | None = None,
) -> PlanAssembly:
    """Assemble one Procedure plan, surfacing only consequential rule UNKNOWNs."""
    submitted = frozenset(facts) if submitted_keys is None else submitted_keys
    derived = derive_facts(dict(facts), evaluation_date)

    procedure_result = evaluate(
        knowledge.procedure.applicability,
        derived,
        submitted_keys=submitted,
    )
    if procedure_result.value is TruthValue.FALSE:
        raise ProcedureNotApplicable(knowledge.procedure.procedure_id)
    if procedure_result.value is TruthValue.UNKNOWN:
        return PlanAssembly(None, procedure_result.missing_facts)

    claims, claim_missing = _select_items(
        knowledge.claims, derived, submitted, consequential=True
    )
    steps, step_missing = _select_items(
        knowledge.steps, derived, submitted, consequential=True
    )
    fees, fee_missing = _select_items(
        knowledge.fees, derived, submitted, consequential=True
    )

    # Routing is deliberately local: unresolved Service Point applicability does
    # not block otherwise-supported guidance.
    service_points, _ = _select_items(
        knowledge.service_points, derived, submitted, consequential=False
    )

    unknowns = tuple(
        item
        for item in knowledge.unknowns
        if evaluate(item.applicability, derived, submitted_keys=submitted).value
        is TruthValue.TRUE
    )

    missing = claim_missing | step_missing | fee_missing
    if missing:
        return PlanAssembly(None, missing)

    semantic_plan = SemanticPlan(
        knowledge=knowledge,
        facts=derived,
        evaluation_date=evaluation_date,
        claims=tuple(sorted(claims, key=lambda item: item.display_order)),
        steps=tuple(sorted(steps, key=lambda item: (item.slot, item.id))),
        fees=tuple(sorted(fees, key=lambda item: item.id)),
        service_points=tuple(sorted(service_points, key=lambda item: item.id)),
        warnings=knowledge.warnings,
        unknowns=tuple(sorted(unknowns, key=lambda item: item.id)),
    )
    return PlanAssembly(semantic_plan)


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
