from __future__ import annotations

from datetime import date
from typing import Mapping

from .contracts import (
    InconclusiveResult,
    InvalidResult,
    KnowledgeBundle,
    KnowledgeCatalog,
    Locale,
    NextQuestionResult,
    PlanResult,
    PlanningResult,
)
from .planner import KnownCaseIncomplete, ProcedureNotApplicable, assemble_known_case_plan
from .presentation import project_plan
from .selection import SelectedProcedure, SelectionFailure, SelectionQuestion, resolve_procedure


def _run_bundle(
    *,
    knowledge: KnowledgeBundle,
    goal_id: str,
    facts: Mapping[str, object],
    locale: Locale,
    evaluation_date: date,
) -> PlanningResult:
    if goal_id != knowledge.goal.id:
        return InvalidResult("unknown_goal")

    try:
        semantic_plan = assemble_known_case_plan(knowledge, facts, evaluation_date)
    except KnownCaseIncomplete:
        # Issue #7 will replace this fixture-plan fallback with the general
        # typed UNKNOWN evaluator and Missing-Fact Picker.
        return InconclusiveResult("known_case_requires_complete_facts")
    except (ProcedureNotApplicable, ValueError, TypeError):
        return InconclusiveResult("known_case_not_supported")

    return PlanResult(project_plan(semantic_plan, locale))


def run_scenario(
    *,
    knowledge: KnowledgeBundle | KnowledgeCatalog,
    goal_id: str,
    facts: Mapping[str, object],
    locale: Locale,
    evaluation_date: date,
) -> PlanningResult:
    """The prototype's single application-level behavioral seam."""
    if locale not in ("ar", "en"):
        return InvalidResult("unsupported_locale")

    if isinstance(knowledge, KnowledgeBundle):
        return _run_bundle(
            knowledge=knowledge,
            goal_id=goal_id,
            facts=facts,
            locale=locale,
            evaluation_date=evaluation_date,
        )

    try:
        selection = resolve_procedure(
            catalog=knowledge,
            goal_id=goal_id,
            facts=facts,
            evaluation_date=evaluation_date,
        )
    except (ValueError, TypeError):
        return InconclusiveResult(
            "procedure_selection_configuration_defect",
            diagnostic_codes=("invalid_selection_predicate",),
        )

    if isinstance(selection, SelectionQuestion):
        question = selection.question
        return NextQuestionResult(
            question_id=question.id,
            fact_key=question.fact_key,
            question=question.text.render(locale),
        )

    if isinstance(selection, SelectionFailure):
        if selection.reason_code == "unknown_goal":
            return InvalidResult("unknown_goal")
        return InconclusiveResult(
            selection.reason_code,
            procedure_id=selection.procedure_id,
            diagnostic_codes=selection.diagnostic_codes,
        )

    assert isinstance(selection, SelectedProcedure)
    candidate = selection.candidate
    if candidate.fixture_id is None:
        return InconclusiveResult(
            "procedure_not_researched",
            procedure_id=candidate.procedure_id,
        )

    fixture = knowledge.fixtures.get(candidate.fixture_id)
    if fixture is None or fixture.procedure.procedure_id != candidate.procedure_id:
        return InconclusiveResult(
            "procedure_selection_configuration_defect",
            procedure_id=candidate.procedure_id,
            diagnostic_codes=("selected_procedure_fixture_missing_or_mismatched",),
        )

    return _run_bundle(
        knowledge=fixture,
        goal_id=goal_id,
        facts=facts,
        locale=locale,
        evaluation_date=evaluation_date,
    )
