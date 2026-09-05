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
        trust = assess_trust(
            item.verification_state,
            evaluation_date=evaluation_date,
            effective_from=item.effective_from,
            effective_to=item.effective_to,
            verified_on=item.verified_on,
            reverify_on=item.reverify_on,
        )
        if item.role == "regeneration":
            # This is product safety policy rather than an external assertion. Publication
            # guarantees exactly one well-formed regeneration Warning whenever guidance is
            # authored, so it must survive ordinary applicability/trust/temporal filtering.
            if item.kind != "product" or item.severity != "important" or item.evidence_links:
                continue
            result.append(
                PublicWarning(
                    item.semantic_id,
                    item.text,
                    item.severity,
                    item.kind,
                    item.role,
                    (),
                    trust.freshness,
                )
            )
            continue
        if (
            item.effective_from is not None
            and evaluation_date < item.effective_from
            or item.effective_to is not None
            and evaluation_date > item.effective_to
        ):
            continue
        if item.applicability is not None:
            applicability = evaluate(
                item.applicability, facts.values, submitted_keys=facts.submitted_keys
            )
            if applicability.value is not TruthValue.TRUE:
                continue
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
