from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Mapping

from .contracts import (
    KnowledgeCatalog,
    Predicate,
    ProcedureCandidateDefinition,
    QuestionDefinition,
)
from .derivations import derive_facts

SelectionState = Literal["match", "no_match", "possible"]


@dataclass(frozen=True)
class PartialEvaluation:
    state: SelectionState
    missing_facts: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SelectedProcedure:
    candidate: ProcedureCandidateDefinition


@dataclass(frozen=True)
class SelectionQuestion:
    question: QuestionDefinition


@dataclass(frozen=True)
class SelectionFailure:
    reason_code: str
    procedure_id: str | None = None
    diagnostic_codes: tuple[str, ...] = ()


SelectionOutcome = SelectedProcedure | SelectionQuestion | SelectionFailure


def _leaf(predicate: Predicate, facts: Mapping[str, object]) -> PartialEvaluation:
    if predicate.fact is None:
        raise ValueError(f"{predicate.op} predicate requires a fact")
    if predicate.fact not in facts:
        return PartialEvaluation("possible", frozenset((predicate.fact,)))

    actual = facts[predicate.fact]
    expected = predicate.value
    op = predicate.op
    if op == "eq":
        result = actual == expected
    elif op == "in":
        result = actual in expected  # type: ignore[operator]
    elif op == "lt":
        result = actual < expected  # type: ignore[operator]
    elif op == "lte":
        result = actual <= expected  # type: ignore[operator]
    elif op == "gt":
        result = actual > expected  # type: ignore[operator]
    elif op == "gte":
        result = actual >= expected  # type: ignore[operator]
    else:
        raise ValueError(f"unsupported selection predicate operator: {op}")
    return PartialEvaluation("match" if result else "no_match")


def evaluate_selection(predicate: Predicate, facts: Mapping[str, object]) -> PartialEvaluation:
    """Selection-only partial matching used by issue #6.

    This intentionally is not the general rule evaluator from #7. It only
    decides whether a Procedure candidate is matched, eliminated, or still
    possible while some referenced Facts are omitted.
    """
    if predicate.op in {"eq", "in", "lt", "lte", "gt", "gte"}:
        return _leaf(predicate, facts)

    children = tuple(evaluate_selection(child, facts) for child in predicate.children)
    if predicate.op == "all":
        if not children:
            raise ValueError("all predicate requires at least one child")
        if any(child.state == "no_match" for child in children):
            return PartialEvaluation("no_match")
        if all(child.state == "match" for child in children):
            return PartialEvaluation("match")
        return PartialEvaluation(
            "possible",
            frozenset().union(
                *(child.missing_facts for child in children if child.state == "possible")
            ),
        )

    if predicate.op == "any":
        if not children:
            raise ValueError("any predicate requires at least one child")
        if any(child.state == "match" for child in children):
            return PartialEvaluation("match")
        if all(child.state == "no_match" for child in children):
            return PartialEvaluation("no_match")
        return PartialEvaluation(
            "possible",
            frozenset().union(
                *(child.missing_facts for child in children if child.state == "possible")
            ),
        )

    if predicate.op == "not":
        if len(children) != 1:
            raise ValueError("not predicate requires exactly one child")
        child = children[0]
        if child.state == "possible":
            return child
        return PartialEvaluation("no_match" if child.state == "match" else "match")

    raise ValueError(f"unsupported selection predicate operator: {predicate.op}")


def _next_question(
    catalog: KnowledgeCatalog,
    goal_id: str,
    missing_facts: frozenset[str],
) -> QuestionDefinition | None:
    questions = sorted(
        (question for question in catalog.questions if question.goal_id == goal_id),
        key=lambda question: (question.priority, question.id),
    )
    return next(
        (
            question
            for question in questions
            if missing_facts.intersection(question.resolved_keys)
        ),
        None,
    )


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

    derived = derive_facts(dict(facts), evaluation_date)
    evaluations = tuple(
        (candidate, evaluate_selection(candidate.applicability, derived))
        for candidate in goal_entry.candidates
    )
    matched = tuple(candidate for candidate, result in evaluations if result.state == "match")
    possible = tuple(
        (candidate, result)
        for candidate, result in evaluations
        if result.state == "possible"
    )

    if len(matched) > 1:
        return SelectionFailure(
            "procedure_selection_configuration_defect",
            diagnostic_codes=("multiple_matching_procedures",),
        )

    if len(matched) == 1 and not possible:
        return SelectedProcedure(matched[0])

    if not matched and not possible:
        return SelectionFailure("no_matching_researched_procedure")

    missing_facts = frozenset().union(*(result.missing_facts for _, result in possible))
    question = _next_question(catalog, goal_id, missing_facts)
    if question is not None:
        return SelectionQuestion(question)

    diagnostics = tuple(
        f"missing_procedure_selection_question:{fact_key}"
        for fact_key in sorted(missing_facts)
    ) or ("unresolved_procedure_selection",)
    return SelectionFailure(
        "procedure_selection_configuration_defect",
        procedure_id=matched[0].procedure_id if len(matched) == 1 else None,
        diagnostic_codes=diagnostics,
    )
