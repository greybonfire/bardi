"""Detached inspection of the real importer, not a second reconciliation algorithm."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from knowledge import models as m
from knowledge.draft_preview import PublicationReadiness, _check_publication
from knowledge.planning_scenarios import planning_behavior_signature
from knowledge.review_workflow import ProcedureVersionReviewPolicy

from .exporting import setup_for
from .mapping import CATALOG, EVIDENCE, OWNED, VERSION, authored
from .state import evidence_for, json_equal

Path = tuple[str | int, ...]
Rows = dict[Path, dict[str, Any]]
TRUST_FIELDS = ("verification_state", "verified_on", "reverify_on")


@dataclass(frozen=True, slots=True)
class InspectionChange:
    kind: str
    path: Path
    fields: tuple[str, ...]
    before: dict[str, Any] | None
    after: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class DraftPackInspection:
    import_result: dict[str, Any]
    precondition: str
    diff: tuple[InspectionChange, ...]
    requires_deletions: bool
    publication: PublicationReadiness


def _trust_values(row: Any) -> dict[str, Any]:
    return {
        name: value.isoformat() if hasattr(value, "isoformat") else value
        for name in TRUST_FIELDS
        if hasattr(row, name)
        for value in (getattr(row, name),)
    }


def _capture(data: dict[str, Any], version: Any) -> Rows:
    """Only uploaded shared identities and applicable owned/setup rows, without export limits."""
    rows: Rows = {}
    for key, spec in CATALOG.items():
        for incoming in data["catalog"][key]:
            identity = incoming[spec.identity]
            row = spec.model.objects.filter(**{spec.identity: identity}).first()
            if row is not None:
                values = authored(row, spec)
                for field in ("is_active", "is_published"):
                    if hasattr(row, field):
                        values[field] = getattr(row, field)
                rows[("catalog", key, identity)] = values
    # Setup may already exist even when importing a new version of an existing Procedure.
    procedure = m.Procedure.objects.filter(semantic_id=data["version"]["procedure"]).first()
    if procedure is not None:
        setup = setup_for(procedure.primary_service)
        for key, identity in (
            ("questions", "semantic_id"),
            ("candidates", "procedure"),
            ("contradictions", "semantic_id"),
        ):
            for row in setup[key]:
                rows[("service_setup", key, row[identity])] = row
    if version is None:
        return rows
    rows[("version",)] = authored(version, VERSION)
    signature = planning_behavior_signature(version)
    for key, spec in OWNED.items():
        for row in spec.model.objects.filter(procedure_version=version):
            values = {**authored(row, spec), **_trust_values(row)}
            if key == "scenarios":
                values["stale"] = row.behavior_signature != signature
            rows[(key, getattr(row, spec.identity))] = values
    for link in evidence_for(version):
        kind = next(
            spec.owner_kind
            for spec in OWNED.values()
            if spec.owner_kind and getattr(link, f"{spec.owner_kind}_id")
        )
        owner = {"kind": kind, "semantic_id": link.owner.semantic_id}
        rows[("evidence_links", kind, link.owner.semantic_id, link.semantic_id)] = {
            **authored(link, EVIDENCE),
            **_trust_values(link),
            "owner": owner,
            "sources": list(
                link.source_links.order_by("position").values_list("source__semantic_id", flat=True)
            ),
        }
    policy = ProcedureVersionReviewPolicy.objects.filter(procedure_version=version).first()
    if policy is not None:
        rows[("review_policy",)] = {"author_id": policy.author_id}
        for risk in data["risks"]:
            rows[("risks", risk)] = {risk: getattr(policy, f"{risk}_risk")}
    return rows


def _diff(before: Rows, after: Rows) -> tuple[InspectionChange, ...]:
    changes = []
    for path in sorted(before.keys() | after.keys()):
        old, new = before.get(path), after.get(path)
        if json_equal(old, new):
            continue
        fields = tuple(
            sorted(
                name
                for name in (old or {}).keys() | (new or {}).keys()
                if old is None or new is None or not json_equal(old.get(name), new.get(name))
            )
        )
        kind = "delete" if new is None else "add" if old is None else "change"
        if old is None and path[0] == "catalog":
            kind = "shared_create"
        elif old is None and path[0] == "service_setup":
            kind = "setup_create"
        elif path[0] == "risks" and any((new or {}).values()):
            kind = "risk_increase"
        changes.append(InspectionChange(kind, path, fields, old, new))
        if old is not None and new is not None:
            reset = tuple(name for name in TRUST_FIELDS if name in fields)
            if reset:
                changes.append(InspectionChange("trust_reset", path, reset, old, new))
            if path[0] == "scenarios" and new.get("stale") and not old.get("stale"):
                changes.append(InspectionChange("scenario_stale", path, ("stale",), old, new))
    return tuple(changes)


def _inspection(
    result: dict[str, Any],
    precondition: str,
    before: Rows,
    data: dict[str, Any],
    version: Any,
    actor: Any,
) -> DraftPackInspection:
    diff = _diff(before, _capture(data, version))
    return DraftPackInspection(
        result,
        precondition,
        diff,
        any(change.kind == "delete" for change in diff),
        _check_publication(version.pk, actor=actor),
    )


def inspect_draft_pack(
    pack: Any, *, actor: Any, target_version: str | None = None
) -> DraftPackInspection:
    from .service import _apply_draft_pack

    return cast(
        DraftPackInspection,
        _apply_draft_pack(
            pack,
            actor=actor,
            target_version=target_version,
            dry_run=True,
            inspect=True,
        ),
    )
