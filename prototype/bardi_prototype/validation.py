from __future__ import annotations

from collections.abc import Iterable, Mapping

from .contracts import FactDefinition, KnowledgeBundle, KnowledgeCatalog, Predicate
from .evaluator import validate_predicate
from .facts import FACT_DEFINITIONS


def _bundle_rules(bundle: KnowledgeBundle) -> Iterable[Predicate | None]:
    yield bundle.procedure.applicability
    for item in bundle.claims:
        yield item.applicability
    for item in bundle.steps:
        yield item.applicability
    for item in bundle.fees:
        yield item.applicability
    for item in bundle.service_points:
        yield item.applicability
    for item in bundle.unknowns:
        yield item.applicability


def validate_bundle(
    bundle: KnowledgeBundle,
    fact_definitions: Mapping[str, FactDefinition],
) -> tuple[str, ...]:
    diagnostics: list[str] = []
    for rule in _bundle_rules(bundle):
        for diagnostic in validate_predicate(rule, fact_definitions):
            if diagnostic not in diagnostics:
                diagnostics.append(diagnostic)
    return tuple(diagnostics)


def validate_catalog(catalog: KnowledgeCatalog) -> tuple[str, ...]:
    diagnostics: list[str] = []
    definitions = catalog.fact_definitions or FACT_DEFINITIONS

    for key, definition in definitions.items():
        if key != definition.key:
            diagnostics.append(f"fact_definition_key_mismatch:{key}")
        if definition.kind == "enum" and not definition.enum_values:
            diagnostics.append(f"empty_enum_definition:{key}")

    for goal_id, goal_entry in catalog.goals.items():
        if goal_entry.goal.id != goal_id:
            diagnostics.append(f"goal_key_mismatch:{goal_id}")
        for candidate in goal_entry.candidates:
            for diagnostic in validate_predicate(candidate.applicability, definitions):
                if diagnostic not in diagnostics:
                    diagnostics.append(diagnostic)

    for fixture_id, fixture in catalog.fixtures.items():
        if fixture_id != fixture.procedure.procedure_id:
            diagnostics.append(f"fixture_key_mismatch:{fixture_id}")
        for diagnostic in validate_bundle(fixture, definitions):
            if diagnostic not in diagnostics:
                diagnostics.append(diagnostic)

    question_ids: set[str] = set()
    for question in catalog.questions:
        if question.id in question_ids:
            diagnostics.append(f"duplicate_question_id:{question.id}")
        question_ids.add(question.id)
        definition = definitions.get(question.fact_key)
        if definition is None:
            diagnostics.append(f"unsupported_question_fact:{question.fact_key}")
        elif definition.derived:
            diagnostics.append(f"question_writes_derived_fact:{question.fact_key}")
        for key in question.resolved_keys:
            if key not in definitions:
                diagnostics.append(f"unsupported_question_resolved_fact:{key}")

    return tuple(dict.fromkeys(diagnostics))
