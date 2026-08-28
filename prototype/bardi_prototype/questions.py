from __future__ import annotations

from .contracts import KnowledgeCatalog, QuestionDefinition


def pick_question(
    catalog: KnowledgeCatalog,
    goal_id: str,
    missing_facts: frozenset[str],
) -> QuestionDefinition | None:
    """Pick the highest-priority authored Question that can resolve an UNKNOWN."""
    questions = sorted(
        (question for question in catalog.questions if question.goal_id == goal_id),
        key=lambda question: (question.priority, question.id),
    )
    return next(
        (
            question
            for question in questions
            if missing_facts.intersection(question.resolved_keys)
        ),
        None,
    )
