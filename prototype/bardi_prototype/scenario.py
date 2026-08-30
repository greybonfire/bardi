from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping

from .contracts import (
    EvidenceSummary,
    InconclusiveResult,
    InvalidResult,
    KnowledgeBundle,
    KnowledgeCatalog,
    Locale,
    NextQuestionResult,
    PlanResult,
    PlanningResult,
    RenderedVerificationPath,
    VerificationPathDefinition,
)
from .contradictions import check_contradictions
from .evaluator import RuleEvaluationRecord
from .facts import FACT_DEFINITIONS, validate_submitted_facts
from .planner import NoApplicableBasis, ProcedureNotApplicable, assemble_plan
from .presentation import project_plan
from .questions import pick_question
from .selection import SelectedProcedure, SelectionFailure, SelectionQuestion, resolve_procedure
from .validation import validate_bundle, validate_catalog
from .versions import (
    bundles_for_procedure,
    resolve_bundle_version,
    resolve_procedure_version,
    upcoming_projection,
)


@dataclass(frozen=True)
class ScenarioInspection:
    result: PlanningResult
    evaluation_traces: tuple[RuleEvaluationRecord, ...] = ()


@dataclass(frozen=True)
class _ScenarioRun:
    result: PlanningResult
    traces: tuple[RuleEvaluationRecord, ...] = ()


def _invalid(
    code: str,
    diagnostics: tuple[str, ...] = (),
    conflicting_fact_keys: tuple[str, ...] = (),
) -> InvalidResult:
    return InvalidResult(
        code,
        diagnostic_codes=diagnostics,
        conflicting_fact_keys=conflicting_fact_keys,
    )


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


def _render_verification_path(
    knowledge: KnowledgeBundle,
    definition: VerificationPathDefinition,
    locale: Locale,
) -> RenderedVerificationPath:
    source_ids: list[str] = []
    for evidence_link_id in definition.evidence_link_ids:
        link = knowledge.evidence_links[evidence_link_id]
        for source_id in link.source_ids:
            if source_id not in source_ids:
                source_ids.append(source_id)
    return RenderedVerificationPath(
        id=definition.id,
        text=definition.text.render(locale),
        sources=tuple(
            EvidenceSummary(
                source_id=source_id,
                authority=knowledge.sources[source_id].authority,
                title=knowledge.sources[source_id].title,
                verified_on=knowledge.sources[source_id].retrieved_on,
                classification=knowledge.sources[source_id].classification,
            )
            for source_id in source_ids
        ),
    )


def _run_bundle(
    *,
    knowledge: KnowledgeBundle,
    goal_id: str,
    facts: Mapping[str, object],
    locale: Locale,
    evaluation_date: date,
    generated_on: date,
    catalog: KnowledgeCatalog | None = None,
    historical: bool = False,
    upcoming_versions=(),
) -> _ScenarioRun:
    if goal_id != knowledge.goal.id:
        return _ScenarioRun(_invalid("unknown_goal"))

    try:
        assembly = assemble_plan(
            knowledge,
            facts,
            evaluation_date,
            submitted_keys=frozenset(facts),
            generated_on=generated_on,
            catalog=catalog,
            historical=historical,
            upcoming_versions=upcoming_versions,
        )
    except NoApplicableBasis as exc:
        return _ScenarioRun(
            InconclusiveResult(
                "no_applicable_basis",
                procedure_id=exc.procedure_id,
                message=exc.text.render(locale),
                verification_path=_render_verification_path(
                    knowledge,
                    exc.verification_path,
                    locale,
                ),
                upcoming_versions=upcoming_projection(upcoming_versions, locale),
            ),
            exc.traces,
        )
    except ProcedureNotApplicable as exc:
        return _ScenarioRun(
            InconclusiveResult("known_case_not_supported"),
            exc.traces,
        )
    except (ValueError, TypeError):
        return _ScenarioRun(
            _invalid("invalid_facts", ("fact_derivation_failed",))
        )

    if assembly.plan is None:
        if catalog is None:
            return _ScenarioRun(
                InconclusiveResult(
                    "known_case_requires_complete_facts",
                    diagnostic_codes=tuple(
                        f"missing_fact:{key}"
                        for key in sorted(assembly.missing_facts)
                    ),
                ),
                assembly.traces,
            )

        question = pick_question(catalog, goal_id, assembly.missing_facts)
        if question is not None:
            return _ScenarioRun(
                NextQuestionResult(
                    question_id=question.id,
                    fact_key=question.fact_key,
                    question=question.text.render(locale),
                    upcoming_versions=upcoming_projection(upcoming_versions, locale),
                ),
                assembly.traces,
            )

        return _ScenarioRun(
            InconclusiveResult(
                "missing_fact_configuration_defect",
                procedure_id=knowledge.procedure.procedure_id,
                diagnostic_codes=tuple(
                    f"missing_plan_question:{key}"
                    for key in sorted(assembly.missing_facts)
                ),
                upcoming_versions=upcoming_projection(upcoming_versions, locale),
            ),
            assembly.traces,
        )

    return _ScenarioRun(
        PlanResult(project_plan(assembly.plan, locale)),
        assembly.traces,
    )


