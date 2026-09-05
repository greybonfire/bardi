"""Conservative pure planning operation for the stateless public contract."""

from __future__ import annotations

from .case_preparation import (
    CasePreparationConfigurationDefect,
    CasePreparationInvalid,
    CasePreparationSuccess,
    prepare_case,
)
from .catalog import KnowledgeSnapshot
from .checklists import select_checklist_items
from .evaluator import TruthValue, evaluate
from .facts import validate_submitted_facts
from .public import (
    AnswerDefinition,
    InconclusiveResult,
    InvalidResult,
    NextQuestionResult,
    PlanningInput,
    PlanningResult,
    PlanResult,
    PublicDiagnostic,
    PublicQuestion,
)
from .selection import (
    ProcedureSelected,
    SelectionConfigurationDefect,
    SelectionInconclusive,
    SelectionQuestion,
    SelectionUnsupported,
    select_procedure,
)
from .steps import select_steps
from .versions import (
    ProcedureVersionConfigurationDefect,
    ProcedureVersionResolved,
    resolve_procedure_version,
)
from .warnings import select_warnings


def _configuration_invalid() -> InvalidResult:
    return InvalidResult((PublicDiagnostic("knowledge_configuration_invalid", ()),))


def plan_stateless(snapshot: KnowledgeSnapshot, planning_input: PlanningInput) -> PlanningResult:
    """Build one deterministic public result from a complete detached knowledge snapshot."""

    service = next(
        (item for item in snapshot.services if item.semantic_id == planning_input.service_id), None
    )
    if service is None:
        return InconclusiveResult("unknown_service")
    if not service.is_active:
        return InconclusiveResult("inactive_service")

    validation = validate_submitted_facts(planning_input.facts, snapshot.fact_definitions)
    if validation.facts is None:
        return InvalidResult(
            tuple(
                PublicDiagnostic(item.code.partition(":")[0], item.path)
                for item in validation.diagnostics
            )
        )

    preparation = prepare_case(
        snapshot.fact_definitions,
        service,
        validation.facts,
        planning_input.evaluation_date,
    )
    if isinstance(preparation, CasePreparationConfigurationDefect):
        return _configuration_invalid()
    if isinstance(preparation, CasePreparationInvalid):
        return InvalidResult(
            tuple(
                PublicDiagnostic(item.code.partition(":")[0], item.path)
                for item in preparation.diagnostics
            )
        )
    assert isinstance(preparation, CasePreparationSuccess)

    selection = select_procedure(snapshot, service.semantic_id, preparation.prepared_facts)
    if isinstance(selection, SelectionQuestion):
        answers = tuple(
            AnswerDefinition(
                key,
                snapshot.fact_definitions[key].kind,
                snapshot.fact_definitions[key].enum_values,
                snapshot.fact_definitions[key].minimum,
            )
            for key in selection.question.resolved_fact_keys
            if key in snapshot.fact_definitions
        )
        if len(answers) != len(selection.question.resolved_fact_keys):
            return _configuration_invalid()
        return NextQuestionResult(
            service.semantic_id,
            PublicQuestion(selection.question.semantic_id, selection.question.text, answers),
        )
    if isinstance(selection, SelectionConfigurationDefect):
        return _configuration_invalid()
    if isinstance(selection, (SelectionUnsupported, SelectionInconclusive)):
        return InconclusiveResult(selection.reason_code)
    assert isinstance(selection, ProcedureSelected)

    resolution = resolve_procedure_version(
        snapshot, selection.procedure_semantic_id, planning_input.evaluation_date
    )
    if isinstance(resolution, ProcedureVersionConfigurationDefect):
        return _configuration_invalid()
    if not isinstance(resolution, ProcedureVersionResolved):
        return InconclusiveResult(resolution.reason_code)

    version_applicability = evaluate(
        resolution.version.applicability,
        preparation.prepared_facts.values,
        submitted_keys=preparation.prepared_facts.submitted_keys,
    )
    if version_applicability.value is TruthValue.UNKNOWN:
        return InconclusiveResult("procedure_version_applicability_unknown")
    if version_applicability.value is TruthValue.FALSE:
        return InconclusiveResult("procedure_version_not_applicable")

    checklist = select_checklist_items(
        resolution.version, preparation.prepared_facts, planning_input.evaluation_date
    )
    if checklist.missing_facts:
        return InconclusiveResult("checklist_applicability_unknown")
    if checklist.trust_inconclusive:
        return InconclusiveResult("checklist_trust_inconclusive")
    steps = select_steps(
        resolution.version, preparation.prepared_facts, planning_input.evaluation_date
    )
    warnings = select_warnings(
        resolution.version, preparation.prepared_facts, planning_input.evaluation_date
    )
    return PlanResult(
        service.semantic_id,
        selection.procedure_semantic_id,
        resolution.version.semantic_id,
        resolution.version.text,
        checklist.items,
        steps,
        warnings,
    )
