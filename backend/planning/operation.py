"""Conservative pure planning operation for the stateless public contract."""

from __future__ import annotations

from dataclasses import replace

from .case_preparation import (
    CasePreparationConfigurationDefect,
    CasePreparationInvalid,
    CasePreparationSuccess,
    prepare_case,
)
from .catalog import KnowledgeSnapshot, QuestionSnapshot
from .checklists import select_checklist_items
from .eligibility_bases import select_eligibility_bases
from .evaluator import TruthValue, evaluate
from .facts import validate_submitted_facts
from .fees import select_fees
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
from .questions import pick_consequential_question
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


def _question_result(
    snapshot: KnowledgeSnapshot,
    service_id: str,
    question: QuestionSnapshot,
) -> NextQuestionResult | InvalidResult:
    answers = tuple(
        AnswerDefinition(
            key,
            snapshot.fact_definitions[key].kind,
            snapshot.fact_definitions[key].enum_values,
            snapshot.fact_definitions[key].minimum,
        )
        for key in question.resolved_fact_keys
        if key in snapshot.fact_definitions
    )
    if len(answers) != len(question.resolved_fact_keys):
        return _configuration_invalid()
    return NextQuestionResult(
        service_id,
        PublicQuestion(question.semantic_id, question.text, answers),
    )


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
        return _question_result(snapshot, service.semantic_id, selection.question)
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

    bases = select_eligibility_bases(
        resolution.version,
        preparation.prepared_facts,
        planning_input.evaluation_date,
    )
    if bases.configuration_invalid:
        return _configuration_invalid()
    if bases.missing_facts:
        question = pick_consequential_question(
            snapshot,
            service,
            preparation.prepared_facts,
            bases.missing_facts,
            diagnostic_prefix="missing_eligibility_basis_question",
        )
        if question.diagnostic_codes or question.question is None:
            return _configuration_invalid()
        return _question_result(snapshot, service.semantic_id, question.question)
    if bases.no_applicable_basis:
        return InconclusiveResult("no_applicable_eligibility_basis")

    matched_basis_ids = bases.trusted_matched_basis_ids
    checklist = select_checklist_items(
        resolution.version,
        preparation.prepared_facts,
        planning_input.evaluation_date,
        matched_basis_ids=matched_basis_ids,
    )
    if checklist.basis_resolution_required:
        return _configuration_invalid()
    if checklist.missing_facts:
        return InconclusiveResult("checklist_applicability_unknown")
    if checklist.trust_inconclusive:
        return InconclusiveResult("checklist_trust_inconclusive")
    steps = select_steps(
        resolution.version,
        preparation.prepared_facts,
        planning_input.evaluation_date,
        matched_basis_ids=matched_basis_ids,
    )
    if steps.basis_resolution_required:
        return _configuration_invalid()
    if steps.missing_facts:
        return InconclusiveResult("step_applicability_unknown")
    if steps.trust_inconclusive:
        return InconclusiveResult("step_trust_inconclusive")
    fees = select_fees(
        resolution.version,
        preparation.prepared_facts,
        planning_input.evaluation_date,
        matched_basis_ids=matched_basis_ids,
    )
    if fees.basis_resolution_required:
        return _configuration_invalid()
    if fees.missing_facts:
        return InconclusiveResult("fee_applicability_unknown")
    warnings = select_warnings(
        resolution.version, preparation.prepared_facts, planning_input.evaluation_date
    )
    public_bases = tuple(
        replace(
            basis,
            checklist_item_ids=tuple(
                item.id for item in checklist.items if item.eligibility_basis_id == basis.id
            ),
            step_ids=tuple(
                item.id for item in steps.items if item.eligibility_basis_id == basis.id
            ),
        )
        for basis in bases.bases
    )
    return PlanResult(
        service.semantic_id,
        selection.procedure_semantic_id,
        resolution.version.semantic_id,
        resolution.version.text,
        checklist_items=checklist.items,
        steps=steps.items,
        warnings=warnings,
        fees=fees.items,
        eligibility_bases=public_bases,
        inconclusive_basis_ids=bases.inconclusive_basis_ids,
    )
