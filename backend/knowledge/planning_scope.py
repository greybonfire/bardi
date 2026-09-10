"""Private graph discovery for service-scoped planning snapshots.

The public planner still receives a complete immutable ``KnowledgeSnapshot``.  This
module only decides which persisted graph rows are allowed to enter that snapshot;
it deliberately does not apply planning predicates, dates, trust, or publication
selection beyond the public/withdrawn version boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from django.db.models import Q


@dataclass(frozen=True, slots=True)
class PlanningScope:
    """The persisted identifiers belonging to one requested Service graph.

    An empty set is an explicit empty graph.  Callers must never interpret it as a
    request to omit a filter.
    """

    service_id: str
    procedure_ids: frozenset[int] = frozenset()
    version_ids: frozenset[int] = frozenset()
    association_ids: frozenset[int] = frozenset()
    material_ids: frozenset[int] = frozenset()
    evidence_link_ids: frozenset[int] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "procedure_ids", frozenset(self.procedure_ids))
        object.__setattr__(self, "version_ids", frozenset(self.version_ids))
        object.__setattr__(self, "association_ids", frozenset(self.association_ids))
        object.__setattr__(self, "material_ids", frozenset(self.material_ids))
        object.__setattr__(self, "evidence_link_ids", frozenset(self.evidence_link_ids))


def _empty_scope(service_id: str) -> PlanningScope:
    return PlanningScope(service_id)


def _discover_procedure_graph(
    initial_procedure_ids: Iterable[int],
    versions_for: Callable[[set[int]], Iterable[int]],
    targets_for: Callable[[set[int]], Iterable[int]],
) -> tuple[frozenset[int], frozenset[int]]:
    """Close a blocking-dependency graph in batched stages, including cycles safely."""

    frontier = set(initial_procedure_ids)
    visited: set[int] = set()
    version_ids: set[int] = set()
    while frontier:
        current = frontier - visited
        if not current:
            break
        visited.update(current)
        current_version_ids = {int(value) for value in versions_for(current)}
        version_ids.update(current_version_ids)
        frontier = {int(value) for value in targets_for(current_version_ids)} - visited
    return frozenset(visited), frozenset(version_ids)


def discover_planning_scope(service_id: str) -> PlanningScope:
    """Discover the bounded Procedure/version/dependency graph for ``service_id``.

    Dependencies are traversed in batched Procedure frontiers.  A Procedure is marked
    visited before its versions are inspected, which makes cycles terminate and also
    preserves the important distinction between a known target and a target with no
    public versions.
    """

    # Runtime imports avoid model-registration cycles during AppConfig model loading.
    from .models import EvidenceLink, ProcedureVersion, Service, ServiceProcedureCandidate
    from .procedure_dependencies import ProcedureDependency
    from .service_point_routing import ProcedureServicePointAssociation

    service = Service.objects.filter(semantic_id=service_id).values("pk").first()
    if service is None:
        return _empty_scope(service_id)

    initial_procedure_ids = set(
        ServiceProcedureCandidate.objects.filter(service_id=service["pk"]).values_list(
            "procedure_id", flat=True
        )
    )
    procedure_ids, version_ids = _discover_procedure_graph(
        initial_procedure_ids,
        lambda procedure_ids: (
            row["id"]
            for row in ProcedureVersion.objects.filter(
                procedure_id__in=procedure_ids,
                state__in=(
                    ProcedureVersion.State.PUBLISHED,
                    ProcedureVersion.State.WITHDRAWN,
                ),
            ).values("id")
        ),
        lambda version_ids: ProcedureDependency.objects.filter(
            procedure_version_id__in=version_ids,
            relation=ProcedureDependency.Relation.BLOCKING_PREREQUISITE,
        ).values_list("target_procedure_id", flat=True),
    )

    associations = list(
        ProcedureServicePointAssociation.objects.filter(
            procedure_version_id__in=version_ids
        ).values("id", "service_point_version_id")
    )
    association_ids = {int(row["id"]) for row in associations}
    material_ids = {int(row["service_point_version_id"]) for row in associations}

    # The workflow anchor may be any link of a graph owner, including a shared
    # ServicePointVersion.  Keep every such link, not just one preferred anchor.
    owner_filter = (
        Q(checklist_item__procedure_version_id__in=version_ids)
        | Q(step__procedure_version_id__in=version_ids)
        | Q(warning__procedure_version_id__in=version_ids)
        | Q(fee__procedure_version_id__in=version_ids)
        | Q(eligibility_basis__procedure_version_id__in=version_ids)
        | Q(procedure_dependency__procedure_version_id__in=version_ids)
        | Q(procedure_service_point_association_id__in=association_ids)
        | Q(service_point_version_id__in=material_ids)
    )
    evidence_link_ids = set(EvidenceLink.objects.filter(owner_filter).values_list("id", flat=True))

    return PlanningScope(
        service_id,
        procedure_ids,
        version_ids,
        frozenset(association_ids),
        frozenset(material_ids),
        frozenset(evidence_link_ids),
    )


__all__ = ("PlanningScope", "discover_planning_scope")