def _execute_scenario(
    *,
    knowledge: KnowledgeBundle | KnowledgeCatalog,
    goal_id: str,
    facts: Mapping[str, object],
    locale: Locale,
    evaluation_date: date,
    generated_on: date | None = None,
    detailed_diagnostics: bool = False,
    historical_version_id: str | None = None,
    procedure_version_id: str | None = None,
    version_id: str | None = None,
) -> _ScenarioRun:
    if locale not in ("ar", "en"):
        return _ScenarioRun(_invalid("unsupported_locale"))
    if type(evaluation_date) is not date:
        return _ScenarioRun(_invalid("invalid_evaluation_date"))

    generation_date = evaluation_date if generated_on is None else generated_on
    if type(generation_date) is not date:
        return _ScenarioRun(_invalid("invalid_generation_date"))

    requested_version_ids = tuple(
        value
        for value in (historical_version_id, procedure_version_id, version_id)
        if value is not None
    )
    if len(set(requested_version_ids)) > 1:
        return _ScenarioRun(_invalid("invalid_procedure_version_selector"))
    requested_version_id = requested_version_ids[0] if requested_version_ids else None

    if isinstance(knowledge, KnowledgeBundle):
        knowledge_diagnostics = validate_bundle(
            knowledge,
            FACT_DEFINITIONS,
        )
        if knowledge_diagnostics:
            return _ScenarioRun(
                _invalid(
                    "invalid_knowledge",
                    knowledge_diagnostics
                    if detailed_diagnostics
                    else ("invalid_knowledge",),
                )
            )
        fact_diagnostics = _validate_facts(
            facts,
            FACT_DEFINITIONS,
            evaluation_date,
        )
        if fact_diagnostics:
            return _ScenarioRun(_invalid("invalid_facts", fact_diagnostics))
        version = resolve_bundle_version(
            knowledge,
            evaluation_date,
            version_id=requested_version_id,
        )
        if version.bundle is None:
            return _ScenarioRun(
                InconclusiveResult(
                    version.reason_code or "no_applicable_procedure_version",
                    procedure_id=knowledge.procedure.procedure_id,
                    upcoming_versions=upcoming_projection(version.upcoming, locale),
                )
            )
        return _run_bundle(
            knowledge=version.bundle,
            goal_id=goal_id,
            facts=facts,
            locale=locale,
            evaluation_date=evaluation_date,
            generated_on=generation_date,
            historical=version.historical,
            upcoming_versions=version.upcoming,
        )

    knowledge_diagnostics = validate_catalog(knowledge)
    if knowledge_diagnostics:
        return _ScenarioRun(
            _invalid(
                "invalid_knowledge",
                knowledge_diagnostics
                if detailed_diagnostics
                else ("invalid_knowledge",),
            )
        )

    definitions = knowledge.fact_definitions or FACT_DEFINITIONS
    fact_diagnostics = _validate_facts(
        facts,
        definitions,
        evaluation_date,
    )
    if fact_diagnostics:
        return _ScenarioRun(_invalid("invalid_facts", fact_diagnostics))

    contradiction_check = check_contradictions(
        catalog=knowledge,
        goal_id=goal_id,
        facts=facts,
        evaluation_date=evaluation_date,
    )
    traces: list[RuleEvaluationRecord] = list(contradiction_check.traces)
    if contradiction_check.matches:
        diagnostics = tuple(
            f"contradiction:{match.definition.id}"
            for match in contradiction_check.matches
        )
        conflicting_keys = tuple(
            sorted(
                {
                    key
                    for match in contradiction_check.matches
                    for key in match.definition.fact_keys
                }
            )
        )
        return _ScenarioRun(
            _invalid(
                "contradictory_facts",
                diagnostics,
                conflicting_fact_keys=conflicting_keys,
            ),
            tuple(traces),
        )

    selection = resolve_procedure(
        catalog=knowledge,
        goal_id=goal_id,
        facts=facts,
        evaluation_date=evaluation_date,
    )
    traces.extend(selection.traces)

    if isinstance(selection, SelectionQuestion):
        question = selection.question
        return _ScenarioRun(
            NextQuestionResult(
                question_id=question.id,
                fact_key=question.fact_key,
                question=question.text.render(locale),
            ),
            tuple(traces),
        )

    if isinstance(selection, SelectionFailure):
        if selection.reason_code == "unknown_goal":
            return _ScenarioRun(_invalid("unknown_goal"), tuple(traces))
        return _ScenarioRun(
            InconclusiveResult(
                selection.reason_code,
                procedure_id=selection.procedure_id,
                diagnostic_codes=selection.diagnostic_codes,
            ),
            tuple(traces),
        )

    assert isinstance(selection, SelectedProcedure)
    candidate = selection.candidate
    if candidate.fixture_id is None and not bundles_for_procedure(knowledge, candidate.procedure_id):
        return _ScenarioRun(
            InconclusiveResult(
                "procedure_not_researched",
                procedure_id=candidate.procedure_id,
            ),
            tuple(traces),
        )

    if candidate.fixture_id is not None and not bundles_for_procedure(
        knowledge, candidate.procedure_id
    ):
        legacy_fixture = knowledge.fixtures.get(candidate.fixture_id)
        version = (
            resolve_bundle_version(
                legacy_fixture,
                evaluation_date,
                version_id=requested_version_id,
            )
            if legacy_fixture is not None
            and legacy_fixture.procedure.procedure_id == candidate.procedure_id
            else resolve_procedure_version(
                knowledge,
                candidate.procedure_id,
                evaluation_date,
                version_id=requested_version_id,
            )
        )
    else:
        version = resolve_procedure_version(
            knowledge,
            candidate.procedure_id,
            evaluation_date,
            version_id=requested_version_id,
        )
    if version.bundle is None:
        return _ScenarioRun(
            InconclusiveResult(
                version.reason_code or "no_applicable_procedure_version",
                procedure_id=candidate.procedure_id,
                upcoming_versions=upcoming_projection(version.upcoming, locale),
            ),
            tuple(traces),
        )

    bundle_run = _run_bundle(
        knowledge=version.bundle,
        goal_id=goal_id,
        facts=facts,
        locale=locale,
        evaluation_date=evaluation_date,
        generated_on=generation_date,
        catalog=knowledge,
        historical=version.historical,
        upcoming_versions=version.upcoming,
    )
    return _ScenarioRun(
        bundle_run.result,
        tuple(traces) + bundle_run.traces,
    )


