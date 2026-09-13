"""Runtime Missing-Fact Picker policy and selected-Question projection.

Callers own case preparation and which missing Facts are consequential. Picking requires
complete source coverage before ranking by priority and semantic ID; exact ties retain
Service Question order. Neither picker validates the winner's answers. Only question_result
projects them, without inspecting other Questions or changing phase-specific trust policy.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from .catalog import KnowledgeSnapshot, QuestionSnapshot, ServiceSnapshot
from .facts import PreparedFacts
from .public import (
    AnswerDefinition,
    InvalidResult,
    NextQuestionResult,
    PublicDiagnostic,
    PublicQuestion,
)


@dataclass(frozen=True, slots=True)
class ConsequentialQuestion:
    question: QuestionSnapshot | None
    diagnostic_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostic_codes", tuple(self.diagnostic_codes))


def pick_procedure_selection_question(
    snapshot: KnowledgeSnapshot,
    service: ServiceSnapshot,
    prepared_facts: PreparedFacts,
    missing_facts: frozenset[str],
) -> ConsequentialQuestion:
    """Pick an unchecked Question using the fixed legacy selection policy.

    Unlike the later-phase picker, absent Fact/dependency definitions may count as source
    Facts. If coverage succeeds but no Question intersects the source set, ranking retains
    min's ValueError. These handoff behaviors do not permit publishing malformed knowledge.
    """
    return _pick_question(
        snapshot,
        service,
        prepared_facts,
        missing_facts,
        profile="selection",
        diagnostic_prefix="missing_procedure_selection_question",
    )


def pick_consequential_question(
    snapshot: KnowledgeSnapshot,
    service: ServiceSnapshot,
    prepared_facts: PreparedFacts,
    missing_facts: frozenset[str],
    *,
    diagnostic_prefix: str,
) -> ConsequentialQuestion:
    """Pick an unchecked Question, requiring defined source Facts and dependencies.

    Expansion defects precede coverage defects. An empty covering set returns the
    no_source_fact diagnostic instead of raising. The required diagnostic_prefix is
    preserved verbatim; it labels coverage failures, not a configurable policy.
    """

    return _pick_question(
        snapshot,
        service,
        prepared_facts,
        missing_facts,
        profile="consequential",
        diagnostic_prefix=diagnostic_prefix,
    )


def _pick_question(
    snapshot: KnowledgeSnapshot,
    service: ServiceSnapshot,
    prepared_facts: PreparedFacts,
    missing_facts: frozenset[str],
    *,
    profile: Literal["selection", "consequential"],
    diagnostic_prefix: str,
) -> ConsequentialQuestion:
    source_facts: set[str] = set()
    defects: set[str] = set()
    for key in missing_facts:
        definition = snapshot.fact_definitions.get(key)
        if definition is None and profile == "consequential":
            defects.add(f"unknown_fact:{key}")
            continue
        if definition is None or not definition.derived:
            source_facts.add(key)
            continue
        dependencies = prepared_facts.missing_source_dependencies.get(key)
        if not dependencies or (
            any(
                snapshot.fact_definitions.get(source) is not None
                and snapshot.fact_definitions[source].derived
                for source in dependencies
            )
            if profile == "selection"
            else any(
                (dependency := snapshot.fact_definitions.get(source)) is None or dependency.derived
                for source in dependencies
            )
        ):
            defects.add(f"missing_source_dependencies:{key}")
        else:
            source_facts.update(dependencies)

    if defects:
        return ConsequentialQuestion(None, tuple(sorted(defects)))

    covered = {
        fact_key for question in service.questions for fact_key in question.resolved_fact_keys
    }
    uncovered = source_facts - covered
    if uncovered:
        return ConsequentialQuestion(
            None,
            tuple(f"{diagnostic_prefix}:{key}" for key in sorted(uncovered)),
        )

    covering: Iterable[QuestionSnapshot] = (
        question
        for question in service.questions
        if source_facts.intersection(question.resolved_fact_keys)
    )
    # Selection historically consumes the generator inside min (including its empty error).
    # Later phases finish filtering before comparing priorities; preserve that order too.
    if profile == "consequential":
        covering = tuple(covering)
        if not covering:
            return ConsequentialQuestion(None, (f"{diagnostic_prefix}:no_source_fact",))
    return ConsequentialQuestion(min(covering, key=lambda item: (item.priority, item.semantic_id)))


def question_result(
    snapshot: KnowledgeSnapshot,
    service_id: str,
    question: QuestionSnapshot,
) -> NextQuestionResult | InvalidResult:
    """Project every authored answer of the winner, or return sanitized invalid knowledge.

    Preserve answer order and duplicates. Metadata construction deliberately precedes
    absent/derived-key rejection; do not add earlier validation or a runner-up fallback.
    """
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
    if len(answers) != len(question.resolved_fact_keys) or any(
        snapshot.fact_definitions[key].derived for key in question.resolved_fact_keys
    ):
        return InvalidResult((PublicDiagnostic("knowledge_configuration_invalid", ()),))
    return NextQuestionResult(
        service_id,
        PublicQuestion(question.semantic_id, question.text, answers),
    )
