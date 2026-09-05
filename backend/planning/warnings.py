"""Pure deterministic Warning selection."""

from __future__ import annotations

from datetime import date

from .catalog import ProcedureVersionSnapshot
from .evaluator import TruthValue, evaluate
from .facts import PreparedFacts
from .provenance import supporting_sources
from .public import PublicSource, PublicWarning
from .trust import assess_trust


def select_warnings(
    version: ProcedureVersionSnapshot, facts: PreparedFacts, evaluation_date: date
) -> tuple[PublicWarning, ...]:
    result: list[PublicWarning] = []
    for item in sorted(version.warnings, key=lambda row: (row.display_order, row.semantic_id)):
        if (
            item.effective_from
            and evaluation_date < item.effective_from
            or item.effective_to
            and evaluation_date > item.effective_to
        ):
            continue
        if (
            item.applicability is not None
            and evaluate(
                item.applicability, facts.values, submitted_keys=facts.submitted_keys
            ).value
            is not TruthValue.TRUE
        ):
            continue
        trust = assess_trust(
            item.verification_state,
            evaluation_date=evaluation_date,
            verified_on=item.verified_on,
            reverify_on=item.reverify_on,
        )
        if trust.disposition != "assert_current":
            continue
        sources: tuple[PublicSource, ...] | None
        if item.kind == "product":
            if item.evidence_links:
                continue
            sources = ()
        elif item.kind == "administrative":
            sources = supporting_sources(item.evidence_links, evaluation_date)
            if sources is None:
                continue
        else:
            continue
        result.append(
            PublicWarning(
                item.semantic_id,
                item.text,
                item.severity,
                item.kind,
                item.role,
                sources,
                trust.freshness,
            )
        )
    return tuple(result)
