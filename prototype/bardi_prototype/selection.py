from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping

from .contracts import KnowledgeCatalog, ProcedureCandidateDefinition, QuestionDefinition
from .derivations import derive_facts
from .evaluator import RuleEvaluationRecord, TruthValue, evaluate, record_evaluation
from .questions import pick_question


@dataclass(frozen=True)
class SelectedProcedure:
    candidate: ProcedureCandidateDefinition
    traces: tuple[RuleEvaluationRecord, ...] = ()


@dataclass(frozen=True)
class SelectionQuestion:
    question: QuestionDefinition
    traces: tuple[RuleEvaluationRecord, ...] = ()


@dataclass(frozen=True)
class SelectionFailure:
    reason_code: str
    procedure_id: str | None = None
    diagnostic_codes: tuple[str, ...] = ()
    traces: tuple[RuleEvaluationRecord, ...] = ()


SelectionOutcome = SelectedProcedure | SelectionQuestion | SelectionFailure


def resolve_procedure(
    *,
    catalog: KnowledgeCatalog,
    goal_id: str,
    facts: Mapping[str, object],
    evaluation_date: date,
) -> SelectionOutcome:
    goal_entry = catalog.goals.get(goal_id)
    if goal_entry is None:
        return SelectionFailure("unknown_goal")

    submitted_keys = frozenset(facts)
    derived = derive_facts(dict(facts), evaluation_date)
    evaluations = tuple(
        (
            candidate,
            evaluate(
                candidate.applicability,
                derived,
                submitted_keys=submitted_keys,
            ),
        )
        for candidate in goal_entry.candidates
    )
    traces = tuple(
        record_evaluation(
            f"procedure_selection:{candidate.procedure_id}",
            result,
            consequential_to_planning=True,
        )
        for candidate, result in evaluations
    )

    matched = tuple(
        candidate
        for candidate, result in evaluations
        if result.value is TruthValue.TRUE
    )
    unknown = tuple(
        (candidate, result)
        for candidate, result in evaluations
        if result.value is TruthValue.UNKNOWN
    )

    if len(matched) > 1:
        return SelectionFailure(
            "procedure_selection_configuration_defect",
            diagnostic_codes=("multiple_matching_procedures",),
            traces=traces,
        )

    if len(matched) == 1 and not unknown:
        return SelectedProcedure(matched[0], traces)

    if not matched and not unknown:
        return SelectionFailure("no_matching_researched_procedure", traces=traces)

    missing_facts = frozenset().union(
        *(result.missing_facts for _, result in unknown)
    )
    question = pick_question(catalog, goal_id, missing_facts)
    if question is not None:
        return SelectionQuestion(question, traces)

    diagnostics = tuple(
        f"missing_procedure_selection_question:{fact_key}"
        for fact_key in sorted(missing_facts)
    ) or ("unresolved_procedure_selection",)
    return SelectionFailure(
        "procedure_selection_configuration_defect",
        procedure_id=matched[0].procedure_id if len(matched) == 1 else None,
        diagnostic_codes=diagnostics,
        traces=traces,
    )
