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
from .facts import FACT_DEFINITIONS, validate_submitted_facts
from .planner import ProcedureNotApplicable, assemble_plan
from .presentation import project_plan
from .questions import pick_question
from .selection import SelectedProcedure, SelectionFailure, SelectionQuestion, resolve_procedure
from .validation import validate_bundle, validate_catalog


def _invalid(code: str, diagnostics: tuple[str, ...] = ()) -> InvalidResult:
    return InvalidResult(code, diagnostic_codes=diagnostics)


def _validate_facts(
    facts: Mapping[str, object],
    definitions,
    evaluation_date: date,
) -> tuple[str, ...]:
    diagnostics = list(validate_submitted_facts(facts, definitions))
    birth_date = facts.get("birth_date")
    if type(birth_date) is date and birth_date > evaluation_date:
        diagnostics.append("invalid_fact_value:birth_date")
    return tuple(dict.fromkeys(diagnostics))


def _run_bundle(
    *,
    knowledge: KnowledgeBundle,
    goal_id: str,
    facts: Mapping[str, object],
    locale: Locale,
    evaluation_date: date,
    catalog: KnowledgeCatalog | None = None,
) -> PlanningResult:
    if goal_id != knowledge.goal.id:
        return _invalid("unknown_goal")

    try:
        assembly = assemble_plan(
            knowledge,
            facts,
            evaluation_date,
            submitted_keys=frozenset(facts),
        )
    except ProcedureNotApplicable:
        return InconclusiveResult("known_case_not_supported")
    except (ValueError, TypeError):
        return _invalid("invalid_facts", ("fact_derivation_failed",))

    if assembly.plan is None:
        if catalog is None:
            return InconclusiveResult(
                "known_case_requires_complete_facts",
                diagnostic_codes=tuple(
                    f"missing_fact:{key}" for key in sorted(assembly.missing_facts)
                ),
            )

        question = pick_question(catalog, goal_id, assembly.missing_facts)
        if question is not None:
            return NextQuestionResult(
                question_id=question.id,
                fact_key=question.fact_key,
                question=question.text.render(locale),
            )

        return InconclusiveResult(
            "missing_fact_configuration_defect",
            procedure_id=knowledge.procedure.procedure_id,
            diagnostic_codes=tuple(
                f"missing_plan_question:{key}" for key in sorted(assembly.missing_facts)
            ),
        )

    return PlanResult(project_plan(assembly.plan, locale))


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
        return _invalid("unsupported_locale")
    if type(evaluation_date) is not date:
        return _invalid("invalid_evaluation_date")

    if isinstance(knowledge, KnowledgeBundle):
        knowledge_diagnostics = validate_bundle(knowledge, FACT_DEFINITIONS)
        if knowledge_diagnostics:
            return _invalid("invalid_knowledge", knowledge_diagnostics)
        fact_diagnostics = _validate_facts(facts, FACT_DEFINITIONS, evaluation_date)
        if fact_diagnostics:
            return _invalid("invalid_facts", fact_diagnostics)
        return _run_bundle(
            knowledge=knowledge,
            goal_id=goal_id,
            facts=facts,
            locale=locale,
            evaluation_date=evaluation_date,
        )

    knowledge_diagnostics = validate_catalog(knowledge)
    if knowledge_diagnostics:
        return _invalid("invalid_knowledge", knowledge_diagnostics)

    definitions = knowledge.fact_definitions or FACT_DEFINITIONS
    fact_diagnostics = _validate_facts(facts, definitions, evaluation_date)
    if fact_diagnostics:
        return _invalid("invalid_facts", fact_diagnostics)

    selection = resolve_procedure(
        catalog=knowledge,
        goal_id=goal_id,
        facts=facts,
        evaluation_date=evaluation_date,
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
            return _invalid("unknown_goal")
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
        catalog=knowledge,
    )
