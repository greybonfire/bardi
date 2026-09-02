"""Pure, deterministic Procedure selection from an immutable knowledge snapshot."""

from __future__ import annotations

from dataclasses import dataclass

from .catalog import KnowledgeSnapshot, QuestionSnapshot
from .evaluator import Evaluation, TruthValue, evaluate
from .facts import PreparedFacts


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    candidate_semantic_id: str
    evaluation: Evaluation


@dataclass(frozen=True, slots=True)
class ProcedureSelected:
    procedure_semantic_id: str
    evaluations: tuple[CandidateEvaluation, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluations", tuple(self.evaluations))


@dataclass(frozen=True, slots=True)
class SelectionQuestion:
    question: QuestionSnapshot
    evaluations: tuple[CandidateEvaluation, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluations", tuple(self.evaluations))


@dataclass(frozen=True, slots=True)
class SelectionUnsupported:
    reason_code: str
    evaluations: tuple[CandidateEvaluation, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluations", tuple(self.evaluations))


@dataclass(frozen=True, slots=True)
class SelectionInconclusive:
    reason_code: str
    candidate_semantic_ids: tuple[str, ...]
    evaluations: tuple[CandidateEvaluation, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_semantic_ids", tuple(self.candidate_semantic_ids))
        object.__setattr__(self, "evaluations", tuple(self.evaluations))


@dataclass(frozen=True, slots=True)
class SelectionConfigurationDefect:
    diagnostic_codes: tuple[str, ...]
    evaluations: tuple[CandidateEvaluation, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostic_codes", tuple(self.diagnostic_codes))
        object.__setattr__(self, "evaluations", tuple(self.evaluations))


type SelectionOutcome = (
    ProcedureSelected
    | SelectionQuestion
    | SelectionUnsupported
    | SelectionInconclusive
    | SelectionConfigurationDefect
)


def select_procedure(
    snapshot: KnowledgeSnapshot,
    service_semantic_id: str,
    prepared_facts: PreparedFacts,
) -> SelectionOutcome:
    """Evaluate every curated candidate once, without scoring or version applicability.

    ``prepared_facts`` is a trusted internal handoff. The production application path must
    establish validation, deterministic derivation, and contradiction rejection before
    calling this selector; issue #38 owns that orchestration.
    """

    service = next(
        (item for item in snapshot.services if item.semantic_id == service_semantic_id), None
    )
    if service is None:
        return SelectionUnsupported("unknown_service", ())
    if not service.is_active:
        return SelectionUnsupported("inactive_service", ())

    evaluations = tuple(
        CandidateEvaluation(
            candidate.procedure_semantic_id,
            evaluate(
                candidate.selection_predicate,
                prepared_facts.values,
                submitted_keys=prepared_facts.submitted_keys,
            ),
        )
        for candidate in sorted(service.candidates, key=lambda item: item.procedure_semantic_id)
    )
    matching_ids = tuple(
        item.candidate_semantic_id
        for item in evaluations
        if item.evaluation.value is TruthValue.TRUE
    )
    has_unknown = any(item.evaluation.value is TruthValue.UNKNOWN for item in evaluations)

    if len(matching_ids) > 1:
        return SelectionInconclusive("multiple_matching_procedures", matching_ids, evaluations)
    if len(matching_ids) == 1 and not has_unknown:
        return ProcedureSelected(matching_ids[0], evaluations)
    if not matching_ids and not has_unknown:
        return SelectionUnsupported("no_matching_researched_procedure", evaluations)

    consequential = frozenset().union(
        *(
            item.evaluation.missing_facts
            for item in evaluations
            if item.evaluation.value is TruthValue.UNKNOWN
        )
    )
    source_facts: set[str] = set()
    dependency_defects: set[str] = set()
    for key in consequential:
        definition = snapshot.fact_definitions.get(key)
        if definition is None or not definition.derived:
            source_facts.add(key)
            continue
        dependencies = prepared_facts.missing_source_dependencies.get(key)
        if not dependencies or any(
            snapshot.fact_definitions.get(source) is not None
            and snapshot.fact_definitions[source].derived
            for source in dependencies
        ):
            dependency_defects.add(f"missing_source_dependencies:{key}")
        else:
            source_facts.update(dependencies)

    if dependency_defects:
        return SelectionConfigurationDefect(tuple(sorted(dependency_defects)), evaluations)

    covered = {
        fact_key for question in service.questions for fact_key in question.resolved_fact_keys
    }
    uncovered = source_facts - covered
    if uncovered:
        return SelectionConfigurationDefect(
            tuple(f"missing_procedure_selection_question:{key}" for key in sorted(uncovered)),
            evaluations,
        )

    covering_questions = (
        question
        for question in service.questions
        if source_facts.intersection(question.resolved_fact_keys)
    )
    question = min(covering_questions, key=lambda item: (item.priority, item.semantic_id))
    return SelectionQuestion(question, evaluations)
