from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping

from .contracts import InconclusiveResult, InvalidResult, KnowledgeBundle, KnowledgeCatalog, Locale, NextQuestionResult, PlanResult, PlanningResult
from .contradictions import check_contradictions
from .evaluator import RuleEvaluationRecord
from .facts import FACT_DEFINITIONS, validate_submitted_facts
from .planner import ProcedureNotApplicable, assemble_plan
from .presentation import project_plan
from .questions import pick_question
from .selection import SelectedProcedure, SelectionFailure, SelectionQuestion, resolve_procedure
from .validation import validate_bundle, validate_catalog


@dataclass(frozen=True)
class ScenarioInspection:
    result: PlanningResult
    evaluation_traces: tuple[RuleEvaluationRecord, ...] = ()


@dataclass(frozen=True)
class _ScenarioRun:
    result: PlanningResult
    traces: tuple[RuleEvaluationRecord, ...] = ()


def _invalid(code: str, diagnostics: tuple[str, ...] = (), conflicting_fact_keys: tuple[str, ...] = ()) -> InvalidResult:
    return InvalidResult(code, diagnostic_codes=diagnostics, conflicting_fact_keys=conflicting_fact_keys)


def _validate_facts(facts: Mapping[str, object], definitions, evaluation_date: date) -> tuple[str, ...]:
    diagnostics = list(validate_submitted_facts(facts, definitions))
    birth_date = facts.get("birth_date")
    if type(birth_date) is date and birth_date > evaluation_date:
        diagnostics.append("invalid_fact_value:birth_date")
    return tuple(dict.fromkeys(diagnostics))


def _run_bundle(*, knowledge: KnowledgeBundle, goal_id: str, facts: Mapping[str, object], locale: Locale, evaluation_date: date, generated_on: date, catalog: KnowledgeCatalog | None = None) -> _ScenarioRun:
    if goal_id != knowledge.goal.id:
        return _ScenarioRun(_invalid("unknown_goal"))
    try:
        assembly = assemble_plan(knowledge, facts, evaluation_date, submitted_keys=frozenset(facts), generated_on=generated_on)
    except ProcedureNotApplicable as exc:
        return _ScenarioRun(InconclusiveResult("known_case_not_supported"), exc.traces)
    except (ValueError, TypeError):
        return _ScenarioRun(_invalid("invalid_facts", ("fact_derivation_failed",)))

    if assembly.plan is None:
        if catalog is None:
            return _ScenarioRun(InconclusiveResult("known_case_requires_complete_facts", diagnostic_codes=tuple(f"missing_fact:{key}" for key in sorted(assembly.missing_facts))), assembly.traces)
        question = pick_question(catalog, goal_id, assembly.missing_facts)
        if question is not None:
            return _ScenarioRun(NextQuestionResult(question_id=question.id, fact_key=question.fact_key, question=question.text.render(locale)), assembly.traces)
        return _ScenarioRun(InconclusiveResult("missing_fact_configuration_defect", procedure_id=knowledge.procedure.procedure_id, diagnostic_codes=tuple(f"missing_plan_question:{key}" for key in sorted(assembly.missing_facts))), assembly.traces)

    return _ScenarioRun(PlanResult(project_plan(assembly.plan, locale)), assembly.traces)


