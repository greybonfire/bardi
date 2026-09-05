"""Pure evidence trust assessment and compact provenance projection."""

from __future__ import annotations

from datetime import date

from .catalog import EvidenceLinkSnapshot, SourceSnapshot
from .public import PublicSource
from .trust import assess_trust


def source_is_current(source: SourceSnapshot, evaluation_date: date) -> bool:
    return (
        assess_trust(
            "current",
            evaluation_date=evaluation_date,
            effective_from=source.effective_from,
            effective_to=source.effective_to,
            retrieved_on=source.retrieved_on,
            reverify_on=source.reverify_on,
        ).disposition
        == "assert_current"
    )


def supporting_sources(
    links: tuple[EvidenceLinkSnapshot, ...], evaluation_date: date, *, official_only: bool = False
) -> tuple[PublicSource, ...] | None:
    """Return sorted supporting sources, or None for contradiction/unsupported evidence."""
    sources: dict[str, PublicSource] = {}
    contradiction = False
    for link in links:
        assessment = assess_trust(
            link.verification_state,
            evaluation_date=evaluation_date,
            effective_from=link.effective_from,
            effective_to=link.effective_to,
            retrieved_on=link.retrieved_on,
            verified_on=link.verified_on,
            reverify_on=link.reverify_on,
        )
        if assessment.disposition != "assert_current" or not link.sources:
            continue
        if not all(source_is_current(source, evaluation_date) for source in link.sources):
            continue
        if link.support_status == "contradicts":
            contradiction = True
            continue
        if link.support_status != "supports":
            continue
        if official_only and not all(
            source.classification == "official" for source in link.sources
        ):
            continue
        for source in link.sources:
            sources[source.semantic_id] = PublicSource(
                source.semantic_id,
                source.authority.semantic_id,
                source.title,
                source.locator,
                source.classification,
                source.retrieved_on,
            )
    if contradiction or not sources:
        return None
    return tuple(sources[key] for key in sorted(sources))
