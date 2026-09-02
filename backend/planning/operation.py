"""Conservative pure planning operation for the staged #37 contract."""

from __future__ import annotations

from .catalog import KnowledgeSnapshot, ServiceSnapshot
from .facts import PreparedFacts, validate_submitted_facts
from .public import (
    AnswerDefinition,
    InconclusiveResult,
    InvalidResult,
    NextQuestionResult,
    PlanningInput,
    PlanningResult,
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
from .versions import (
    ProcedureVersionConfigurationDefect,
    ProcedureVersionResolved,
    resolve_procedure_version,
)


def _requires_case_preparation(snapshot: KnowledgeSnapshot, service: ServiceSnapshot) -> bool:
    if service.contradictions:
        return True
    for candidate in service.candidates:
        stack = [candidate.selection_predicate]
        while stack:
            predicate = stack.pop()
            if predicate.fact is not None:
                definition = snapshot.fact_definitions.get(predicate.fact)
                if definition is not None and definition.derived:
                    return True
            stack.extend(predicate.children)
    return False


def _configuration_invalid() -> InvalidResult:
    return InvalidResult((PublicDiagnostic("knowledge_configuration_invalid", ()),))


def plan_stateless(snapshot: KnowledgeSnapshot, planning_input: PlanningInput) -> PlanningResult:
    """Plan from detached values, stopping at each not-yet-implemented planning stage."""

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

    if _requires_case_preparation(snapshot, service):
        return InconclusiveResult("case_preparation_unavailable")

    prepared = PreparedFacts(validation.facts, frozenset(validation.facts), {})
    selection = select_procedure(snapshot, service.semantic_id, prepared)
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

    # Procedure-Version applicability and plan assembly belong to later planning work,
    # after #38's case-preparation stage.
    return InconclusiveResult("plan_assembly_unavailable")