def _execute_scenario(*, knowledge: KnowledgeBundle | KnowledgeCatalog, goal_id: str, facts: Mapping[str, object], locale: Locale, evaluation_date: date, generated_on: date | None = None) -> _ScenarioRun:
    if locale not in ("ar", "en"):
        return _ScenarioRun(_invalid("unsupported_locale"))
    if type(evaluation_date) is not date:
        return _ScenarioRun(_invalid("invalid_evaluation_date"))
    generation_date = evaluation_date if generated_on is None else generated_on
    if type(generation_date) is not date:
        return _ScenarioRun(_invalid("invalid_generation_date"))

    if isinstance(knowledge, KnowledgeBundle):
        knowledge_diagnostics = validate_bundle(knowledge, FACT_DEFINITIONS)
        if knowledge_diagnostics:
            return _ScenarioRun(_invalid("invalid_knowledge", knowledge_diagnostics))
        fact_diagnostics = _validate_facts(facts, FACT_DEFINITIONS, evaluation_date)
        if fact_diagnostics:
            return _ScenarioRun(_invalid("invalid_facts", fact_diagnostics))
        return _run_bundle(knowledge=knowledge, goal_id=goal_id, facts=facts, locale=locale, evaluation_date=evaluation_date, generated_on=generation_date)

    knowledge_diagnostics = validate_catalog(knowledge)
    if knowledge_diagnostics:
        return _ScenarioRun(_invalid("invalid_knowledge", knowledge_diagnostics))
    definitions = knowledge.fact_definitions or FACT_DEFINITIONS
    fact_diagnostics = _validate_facts(facts, definitions, evaluation_date)
    if fact_diagnostics:
        return _ScenarioRun(_invalid("invalid_facts", fact_diagnostics))

    contradiction_check = check_contradictions(catalog=knowledge, goal_id=goal_id, facts=facts, evaluation_date=evaluation_date)
    traces: list[RuleEvaluationRecord] = list(contradiction_check.traces)
    if contradiction_check.matches:
        diagnostics = tuple(f"contradiction:{match.definition.id}" for match in contradiction_check.matches)
        conflicting_keys = tuple(sorted({key for match in contradiction_check.matches for key in match.definition.fact_keys}))
        return _ScenarioRun(_invalid("contradictory_facts", diagnostics, conflicting_fact_keys=conflicting_keys), tuple(traces))

    selection = resolve_procedure(catalog=knowledge, goal_id=goal_id, facts=facts, evaluation_date=evaluation_date)
    traces.extend(selection.traces)
    if isinstance(selection, SelectionQuestion):
        q = selection.question
        return _ScenarioRun(NextQuestionResult(question_id=q.id, fact_key=q.fact_key, question=q.text.render(locale)), tuple(traces))
    if isinstance(selection, SelectionFailure):
        if selection.reason_code == "unknown_goal":
            return _ScenarioRun(_invalid("unknown_goal"), tuple(traces))
        return _ScenarioRun(InconclusiveResult(selection.reason_code, procedure_id=selection.procedure_id, diagnostic_codes=selection.diagnostic_codes), tuple(traces))

    assert isinstance(selection, SelectedProcedure)
    candidate = selection.candidate
    if candidate.fixture_id is None:
        return _ScenarioRun(InconclusiveResult("procedure_not_researched", procedure_id=candidate.procedure_id), tuple(traces))
    fixture = knowledge.fixtures.get(candidate.fixture_id)
    if fixture is None or fixture.procedure.procedure_id != candidate.procedure_id:
        return _ScenarioRun(InconclusiveResult("procedure_selection_configuration_defect", procedure_id=candidate.procedure_id, diagnostic_codes=("selected_procedure_fixture_missing_or_mismatched",)), tuple(traces))
    bundle_run = _run_bundle(knowledge=fixture, goal_id=goal_id, facts=facts, locale=locale, evaluation_date=evaluation_date, generated_on=generation_date, catalog=knowledge)
    return _ScenarioRun(bundle_run.result, tuple(traces) + bundle_run.traces)


def run_scenario(*, knowledge: KnowledgeBundle | KnowledgeCatalog, goal_id: str, facts: Mapping[str, object], locale: Locale, evaluation_date: date, generated_on: date | None = None) -> PlanningResult:
    return _execute_scenario(knowledge=knowledge, goal_id=goal_id, facts=facts, locale=locale, evaluation_date=evaluation_date, generated_on=generated_on).result


def inspect_scenario(*, knowledge: KnowledgeBundle | KnowledgeCatalog, goal_id: str, facts: Mapping[str, object], locale: Locale, evaluation_date: date, generated_on: date | None = None) -> ScenarioInspection:
    execution = _execute_scenario(knowledge=knowledge, goal_id=goal_id, facts=facts, locale=locale, evaluation_date=evaluation_date, generated_on=generated_on)
    return ScenarioInspection(execution.result, execution.traces)
