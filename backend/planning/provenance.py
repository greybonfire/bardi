"""Pure evidence trust assessment and compact provenance projection."""

from __future__ import annotations

from datetime import date

from .catalog import EvidenceLinkSnapshot, SourceSnapshot
from .public import PublicSource
from .trust import assess_trust


def _public_source(source: SourceSnapshot) -> PublicSource:
    return PublicSource(
        source.semantic_id,
        source.authority.semantic_id,
        source.title,
        source.locator,
        source.classification,
        source.retrieved_on,
    )


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
    """Return sorted current supporting sources, or None for contradiction/unsupported evidence."""
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
            sources[source.semantic_id] = _public_source(source)
    if contradiction or not sources:
        return None
    return tuple(sources[key] for key in sorted(sources))


def claim_sources(links: tuple[EvidenceLinkSnapshot, ...]) -> tuple[PublicSource, ...]:
    """Project preserved supporting provenance without asserting that it is current.

    Fees whose current value is inconclusive still benefit from compact provenance for the
    researched prior/candidate value. Contradicting/context-only links are deliberately not
    presented as support, and no editorial EvidenceLink fields cross this boundary.
    """
    sources: dict[str, PublicSource] = {}
    for link in links:
        if link.support_status != "supports":
            continue
        for source in link.sources:
            sources[source.semantic_id] = _public_source(source)
    return tuple(sources[key] for key in sorted(sources))
