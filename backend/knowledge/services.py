"""Transactional operations for catalog relationships."""

from __future__ import annotations

from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.db import transaction

from .domain import decode_stored_rule, diagnostic_messages, referenced_fact_keys
from .models import (
    FactDefinition,
    GoalContradiction,
    GoalContradictionFact,
    GoalProcedureCandidate,
    GoalQuestion,
    GoalQuestionResolvedFact,
)


@transaction.atomic
def save_candidate(candidate: GoalProcedureCandidate) -> GoalProcedureCandidate:
    candidate.full_clean()
    candidate.save()
    return candidate


def _materialize_facts(facts: Iterable[FactDefinition]) -> tuple[FactDefinition, ...]:
    values = tuple(facts)
    if len({fact.pk for fact in values}) != len(values):
        raise ValidationError("Fact sequences cannot contain duplicates.")
    if any(fact.pk is None for fact in values):
        raise ValidationError("Fact definitions must be saved first.")
    return values


@transaction.atomic
def set_question_resolved_facts(
    question: GoalQuestion, facts: Iterable[FactDefinition]
) -> GoalQuestion:
    values = _materialize_facts(facts)
    question.full_clean(exclude=("resolves_facts",))
    if any(fact.derived for fact in values):
        raise ValidationError("Questions may resolve source Facts only.")
    if values and question.fact_id not in {fact.pk for fact in values}:
        raise ValidationError("Explicit resolved Facts must include the primary Fact.")
    # Validation precedes replacement so a rejected proposal cannot destroy current rows.
    question.resolved_fact_links.all().delete()
    GoalQuestionResolvedFact.objects.bulk_create(
        GoalQuestionResolvedFact(question=question, fact=fact, position=index)
        for index, fact in enumerate(values, start=1)
    )
    question.full_clean(exclude=("resolves_facts",))
    return question


@transaction.atomic
def set_contradiction_facts(
    contradiction: GoalContradiction, facts: Iterable[FactDefinition]
) -> GoalContradiction:
    values = _materialize_facts(facts)
    if len(values) < 2:
        raise ValidationError("A contradiction requires at least two declared Facts.")
    if any(fact.derived for fact in values):
        raise ValidationError("Contradictions may declare source Facts only.")
    result = decode_stored_rule(contradiction.condition)
    if result.diagnostics:
        raise ValidationError({"condition": diagnostic_messages(result)})
    assert result.predicate is not None
    if {fact.key for fact in values} != set(referenced_fact_keys(result.predicate)):
        raise ValidationError("Declared Facts must exactly match condition references.")
    contradiction.clean_fields(exclude=("facts",))
    contradiction.validate_unique()
    contradiction.validate_constraints()
    contradiction.fact_links.all().delete()
    GoalContradictionFact.objects.bulk_create(
        GoalContradictionFact(contradiction=contradiction, fact=fact, position=index)
        for index, fact in enumerate(values, start=1)
    )
    contradiction.full_clean(exclude=("facts",))
    return contradiction


def validate_core_catalog() -> None:
    from .models import FactDefinition, Goal, Procedure

    for model in (
        Goal,
        Procedure,
        FactDefinition,
        GoalProcedureCandidate,
        GoalQuestion,
        GoalContradiction,
    ):
        for instance in model.objects.all():
            instance.full_clean()
