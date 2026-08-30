"""Date and publication aware Procedure-Version resolution.

The resolver deliberately knows nothing about rule truth.  It only chooses the
immutable snapshot for a stable Procedure; the planner evaluates that snapshot
afterwards.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .contracts import (
    KnowledgeBundle,
    KnowledgeCatalog,
    UpcomingProcedureVersion,
)


@dataclass(frozen=True)
class VersionResolution:
    bundle: KnowledgeBundle | None
    upcoming: tuple[KnowledgeBundle, ...] = ()
    historical: bool = False
    reason_code: str | None = None


_EXPLICIT_COLLECTIONS = (
    "versioned_fixtures",
    "versions",
    "procedure_versions",
    "version_collections",
)


def _legacy_values(
    catalog: KnowledgeCatalog,
    procedure_id: str,
) -> tuple[KnowledgeBundle, ...]:
    values: list[KnowledgeBundle] = []
    direct_legacy = catalog.fixtures.get(procedure_id)
    if direct_legacy is not None:
        values.append(direct_legacy)
    values.extend(
        bundle
        for key, bundle in catalog.fixtures.items()
        if key != procedure_id and bundle.procedure.procedure_id == procedure_id
    )
    return tuple(values)


def version_collection_conflicts(
    catalog: KnowledgeCatalog,
    procedure_id: str,
) -> tuple[str, ...]:
    """Return version IDs represented by unequal catalog records.

    The compatibility ``fixtures`` map and each version-collection alias may
    repeat an immutable snapshot, but repeated records must be equal. A
    different record with the same version ID would make that ID mutable.
    """
    representations: dict[str, list[KnowledgeBundle]] = {}
    explicit_ids: set[str] = set()
    has_explicit_collection = False
    for collection_name in _EXPLICIT_COLLECTIONS:
        collection = getattr(catalog, collection_name)
        if procedure_id in collection:
            has_explicit_collection = True
        for bundle in collection.get(procedure_id, ()):
            version_id = bundle.procedure.version_id
            explicit_ids.add(version_id)
            representations.setdefault(version_id, []).append(bundle)
    unmatched_legacy_ids: set[str] = set()
    for bundle in _legacy_values(catalog, procedure_id):
        version_id = bundle.procedure.version_id
        if has_explicit_collection and version_id not in explicit_ids:
            unmatched_legacy_ids.add(version_id)
        representations.setdefault(version_id, []).append(bundle)
    unequal_ids = {
        version_id
        for version_id, bundles in representations.items()
        if any(bundle != bundles[0] for bundle in bundles[1:])
    }
    return tuple(sorted(unequal_ids | unmatched_legacy_ids))


def _collection_values(catalog: KnowledgeCatalog, procedure_id: str) -> list[KnowledgeBundle]:
    """Return canonical versions without overwriting explicit snapshots."""
    values: list[KnowledgeBundle] = []
    seen: set[str] = set()
    for collection_name in _EXPLICIT_COLLECTIONS:
        collection = getattr(catalog, collection_name)
        for bundle in collection.get(procedure_id, ()):
            version_id = bundle.procedure.version_id
            if version_id not in seen:
                values.append(bundle)
                seen.add(version_id)

    # Legacy-only catalogs continue to work. Once an explicit collection is
    # present, an unmatched legacy record is retained for validation to reject,
    # never silently folded into or used to replace the collection.
    for legacy in _legacy_values(catalog, procedure_id):
        if legacy.procedure.version_id not in seen:
            values.append(legacy)
            seen.add(legacy.procedure.version_id)
        # Equal legacy representations are already covered by the explicit
        # record; unequal ones are reported by version_collection_conflicts.
    return values


def bundles_for_procedure(
    catalog: KnowledgeCatalog,
    procedure_id: str,
) -> tuple[KnowledgeBundle, ...]:
    return tuple(
        sorted(
            _collection_values(catalog, procedure_id),
            key=lambda bundle: (
                bundle.procedure.effective_from
                if type(bundle.procedure.effective_from) is date
                else date.min,
                str(bundle.procedure.version_id),
            ),
        )
    )


def _in_interval(value: date, start: date | None, end: date | None) -> bool:
    if type(value) is not date:
        return False
    if start is not None and type(start) is not date:
        return False
    if end is not None and type(end) is not date:
        return False
    return (start is None or value >= start) and (end is None or value <= end)


def resolve_procedure_version(
    catalog: KnowledgeCatalog,
    procedure_id: str,
    evaluation_date: date,
    *,
    version_id: str | None = None,
) -> VersionResolution:
    if version_collection_conflicts(catalog, procedure_id):
        return VersionResolution(
            None,
            reason_code="conflicting_procedure_version_representations",
        )
    versions = bundles_for_procedure(catalog, procedure_id)
    if version_id is not None:
        requested = next(
            (bundle for bundle in versions if bundle.procedure.version_id == version_id),
            None,
        )
        if requested is None:
            return VersionResolution(None, reason_code="unknown_procedure_version")
        if requested.procedure.publication_state == "draft":
            return VersionResolution(None, reason_code="draft_procedure_version")
        if requested.procedure.publication_state not in ("published", "withdrawn"):
            return VersionResolution(None, reason_code="unknown_publication_state")
        if requested.procedure.publication_state == "withdrawn":
            if not _in_interval(
                evaluation_date,
                requested.procedure.effective_from,
                requested.procedure.effective_to,
            ):
                return VersionResolution(
                    None,
                    reason_code="procedure_version_outside_effective_interval",
                )
            return VersionResolution(requested, historical=True)
        if (
            requested.procedure.effective_from is not None
            and type(requested.procedure.effective_from) is date
            and evaluation_date < requested.procedure.effective_from
        ):
            return VersionResolution(
                None,
                upcoming=(requested,),
                reason_code="procedure_version_not_yet_effective",
            )
        if (
            requested.procedure.effective_to is not None
            and type(requested.procedure.effective_to) is date
            and evaluation_date > requested.procedure.effective_to
        ):
            return VersionResolution(requested, historical=True)
        if not _in_interval(
            evaluation_date,
            requested.procedure.effective_from,
            requested.procedure.effective_to,
        ):
            return VersionResolution(None, reason_code="procedure_version_outside_effective_interval")
        return VersionResolution(requested)

    published = tuple(
        bundle
        for bundle in versions
        if bundle.procedure.publication_state == "published"
    )
    current = tuple(
        bundle
        for bundle in published
        if _in_interval(
            evaluation_date,
            bundle.procedure.effective_from,
            bundle.procedure.effective_to,
        )
    )
    upcoming = tuple(
        sorted(
            (
                bundle
                for bundle in published
                if bundle.procedure.effective_from is not None
                and bundle.procedure.effective_from > evaluation_date
            ),
            key=lambda bundle: (
                bundle.procedure.effective_from
                if type(bundle.procedure.effective_from) is date
                else date.max,
                str(bundle.procedure.version_id),
            ),
        )
    )
    if len(current) == 1:
        return VersionResolution(current[0], upcoming=upcoming)
    if len(current) > 1:
        # Catalog validation normally catches this. Keeping a failure here
        # makes direct use safe as well.
        return VersionResolution(None, upcoming=upcoming, reason_code="overlapping_published_procedure_versions")
    if upcoming:
        return VersionResolution(None, upcoming=upcoming, reason_code="procedure_version_not_yet_effective")
    if published:
        return VersionResolution(None, reason_code="no_applicable_procedure_version")
    if any(bundle.procedure.publication_state == "draft" for bundle in versions):
        return VersionResolution(None, reason_code="procedure_version_not_published")
    if any(bundle.procedure.publication_state == "withdrawn" for bundle in versions):
        return VersionResolution(None, reason_code="withdrawn_procedure_version")
    return VersionResolution(None, reason_code="no_applicable_procedure_version")


def upcoming_projection(
    bundles: Iterable[KnowledgeBundle],
    locale: str,
) -> tuple[UpcomingProcedureVersion, ...]:
    return tuple(
        UpcomingProcedureVersion(
            procedure_id=bundle.procedure.procedure_id,
            procedure_version_id=bundle.procedure.version_id,
            procedure=bundle.procedure.text.render(locale),
            effective_from=bundle.procedure.effective_from,
            effective_to=bundle.procedure.effective_to,
            publication_state=bundle.procedure.publication_state,
        )
        for bundle in bundles
    )


# Descriptive public alias used by callers migrating to the versioned catalog.
select_procedure_version = resolve_procedure_version


def resolve_bundle_version(
    bundle: KnowledgeBundle,
    evaluation_date: date,
    *,
    version_id: str | None = None,
) -> VersionResolution:
    """Resolve a direct bundle while retaining the direct-input API."""
    if version_id is not None and version_id != bundle.procedure.version_id:
        return VersionResolution(None, reason_code="unknown_procedure_version")
    state = bundle.procedure.publication_state
    if state == "draft":
        return VersionResolution(None, reason_code="draft_procedure_version")
    if state == "withdrawn" and version_id is None:
        return VersionResolution(None, reason_code="withdrawn_procedure_version")
    if state == "withdrawn":
        if not _in_interval(
            evaluation_date,
            bundle.procedure.effective_from,
            bundle.procedure.effective_to,
        ):
            return VersionResolution(
                None,
                reason_code="procedure_version_outside_effective_interval",
            )
        return VersionResolution(bundle, historical=True)
    if (
        bundle.procedure.effective_from is not None
        and type(bundle.procedure.effective_from) is date
        and bundle.procedure.effective_from > evaluation_date
    ):
        return VersionResolution(
            None,
            upcoming=(bundle,),
            reason_code="procedure_version_not_yet_effective",
        )
    if (
        bundle.procedure.effective_to is not None
        and type(bundle.procedure.effective_to) is date
        and bundle.procedure.effective_to < evaluation_date
        and version_id is not None
    ):
        return VersionResolution(bundle, historical=True)
    if not _in_interval(
        evaluation_date,
        bundle.procedure.effective_from,
        bundle.procedure.effective_to,
    ):
        return VersionResolution(None, reason_code="procedure_version_outside_effective_interval")
    return VersionResolution(bundle)
