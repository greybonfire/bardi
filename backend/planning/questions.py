"""Deterministic Service Question resolution for consequential planning Facts."""

from __future__ import annotations

from dataclasses import dataclass

from .catalog import KnowledgeSnapshot, QuestionSnapshot, ServiceSnapshot
from .facts import PreparedFacts


@dataclass(frozen=True, slots=True)
class ConsequentialQuestion:
    question: QuestionSnapshot | None
    diagnostic_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostic_codes", tuple(self.diagnostic_codes))


def pick_consequential_question(
    snapshot: KnowledgeSnapshot,
    service: ServiceSnapshot,
    prepared_facts: PreparedFacts,
    missing_facts: frozenset[str],
    *,
    diagnostic_prefix: str,
) -> ConsequentialQuestion:
    """Resolve consequential derived Facts to source Facts and select one authored Question."""

    source_facts: set[str] = set()
    defects: set[str] = set()
    for key in missing_facts:
        definition = snapshot.fact_definitions.get(key)
        if definition is None:
            defects.add(f"unknown_fact:{key}")
            continue
        if not definition.derived:
            source_facts.add(key)
            continue
        dependencies = prepared_facts.missing_source_dependencies.get(key)
        if not dependencies or any(
            (dependency := snapshot.fact_definitions.get(source)) is None or dependency.derived
            for source in dependencies
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

    covering = tuple(
        question
        for question in service.questions
        if source_facts.intersection(question.resolved_fact_keys)
    )
    if not covering:
        return ConsequentialQuestion(None, (f"{diagnostic_prefix}:no_source_fact",))
    return ConsequentialQuestion(min(covering, key=lambda item: (item.priority, item.semantic_id)))
