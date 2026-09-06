"""Publication coverage gate for consequential Procedure-selection Facts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from django.conf import settings
from planning.case_preparation import DERIVED_FACT_DEPENDENCIES
from planning.facts import FactDefinition as DomainFactDefinition

from .domain import decode_stored_rule, referenced_fact_keys
from .models import ServiceProcedureCandidate, ServiceQuestion
from .publication import PublicationContext, PublicationDiagnostic


def _source_dependencies(
    key: str,
    definitions: Mapping[str, DomainFactDefinition],
    *,
    visiting: frozenset[str] = frozenset(),
) -> frozenset[str]:
    """Expand a referenced derived Fact to its pinned source dependencies."""

    definition = definitions.get(key)
    if definition is None or not definition.derived:
        return frozenset({key})
    if key in visiting:
        return frozenset({key})
    dependencies = DERIVED_FACT_DEPENDENCIES.get(key)
    if not dependencies:
        return frozenset({key})
    result: set[str] = set()
    for dependency in dependencies:
        result.update(
            _source_dependencies(dependency, definitions, visiting=visiting | frozenset({key}))
        )
    return frozenset(result)


class SelectionQuestionPublicationGate:
    """Require same-Service Questions for every candidate-selection source Fact."""

    name = "core.selection_questions"

    def validate(self, context: PublicationContext) -> Iterable[PublicationDiagnostic]:
        if not getattr(settings, "SELECTION_QUESTIONS_REQUIRED", True):
            return ()
        version = context.version
        candidates = tuple(
            ServiceProcedureCandidate.objects.filter(
                procedure=version.procedure,
                service=version.procedure.primary_service,
            ).order_by("pk")
        )
        failures: list[PublicationDiagnostic] = []
        required: set[str] = set()
        for candidate in candidates:
            decoded = decode_stored_rule(candidate.selection_predicate, context.fact_definitions)
            if decoded.diagnostics:
                failures.extend(
                    PublicationDiagnostic(self.name, diagnostic.code)
                    for diagnostic in decoded.diagnostics
                )
                continue
            assert decoded.predicate is not None
            for key in referenced_fact_keys(decoded.predicate):
                required.update(_source_dependencies(key, context.fact_definitions))

        covered: set[str] = set()
        questions = ServiceQuestion.objects.filter(
            service=version.procedure.primary_service
        ).prefetch_related("resolved_fact_links__fact")
        for question in questions:
            links = tuple(question.resolved_fact_links.all())
            if links:
                covered.update(link.fact.key for link in links if not link.fact.derived)
            elif not question.fact.derived:
                covered.add(question.fact.key)

        failures.extend(
            PublicationDiagnostic(self.name, "missing_service_question", key)
            for key in sorted(required - covered)
        )
        return tuple(failures)


__all__ = ("SelectionQuestionPublicationGate",)
