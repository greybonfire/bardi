"""Pure, deterministic Procedure-Version date resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .catalog import KnowledgeSnapshot, ProcedureVersionSnapshot


@dataclass(frozen=True, slots=True)
class ProcedureVersionResolved:
    version: ProcedureVersionSnapshot
    upcoming: tuple[ProcedureVersionSnapshot, ...]
    historical: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "upcoming", tuple(self.upcoming))


@dataclass(frozen=True, slots=True)
class ProcedureVersionUnavailable:
    reason_code: str
    upcoming: tuple[ProcedureVersionSnapshot, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "upcoming", tuple(self.upcoming))


@dataclass(frozen=True, slots=True)
class ProcedureVersionConfigurationDefect:
    diagnostic_codes: tuple[str, ...]
    conflicting_version_ids: tuple[str, ...]
    upcoming: tuple[ProcedureVersionSnapshot, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostic_codes", tuple(sorted(self.diagnostic_codes)))
        object.__setattr__(
            self, "conflicting_version_ids", tuple(sorted(self.conflicting_version_ids))
        )
        object.__setattr__(self, "upcoming", tuple(self.upcoming))


type ProcedureVersionResolutionOutcome = (
    ProcedureVersionResolved | ProcedureVersionUnavailable | ProcedureVersionConfigurationDefect
)
type ProcedureVersionResolution = ProcedureVersionResolutionOutcome


def _version_key(version: ProcedureVersionSnapshot) -> tuple[date, str]:
    return (version.effective_from or date.min, version.semantic_id)


def _upcoming(
    versions: tuple[ProcedureVersionSnapshot, ...], evaluation_date: date
) -> tuple[ProcedureVersionSnapshot, ...]:
    return tuple(
        sorted(
            (
                version
                for version in versions
                if version.state == "published"
                and type(version.effective_from) is date
                and version.effective_from > evaluation_date
            ),
            key=_version_key,
        )
    )


def _contains(version: ProcedureVersionSnapshot, value: date) -> bool:
    return (version.effective_from is None or version.effective_from <= value) and (
        version.effective_to is None or value <= version.effective_to
    )


def _overlap(left: ProcedureVersionSnapshot, right: ProcedureVersionSnapshot) -> bool:
    return (
        left.effective_from is None
        or right.effective_to is None
        or left.effective_from <= right.effective_to
    ) and (
        right.effective_from is None
        or left.effective_to is None
        or right.effective_from <= left.effective_to
    )


def resolve_procedure_version(
    snapshot: KnowledgeSnapshot,
    procedure_semantic_id: str,
    evaluation_date: date,
    *,
    historical_version_id: str | None = None,
) -> ProcedureVersionResolution:
    """Resolve one version without ORM access or applicability evaluation."""

    versions = tuple(
        sorted(
            (
                version
                for version in snapshot.procedure_versions
                if version.procedure_semantic_id == procedure_semantic_id
            ),
            key=lambda item: item.semantic_id,
        )
    )
    known = bool(versions) or any(
        candidate.procedure_semantic_id == procedure_semantic_id
        for service in snapshot.services
        for candidate in service.candidates
    )
    if not known:
        return ProcedureVersionUnavailable("unknown_procedure", ())

    diagnostics: set[str] = set()
    malformed_ids: set[str] = set()
    for version in versions:
        version_diagnostics: set[str] = set()
        if version.state not in {"draft", "published", "withdrawn"}:
            version_diagnostics.add("invalid_lifecycle_state")
        if version.rules_contract_version != "v1":
            version_diagnostics.add("unsupported_rules_contract")
        if version.effective_from is not None and type(version.effective_from) is not date:
            version_diagnostics.add("invalid_effective_from")
        if version.effective_to is not None and type(version.effective_to) is not date:
            version_diagnostics.add("invalid_effective_to")
        if (
            type(version.effective_from) is date
            and type(version.effective_to) is date
            and version.effective_from > version.effective_to
        ):
            version_diagnostics.add("invalid_effective_interval")
        if version_diagnostics:
            malformed_ids.add(version.semantic_id)
            diagnostics.update(version_diagnostics)

    upcoming = _upcoming(versions, evaluation_date)
    if diagnostics:
        return ProcedureVersionConfigurationDefect(
            tuple(diagnostics), tuple(malformed_ids), upcoming
        )

    published = tuple(version for version in versions if version.state == "published")
    conflicting: set[str] = set()
    for index, left in enumerate(published):
        for right in published[index + 1 :]:
            if _overlap(left, right):
                conflicting.update((left.semantic_id, right.semantic_id))
    if conflicting:
        return ProcedureVersionConfigurationDefect(
            ("overlapping_published_intervals",), tuple(conflicting), upcoming
        )

    if historical_version_id is not None:
        selected = next(
            (version for version in versions if version.semantic_id == historical_version_id), None
        )
        if selected is None:
            return ProcedureVersionUnavailable("unknown_historical_version", upcoming)
        if selected.state == "draft":
            return ProcedureVersionUnavailable("draft_historical_version", upcoming)
        if selected.effective_from is not None and evaluation_date < selected.effective_from:
            return ProcedureVersionUnavailable("historical_version_not_yet_effective", upcoming)
        historical = selected.state == "withdrawn" or (
            selected.effective_to is not None and evaluation_date > selected.effective_to
        )
        return ProcedureVersionResolved(selected, upcoming, historical)

    applicable = tuple(version for version in published if _contains(version, evaluation_date))
    if len(applicable) == 1:
        return ProcedureVersionResolved(applicable[0], upcoming)
    if not published:
        return ProcedureVersionUnavailable("no_published_version", upcoming)
    if all(
        version.effective_from is not None and version.effective_from > evaluation_date
        for version in published
    ):
        return ProcedureVersionUnavailable("not_yet_effective", upcoming)
    return ProcedureVersionUnavailable("no_applicable_version", upcoming)
