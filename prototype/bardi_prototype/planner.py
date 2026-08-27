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
from .evaluator import MissingFactError, evaluate


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


class KnownCaseIncomplete(Exception):
    pass


class ProcedureNotApplicable(Exception):
    pass


def _current_and_applicable(items, facts):
    selected = []
    for item in items:
        if getattr(item, "verification_state", "current") != "current":
            continue
        if evaluate(item.applicability, facts):
            selected.append(item)
    return tuple(selected)


def assemble_known_case_plan(
    knowledge: KnowledgeBundle,
    facts: Mapping[str, object],
    evaluation_date: date,
) -> SemanticPlan:
    """Assemble a plan for a complete known case only.

    Missing-Fact selection and three-valued evaluation are intentionally deferred
    to later prototype issues.
    """
    derived = derive_facts(dict(facts), evaluation_date)
    try:
        if not evaluate(knowledge.procedure.applicability, derived):
            raise ProcedureNotApplicable(knowledge.procedure.procedure_id)
        claims = _current_and_applicable(knowledge.claims, derived)
        steps = _current_and_applicable(knowledge.steps, derived)
        fees = _current_and_applicable(knowledge.fees, derived)
        service_points = _current_and_applicable(knowledge.service_points, derived)
        unknowns = tuple(item for item in knowledge.unknowns if evaluate(item.applicability, derived))
    except MissingFactError as exc:
        raise KnownCaseIncomplete(str(exc)) from exc

    warnings = knowledge.warnings

    return SemanticPlan(
        knowledge=knowledge,
        facts=derived,
        evaluation_date=evaluation_date,
        claims=tuple(sorted(claims, key=lambda item: item.display_order)),
        steps=tuple(sorted(steps, key=lambda item: (item.slot, item.id))),
        fees=tuple(sorted(fees, key=lambda item: item.id)),
        service_points=tuple(sorted(service_points, key=lambda item: item.id)),
        warnings=warnings,
        unknowns=tuple(sorted(unknowns, key=lambda item: item.id)),
    )