def run_scenario(
    *,
    knowledge: KnowledgeBundle | KnowledgeCatalog,
    goal_id: str,
    facts: Mapping[str, object],
    locale: Locale,
    evaluation_date: date,
    generated_on: date | None = None,
    historical_version_id: str | None = None,
    procedure_version_id: str | None = None,
    version_id: str | None = None,
) -> PlanningResult:
    """Public trace-free seam with an explicit optional generation date."""
    return _execute_scenario(
        knowledge=knowledge,
        goal_id=goal_id,
        facts=facts,
        locale=locale,
        evaluation_date=evaluation_date,
        generated_on=generated_on,
        historical_version_id=historical_version_id,
        procedure_version_id=procedure_version_id,
        version_id=version_id,
    ).result


def inspect_scenario(
    *,
    knowledge: KnowledgeBundle | KnowledgeCatalog,
    goal_id: str,
    facts: Mapping[str, object],
    locale: Locale,
    evaluation_date: date,
    generated_on: date | None = None,
    historical_version_id: str | None = None,
    procedure_version_id: str | None = None,
    version_id: str | None = None,
) -> ScenarioInspection:
    execution = _execute_scenario(
        knowledge=knowledge,
        goal_id=goal_id,
        facts=facts,
        locale=locale,
        evaluation_date=evaluation_date,
        generated_on=generated_on,
        detailed_diagnostics=True,
        historical_version_id=historical_version_id,
        procedure_version_id=procedure_version_id,
        version_id=version_id,
    )
    return ScenarioInspection(execution.result, execution.traces)
