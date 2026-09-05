"""One-level direct Procedure prerequisite evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .catalog import KnowledgeSnapshot, ProcedureDependencySnapshot, ProcedureVersionSnapshot
from .evaluator import TruthValue, evaluate
from .facts import PreparedFacts
from .provenance import claim_sources, supporting_sources
from .public import PublicProcedureDependency
from .trust import assess_trust
from .versions import (
    ProcedureVersionConfigurationDefect,
    ProcedureVersionResolved,
    resolve_procedure_version,
)


@dataclass(frozen=True, slots=True)
class ProcedureDependencySelection:
    dependencies: tuple[PublicProcedureDependency, ...]
    missing_facts: frozenset[str] = frozenset()
    configuration_invalid: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        object.__setattr__(self, "missing_facts", frozenset(self.missing_facts))


def _inside_effective_interval(
    dependency: ProcedureDependencySnapshot, evaluation_date: date
) -> bool:
    return not (
        dependency.effective_from is not None
        and evaluation_date < dependency.effective_from
        or dependency.effective_to is not None
        and evaluation_date > dependency.effective_to
    )


def select_procedure_dependencies(
    snapshot: KnowledgeSnapshot,
    version: ProcedureVersionSnapshot,
    facts: PreparedFacts,
    evaluation_date: date,
) -> ProcedureDependencySelection:
    """Evaluate direct prerequisites without recursively planning their targets."""

    selected: list[PublicProcedureDependency] = []
    missing: set[str] = set()
    configuration_invalid = False

    for dependency in sorted(
        version.dependencies,
        key=lambda item: (item.display_order, item.semantic_id),
    ):
        if not _inside_effective_interval(dependency, evaluation_date):
            continue
        if dependency.relation != "blocking_prerequisite" or dependency.satisfied_when is None:
            configuration_invalid = True
            continue

        trust = assess_trust(
            dependency.verification_state,
            evaluation_date=evaluation_date,
            verified_on=dependency.verified_on,
            reverify_on=dependency.reverify_on,
            effective_from=dependency.effective_from,
            effective_to=dependency.effective_to,
        )
        applicability = evaluate(
            dependency.applicability,
            facts.values,
            submitted_keys=facts.submitted_keys,
        )

        if trust.disposition != "assert_current":
            if applicability.value is TruthValue.FALSE:
                continue
            selected.append(
                PublicProcedureDependency(
                    dependency.semantic_id,
                    dependency.text,
                    dependency.relation,
                    "inconclusive",
                    dependency.target_procedure_id,
                    dependency.target_procedure_text,
                    None,
                    claim_sources(dependency.evidence_links),
                    trust.freshness,
                )
            )
            continue

        if applicability.value is TruthValue.FALSE:
            continue
        if applicability.value is TruthValue.UNKNOWN:
            missing.update(applicability.missing_facts)
            continue

        satisfied = evaluate(
            dependency.satisfied_when,
            facts.values,
            submitted_keys=facts.submitted_keys,
        )
        if satisfied.value is TruthValue.UNKNOWN:
            missing.update(satisfied.missing_facts)
            continue

        sources = supporting_sources(dependency.evidence_links, evaluation_date)
        if sources is None:
            configuration_invalid = True
            continue

        target = resolve_procedure_version(
            snapshot,
            dependency.target_procedure_id,
            evaluation_date,
        )
        target_version_id = (
            target.version.semantic_id if isinstance(target, ProcedureVersionResolved) else None
        )
        if satisfied.value is TruthValue.TRUE:
            status = "satisfied"
        elif isinstance(target, ProcedureVersionResolved):
            status = "blocking"
        elif isinstance(target, ProcedureVersionConfigurationDefect):
            status = "inconclusive"
        else:
            status = "unsupported_target"

        selected.append(
            PublicProcedureDependency(
                dependency.semantic_id,
                dependency.text,
                dependency.relation,
                status,
                dependency.target_procedure_id,
                dependency.target_procedure_text,
                target_version_id,
                sources,
                trust.freshness,
            )
        )

    return ProcedureDependencySelection(
        tuple(selected),
        frozenset(missing),
        configuration_invalid,
    )


__all__ = ("ProcedureDependencySelection", "select_procedure_dependencies")
