"""Pure, deterministic Service Point routing with local uncertainty."""

from __future__ import annotations

from datetime import date
from typing import Literal, cast

from .catalog import EvidenceLinkSnapshot, KnowledgeSnapshot, ProcedureVersionSnapshot
from .evaluator import TruthValue, evaluate
from .facts import PreparedFacts
from .provenance import supporting_sources
from .public import PublicRouting, PublicServicePoint, PublicSource, RoutingStatus
from .trust import assess_trust


def select_service_points(
    snapshot: KnowledgeSnapshot,
    version: ProcedureVersionSnapshot,
    facts: PreparedFacts,
    evaluation_date: date,
) -> PublicRouting:
    """Evaluate every association without turning routing gaps into plan-wide questions."""

    points = {item.semantic_id: item for item in snapshot.service_points}
    versions = {item.semantic_id: item for item in snapshot.service_point_versions}
    destinations: list[PublicServicePoint] = []
    verification_sources: dict[str, PublicSource] = {}
    unresolved = not version.service_point_associations

    def add_verification_sources(
        *evidence_groups: tuple[EvidenceLinkSnapshot, ...],
    ) -> None:
        for evidence_links in evidence_groups:
            for link in evidence_links:
                if (
                    link.support_status != "supports"
                    or (link.effective_from and evaluation_date < link.effective_from)
                    or (link.retrieved_on and evaluation_date < link.retrieved_on)
                    or (link.verified_on and evaluation_date < link.verified_on)
                ):
                    continue
                for source in link.sources:
                    if source.retrieved_on > evaluation_date or (
                        source.effective_from and evaluation_date < source.effective_from
                    ):
                        continue
                    verification_sources[source.semantic_id] = PublicSource(
                        source.semantic_id,
                        source.authority.semantic_id,
                        source.title,
                        source.locator,
                        source.classification,
                        source.retrieved_on,
                    )

    for association in sorted(
        version.service_point_associations,
        key=lambda item: (item.service_point_version_id, item.semantic_id),
    ):
        if association.effective_from and evaluation_date < association.effective_from:
            continue
        if association.effective_to and evaluation_date > association.effective_to:
            continue

        association_trust = assess_trust(
            association.verification_state,
            evaluation_date=evaluation_date,
            verified_on=association.verified_on,
            reverify_on=association.reverify_on,
            effective_from=association.effective_from,
            effective_to=association.effective_to,
        )
        association_sources = supporting_sources(association.evidence_links, evaluation_date)
        if association_trust.disposition != "assert_current" or association_sources is None:
            unresolved = True
            add_verification_sources(association.evidence_links)
            continue

        applicability = evaluate(
            association.applicability, facts.values, submitted_keys=facts.submitted_keys
        )
        if applicability.value is TruthValue.FALSE:
            continue
        if applicability.value is TruthValue.UNKNOWN:
            unresolved = True
            add_verification_sources(association.evidence_links)
            continue

        material = versions.get(association.service_point_version_id)
        point = points.get(material.service_point_id) if material is not None else None
        if material is None or point is None:
            unresolved = True
            add_verification_sources(association.evidence_links)
            continue
        if (material.effective_from and evaluation_date < material.effective_from) or (
            material.effective_to and evaluation_date > material.effective_to
        ):
            unresolved = True
            add_verification_sources(association.evidence_links, material.evidence_links)
            continue
        material_trust = assess_trust(
            material.verification_state,
            evaluation_date=evaluation_date,
            verified_on=material.verified_on,
            reverify_on=material.reverify_on,
            effective_from=material.effective_from,
            effective_to=material.effective_to,
        )
        material_sources = supporting_sources(material.evidence_links, evaluation_date)
        if (
            material_trust.disposition != "assert_current"
            or material_sources is None
            or material.availability not in {"available", "unknown"}
        ):
            unresolved = True
            add_verification_sources(material.evidence_links)
            continue
        sources = {source.id: source for source in (*material_sources, *association_sources)}
        destinations.append(
            PublicServicePoint(
                point.semantic_id,
                material.semantic_id,
                association.semantic_id,
                point.text,
                material.address,
                cast(Literal["available", "unknown"], material.availability),
                material.effective_from,
                material.effective_to,
                tuple(sources[key] for key in sorted(sources)),
            )
        )

    destinations.sort(
        key=lambda item: (
            item.service_point_id,
            item.service_point_version_id,
            item.association_id,
        )
    )
    status = (
        "unresolved" if not destinations else "partially_resolved" if unresolved else "resolved"
    )
    return PublicRouting(
        cast(RoutingStatus, status),
        tuple(destinations),
        tuple(verification_sources[key] for key in sorted(verification_sources)),
    )


# Explicit domain-name alias for callers that prefer the full contract terminology.
select_service_point_routing = select_service_points
