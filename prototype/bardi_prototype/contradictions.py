from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping

from .contracts import ContradictionDefinition, KnowledgeCatalog
from .derivations import derive_facts
from .evaluator import RuleEvaluationRecord, TruthValue, evaluate, record_evaluation


@dataclass(frozen=True)
class ContradictionMatch:
    definition: ContradictionDefinition


@dataclass(frozen=True)
class ContradictionCheck:
    matches: tuple[ContradictionMatch, ...]
    traces: tuple[RuleEvaluationRecord, ...]


def check_contradictions(
    *,
    catalog: KnowledgeCatalog,
    goal_id: str,
    facts: Mapping[str, object],
    evaluation_date: date,
) -> ContradictionCheck:
    """Evaluate authored cross-Fact invariants after type validation.

    UNKNOWN contradiction conditions never trigger Questions: contradiction
    checks exist only to reject an already-submitted inconsistent Case.
    """
    submitted = frozenset(facts)
    derived = derive_facts(dict(facts), evaluation_date)
    matches: list[ContradictionMatch] = []
    traces: list[RuleEvaluationRecord] = []

    for definition in catalog.contradictions:
        if definition.goal_id != goal_id:
            continue
        evaluation = evaluate(
            definition.condition,
            derived,
            submitted_keys=submitted,
        )
        traces.append(
            record_evaluation(
                f"contradiction:{definition.id}",
                evaluation,
                consequential_to_planning=True,
            )
        )
        if evaluation.value is TruthValue.TRUE:
            matches.append(ContradictionMatch(definition))

    return ContradictionCheck(tuple(matches), tuple(traces))
