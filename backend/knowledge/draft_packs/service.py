"""Atomic desired-snapshot draft authoring; never publication or verification."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from .inspection import DraftPackInspection

from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import Q
from planning.case_preparation import DERIVED_FACT_DEPENDENCIES
from planning.facts import FACT_DEFINITIONS

from knowledge import models as m
from knowledge.aggregate_guard import allow_aggregate_relation_mutation
from knowledge.domain import (
    decode_stored_rule,
    load_fact_definitions,
    referenced_fact_keys,
    to_domain_fact,
)
from knowledge.evidence_workflow import EvidenceDiscrepancy, EvidenceReverificationEvent
from knowledge.planning_scenarios import planning_behavior_signature, required_scenario_kinds
from knowledge.procedure_dependencies import ProcedureDependency, _has_blocking_cycle
from knowledge.review_workflow import ProcedureVersionReviewPolicy
from knowledge.services import (
    set_contradiction_facts,
    set_evidence_link_sources,
    set_question_resolved_facts,
)

from .errors import Diagnostic, DraftPackError
from .exporting import context, setup_for, snapshot
from .mapping import (
    CANDIDATE,
    CATALOG,
    CONTRADICTION,
    DATE_FIELDS,
    EVIDENCE,
    OWNED,
    QUESTION,
    RULE_FIELDS,
    VERSION,
    Mapping,
    authored,
)
from .schema import DraftPack, parse_draft_pack
from .state import (
    actor_for,
    digest,
    evidence_for,
    fail,
    json_equal,
    locked_snapshot,
    require_add,
    revision,
)
from .state import (
    inspection_precondition as live_precondition,
)


def _normalized(data: dict[str, Any]) -> dict[str, Any]:
    for key, spec in CATALOG.items():
        data["catalog"][key].sort(key=lambda row: row[spec.identity])
    for key, spec in OWNED.items():
        data[key].sort(key=lambda row: row[spec.identity])
    data["evidence_links"].sort(key=_evidence_key)
    if data["service_setup"] is not None:
        for key, identity in (
            ("questions", "semantic_id"),
            ("candidates", "procedure"),
            ("contradictions", "semantic_id"),
        ):
            data["service_setup"][key].sort(key=lambda row: row[identity])
    return data


def _evidence_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["owner"]["kind"], row["owner"]["semantic_id"], row["semantic_id"]


def _validation(exc: ValidationError, path: tuple[str | int, ...]) -> DraftPackError:
    if hasattr(exc, "message_dict"):
        return DraftPackError(
            Diagnostic("invalid_model", (*path, field), message)
            for field, messages in exc.message_dict.items()
            for message in messages
        )
    return DraftPackError(Diagnostic("invalid_model", path, message) for message in exc.messages)


def _save(row: Any, path: tuple[str | int, ...]) -> None:
    try:
        # Scenario.save supplies its own seal before full_clean.
        if row.__class__ is not OWNED["scenarios"].model:
            row.full_clean()
        row.save()
    except ValidationError as exc:
        raise _validation(exc, path) from None


def _resolve(model: Any, value: str, path: tuple[str | int, ...], version: Any = None) -> Any:
    lookup = {"key" if model is m.FactDefinition else "semantic_id": value}
    if model is m.EligibilityBasis:
        lookup["procedure_version"] = version
    row = model.objects.filter(**lookup).first()
    if row is None:
        fail("unresolved_reference", path, "Referenced catalog or owned identity does not exist.")
    return row


def _values(
    data: dict[str, Any], spec: Mapping, path: tuple[str | int, ...], version: Any = None
) -> dict[str, Any]:
    result = {}
    for name in spec.fields:
        value = data[name]
        if name in RULE_FIELDS and value != {}:
            decoded = decode_stored_rule(value)
            if decoded.diagnostics:
                raise DraftPackError(
                    Diagnostic(item.code, (*path, name, *item.path), "Invalid stored rule.")
                    for item in decoded.diagnostics
                )
        if name in spec.references and value is not None:
            value = _resolve(spec.references[name], value, (*path, name), version)
        elif name in DATE_FIELDS and value is not None:
            value = date.fromisoformat(value)
        result[name] = value
    return result


def _catalog(data: dict[str, Any], actor: Any, changes: list[dict[str, Any]]) -> set[str]:
    new_services = set()
    for key, spec in CATALOG.items():
        for index, incoming in enumerate(data[key]):
            path = ("catalog", key, index)
            row = spec.model.objects.filter(**{spec.identity: incoming[spec.identity]}).first()
            if spec.model is m.FactDefinition:
                pinned = FACT_DEFINITIONS.get(incoming["key"])
                if pinned is not None and to_domain_fact(m.FactDefinition(**incoming)) != pinned:
                    fail("shared_conflict", path, "Fact definition conflicts with pinned meaning.")
            if row is not None:
                if spec.model is m.FactDefinition and row.derived:
                    fail(
                        "shared_conflict",
                        path,
                        "Derived Facts can be referenced, not defined in a pack.",
                    )
                for name, value in authored(row, spec).items():
                    if not json_equal(value, incoming[name]):
                        fail(
                            "shared_conflict",
                            (*path, name),
                            "Shared catalog definitions are compare-only; use a new identity.",
                        )
                changes.append({"kind": "shared_reuse", "path": list(path)})
                continue
            require_add(actor, spec.model, path)
            values = _values(incoming, spec, path)
            row = spec.model(**values)
            _save(row, path)
            if spec.model is m.Service:
                new_services.add(row.semantic_id)
            changes.append({"kind": "shared_create", "path": list(path)})
    return new_services


def _setup(
    data: Any, new_services: set[str], version: Any, actor: Any, changes: list[dict[str, Any]]
) -> None:
    if data is None:
        return
    service = version.procedure.primary_service
    if data["service"] != service.semantic_id:
        fail(
            "identity_mismatch",
            ("service_setup", "service"),
            "Setup must name the version's primary Service.",
        )
    if service.semantic_id not in new_services:
        if not json_equal(data, setup_for(service)):
            fail(
                "protected_service_setup",
                ("service_setup",),
                "Existing Service setup cannot be changed, even when inactive.",
            )
        return
    for key, spec in (
        ("questions", QUESTION),
        ("candidates", CANDIDATE),
        ("contradictions", CONTRADICTION),
    ):
        for index, incoming in enumerate(data[key]):
            path = ("service_setup", key, index)
            require_add(actor, spec.model, path)
            row = spec.model(service=service, **_values(incoming, spec, path))
            _save(row, path)
            try:
                if key == "questions":
                    set_question_resolved_facts(
                        row,
                        [
                            _resolve(m.FactDefinition, value, (*path, "resolves_facts", i))
                            for i, value in enumerate(incoming["resolves_facts"])
                        ],
                    )
                elif key == "contradictions":
                    set_contradiction_facts(
                        row,
                        [
                            _resolve(m.FactDefinition, value, (*path, "facts", i))
                            for i, value in enumerate(incoming["facts"])
                        ],
                    )
            except ValidationError as exc:
                raise _validation(exc, path) from None
            changes.append({"kind": "setup_create", "path": list(path)})


def _trust(row: Any) -> bool:
    state = (
        "needs_reverification" if getattr(row, "value_state", None) == "unverified" else "unknown"
    )
    changed = (
        row.verification_state != state
        or row.verified_on is not None
        or row.reverify_on is not None
    )
    row.verification_state, row.verified_on, row.reverify_on = state, None, None
    return changed


def _protect_history(owners: set[tuple[str, str]], version: Any) -> None:
    for kind, identity in sorted(owners):
        links = m.EvidenceLink.objects.filter(
            **{f"{kind}__procedure_version": version, f"{kind}__semantic_id": identity}
        )
        if (
            EvidenceDiscrepancy.objects.filter(
                Q(anchor_evidence_link__in=links) | Q(evidence_rows__evidence_link__in=links)
            ).exists()
            or EvidenceReverificationEvent.objects.filter(
                Q(anchor_evidence_link__in=links) | Q(evidence_rows__evidence_link__in=links)
            ).exists()
        ):
            fail(
                "protected_history",
                ("owners", kind, identity),
                "Affected claims have discrepancy or re-verification history; "
                "use a fresh successor or manual workflow.",
            )


def _reconcile(
    data: dict[str, Any],
    version: Any,
    *,
    dry_run: bool,
    allow_deletions: bool,
    changes: list[dict[str, Any]],
) -> None:
    existing = {
        key: {
            getattr(row, spec.identity): row
            for row in spec.model.objects.filter(procedure_version=version)
        }
        for key, spec in OWNED.items()
    }
    desired = {key: {row[spec.identity]: row for row in data[key]} for key, spec in OWNED.items()}
    affected: set[tuple[str, str]] = set()
    obsolete: list[tuple[str, Any]] = []
    version_fields = [
        name
        for name, value in authored(version, VERSION).items()
        if not json_equal(value, data["version"][name])
    ]
    version_changed = bool(version_fields)
    for key, spec in OWNED.items():
        for identity, row in existing[key].items():
            if identity not in desired[key]:
                obsolete.append((key, row))
                changes.append({"kind": "delete", "path": [key, identity]})
                if spec.owner_kind:
                    affected.add((spec.owner_kind, identity))
        for identity, incoming in desired[key].items():
            old = existing[key].get(identity)
            if old is None or not json_equal(authored(old, spec), incoming):
                changes.append(
                    {
                        "kind": "add" if old is None else "change",
                        "path": [key, identity],
                        "fields": list(incoming)
                        if old is None
                        else [
                            name
                            for name, value in authored(old, spec).items()
                            if not json_equal(incoming[name], value)
                        ],
                    }
                )
                if spec.owner_kind:
                    affected.add((spec.owner_kind, identity))
            if version_changed and spec.owner_kind:
                affected.add((spec.owner_kind, identity))
    old_links = {}
    for row in evidence_for(version):
        kind = next(
            spec.owner_kind
            for spec in OWNED.values()
            if spec.owner_kind and getattr(row, f"{spec.owner_kind}_id")
        )
        old_links[(kind, row.owner.semantic_id, row.semantic_id)] = row
    desired_links = {_evidence_key(row): row for row in data["evidence_links"]}
    removed_links = set(old_links) - set(desired_links)
    for identity in sorted(set(old_links) | set(desired_links)):
        old, incoming = old_links.get(identity), desired_links.get(identity)
        old_data = (
            None
            if old is None
            else {
                **authored(old, EVIDENCE),
                "owner": {"kind": identity[0], "semantic_id": identity[1]},
                "sources": list(
                    old.source_links.order_by("position").values_list(
                        "source__semantic_id", flat=True
                    )
                ),
            }
        )
        if not json_equal(old_data, incoming):
            affected.add(identity[:2])
            changes.append(
                {
                    "kind": "delete" if incoming is None else "add" if old is None else "change",
                    "path": ["evidence_links", *identity],
                    "fields": sorted(
                        name
                        for name in (incoming or old_data or {})
                        if not json_equal((incoming or {}).get(name), (old_data or {}).get(name))
                    ),
                }
            )
    # A basis claim/rule/evidence change invalidates dependent scoped claims too.
    bases = {identity for kind, identity in affected if kind == "eligibility_basis"}
    for key in ("checklist_items", "steps", "fees"):
        spec = OWNED[key]
        for identity in sorted(set(existing[key]) | set(desired[key])):
            old = existing[key].get(identity)
            old_data = authored(old, spec) if old is not None else {}
            incoming = desired[key].get(identity, {})
            if any(
                row.get("scope") == "eligibility_basis"
                and row.get("scope_reference", row.get("eligibility_basis")) in bases
                for row in (old_data, incoming)
            ):
                affected.add((spec.owner_kind, identity))
    _protect_history(affected, version)
    if (obsolete or removed_links) and not (allow_deletions or dry_run):
        fail(
            "deletions_require_confirmation",
            (),
            "Snapshot deletes owned rows; use allow_deletions after reviewing a dry run.",
        )
    # Reset retained current rows first, including siblings, before changed positions/claims.
    for key, spec in OWNED.items():
        if not spec.owner_kind:
            continue
        for identity, row in existing[key].items():
            if (spec.owner_kind, identity) in affected:
                if _trust(row):
                    _save(row, (key, identity))
                    changes.append({"kind": "trust_reset", "path": [key, identity]})
                for link in row.evidence_links.all():
                    if _trust(link):
                        _save(link, ("evidence_links", link.semantic_id))
                        changes.append(
                            {"kind": "trust_reset", "path": ["evidence_links", link.semantic_id]}
                        )
    with allow_aggregate_relation_mutation():
        for identity in sorted(removed_links):
            old_links[identity].delete()
        # Bases go last because scoped children use PROTECT. Surviving rows are
        # reparented below before an obsolete basis is removed.
        for key, row in obsolete:
            if key != "bases":
                row.delete()
    if version_changed:
        for name, value in _values(data["version"], VERSION, ("version",)).items():
            setattr(version, name, value)
        _save(version, ("version",))
        changes.append({"kind": "change", "path": ["version"], "fields": version_fields})
    for key, spec in OWNED.items():
        if key == "scenarios":
            continue
        for index, incoming in enumerate(data[key]):
            identity = incoming[spec.identity]
            row = existing[key].get(identity)
            if row is not None and json_equal(authored(row, spec), incoming):
                continue
            values = _values(incoming, spec, (key, index), version)
            if row is None:
                row = spec.model(procedure_version=version, **values)
            else:
                for name, value in values.items():
                    setattr(row, name, value)
            _trust(row)
            _save(row, (key, index))
    with allow_aggregate_relation_mutation():
        for key, row in obsolete:
            if key == "bases":
                row.delete()
    owner_specs = {spec.owner_kind: spec for spec in OWNED.values() if spec.owner_kind}
    for index, incoming in enumerate(data["evidence_links"]):
        identity = _evidence_key(incoming)
        kind, owner_id, _ = identity
        path = ("evidence_links", index)
        owner = (
            owner_specs[kind]
            .model.objects.filter(procedure_version=version, semantic_id=owner_id)
            .first()
        )
        if owner is None:
            fail(
                "unresolved_reference",
                (*path, "owner", "semantic_id"),
                "Evidence owner is not in the desired snapshot.",
            )
        link = old_links.get(identity)
        sources = [
            _resolve(m.Source, value, (*path, "sources", i))
            for i, value in enumerate(incoming["sources"])
        ]
        if link is None:
            link = m.EvidenceLink(**{kind: owner}, **_values(incoming, EVIDENCE, path))
            _save(link, path)
        elif not json_equal(
            authored(link, EVIDENCE), {name: incoming[name] for name in EVIDENCE.fields}
        ):
            for name, value in _values(incoming, EVIDENCE, path).items():
                setattr(link, name, value)
            _trust(link)
            _save(link, path)
        if list(link.source_links.order_by("position").values_list("source_id", flat=True)) != [
            source.pk for source in sources
        ]:
            try:
                set_evidence_link_sources(link, sources)
            except ValidationError as exc:
                raise _validation(exc, path) from None
    # Do not reseal unchanged scenarios after changing their planning inputs.
    for index, incoming in enumerate(data["scenarios"]):
        spec = OWNED["scenarios"]
        row = existing["scenarios"].get(incoming["name"])
        if row is not None and json_equal(authored(row, spec), incoming):
            continue
        values = _values(incoming, spec, ("scenarios", index))
        if row is None:
            row = spec.model(procedure_version=version, **values)
        else:
            for name, value in values.items():
                setattr(row, name, value)
        _save(row, ("scenarios", index))
    basis_ids = set(version.eligibility_bases.values_list("semantic_id", flat=True))
    for index, row in enumerate(data["checklist_items"]):
        if row["scope"] == "eligibility_basis" and row["scope_reference"] not in basis_ids:
            fail(
                "unresolved_reference",
                ("checklist_items", index, "scope_reference"),
                "Basis scope must reference the desired snapshot.",
            )
    if _has_blocking_cycle(ProcedureDependency.objects.select_related("procedure_version").all()):
        fail(
            "dependency_cycle",
            ("dependencies",),
            "Blocking Procedure dependencies must not form a cycle.",
        )


def _validate_snapshot(data: dict[str, Any], version: Any) -> None:
    """Validate even unchanged rows without saving or refreshing scenario seals."""
    _values(data["version"], VERSION, ("version",))
    try:
        version.full_clean()
    except ValidationError as exc:
        raise _validation(exc, ("version",)) from None
    for key, spec in OWNED.items():
        for index, incoming in enumerate(data[key]):
            _values(incoming, spec, (key, index), version)
            row = spec.model.objects.get(
                procedure_version=version, **{spec.identity: incoming[spec.identity]}
            )
            try:
                row.full_clean()
            except ValidationError as exc:
                raise _validation(exc, (key, index)) from None
    evidence_paths = {_evidence_key(row): index for index, row in enumerate(data["evidence_links"])}
    for link in evidence_for(version):
        kind = next(
            spec.owner_kind
            for spec in OWNED.values()
            if spec.owner_kind and getattr(link, f"{spec.owner_kind}_id")
        )
        index = evidence_paths[(kind, link.owner.semantic_id, link.semantic_id)]
        try:
            link.full_clean()
        except ValidationError as exc:
            raise _validation(exc, ("evidence_links", index)) from None


def _risks(data: dict[str, bool], version: Any, actor: Any, changes: list[dict[str, Any]]) -> None:
    policy = ProcedureVersionReviewPolicy.objects.filter(procedure_version=version).first()
    new = policy is None
    if new:
        policy = ProcedureVersionReviewPolicy(procedure_version=version, author=actor)
    changed = new
    for name, value in data.items():
        field = f"{name}_risk"
        if getattr(policy, field) and not value:
            fail("risk_reduction", ("risks", name), "Imports cannot clear an existing risk flag.")
        if getattr(policy, field) != value:
            changed = True
            setattr(policy, field, value)
            changes.append({"kind": "risk_increase", "path": ["risks", name]})
    if changed:
        _save(policy, ("risks",))
        if new:
            changes.append({"kind": "add", "path": ["review_policy"]})


def _manual(version: Any) -> list[dict[str, Any]]:
    actions = []
    for key, spec in OWNED.items():
        if not spec.owner_kind:
            continue
        for row in spec.model.objects.filter(procedure_version=version):
            if key == "warnings" and row.kind == "product":
                continue
            links = list(row.evidence_links.all())
            incomplete = not links or any(
                not link.passage.strip()
                or not link.location.strip()
                or not link.applicability_context.strip()
                or not link.source_links.exists()
                or link.verification_state != "current"
                for link in links
            )
            if row.verification_state != "current" or incomplete:
                actions.append({"code": "evidence_review_required", "path": [key, row.semantic_id]})
    if not version.procedure.primary_service.questions.exists():
        actions.append({"code": "question_setup_required", "path": ["service_setup", "questions"]})
    definitions = load_fact_definitions()
    rules = [version.applicability]
    for key in ("bases", "checklist_items", "steps", "fees"):
        spec = OWNED[key]
        for row in spec.model.objects.filter(procedure_version=version):
            rules.extend(getattr(row, field) for field in spec.fields if field in RULE_FIELDS)
    rules.extend(
        version.procedure.primary_service.procedure_candidates.values_list(
            "selection_predicate", flat=True
        )
    )
    needed: set[str] = set()
    for raw in rules:
        if raw == {}:
            continue
        decoded = decode_stored_rule(raw, definitions)
        if decoded.predicate is not None:
            for key in referenced_fact_keys(decoded.predicate):
                needed.update(DERIVED_FACT_DEPENDENCIES.get(key, (key,)))
    covered = {
        key
        for question in version.procedure.primary_service.questions.all()
        for key in question.resolved_fact_keys
    }
    for key in sorted(needed - covered):
        actions.append({"code": "question_coverage_required", "path": ["facts", key]})
    for key in sorted(needed):
        if not m.FactDefinition.objects.filter(key=key, is_published=True).exists():
            actions.append({"code": "fact_publication_required", "path": ["facts", key]})
    signature = planning_behavior_signature(version)
    scenarios = list(version.planning_scenarios.all())
    for kind in sorted(
        required_scenario_kinds(version, definitions) - {row.kind for row in scenarios}
    ):
        actions.append({"code": "scenario_coverage_required", "path": ["scenarios", kind]})
    if not scenarios:
        actions.append({"code": "scenario_authoring_required", "path": ["scenarios"]})
    for row in scenarios:
        if row.behavior_signature != signature:
            actions.append({"code": "scenario_stale", "path": ["scenarios", row.name]})
    actions.append({"code": "manual_publication_review_required", "path": []})
    return actions


def _database_failure(exc: DatabaseError) -> None:
    code = getattr(exc.__cause__, "sqlstate", None)
    if code in {"55P03", "40P01", "40001", "23505"}:
        fail("concurrent_edit", (), "Concurrent editing detected; reload and retry.")
    if isinstance(exc, IntegrityError):
        fail("invalid_model", (), "Database structural constraints rejected the snapshot.")
    fail("database_error", (), "The database could not complete the authoring operation.")


def import_draft_pack(
    pack: DraftPack | bytes | str | dict[str, Any],
    *,
    actor: Any,
    target_version: str | None = None,
    dry_run: bool = False,
    allow_deletions: bool = False,
    inspection_precondition: str | None = None,
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        _apply_draft_pack(
            pack,
            actor=actor,
            target_version=target_version,
            dry_run=dry_run,
            allow_deletions=allow_deletions,
            inspection_precondition=inspection_precondition,
        ),
    )


def _apply_draft_pack(
    pack: DraftPack | bytes | str | dict[str, Any],
    *,
    actor: Any,
    target_version: str | None = None,
    dry_run: bool = False,
    allow_deletions: bool = False,
    inspection_precondition: str | None = None,
    inspect: bool = False,
) -> dict[str, Any] | DraftPackInspection:
    from .inspection import _capture, _inspection

    # Reparse model instances too: model_construct or subsequent mutation is not trusted.
    data = _normalized(
        parse_draft_pack(
            pack.model_dump(mode="json") if isinstance(pack, DraftPack) else pack
        ).model_dump(mode="json")
    )
    request_digest = digest({"pack": data, "target_version": target_version})
    try:
        with locked_snapshot():
            actor = actor_for(actor, "knowledge.change_procedureversion")
            if target_version is None:
                require_add(actor, m.ProcedureVersion, ("version",))
            identity = (
                target_version if target_version is not None else data["version"]["semantic_id"]
            )
            version = (
                m.ProcedureVersion.objects.select_for_update(nowait=True)
                .filter(semantic_id=identity)
                .first()
            )
            precondition = (
                live_precondition() if inspect or inspection_precondition is not None else ""
            )
            if target_version is not None and version is None:
                fail("not_found", ("target_version",), "Target Procedure Version does not exist.")
            if version is not None:
                if version.state != m.ProcedureVersion.State.DRAFT:
                    fail("immutable_version", ("target_version",), "Only a draft may be imported.")
                m.Procedure.objects.select_for_update(nowait=True).get(pk=version.procedure_id)
                if (
                    version.semantic_id != data["version"]["semantic_id"]
                    or version.procedure.semantic_id != data["version"]["procedure"]
                ):
                    fail(
                        "identity_mismatch",
                        ("version",),
                        "Target identity and Procedure cannot be renamed or reassigned.",
                    )
                current = revision(version)
                receipt = m.DraftPackImportReceipt.objects.filter(version=version).first()
                retry = (
                    receipt is not None
                    and receipt.request_digest == request_digest
                    and receipt.post_revision == current
                )
                if retry:
                    result = {
                        "status": "dry_run" if dry_run else "noop",
                        "version": version.semantic_id,
                        "revision": current,
                        "changes": [],
                        "manual_actions": _manual(version),
                    }
                    if inspect:
                        checked = _inspection(
                            result,
                            precondition,
                            _capture(data, version),
                            data,
                            version,
                            actor,
                        )
                        transaction.set_rollback(True)
                        return checked
                    return result
                if inspection_precondition is not None and inspection_precondition != precondition:
                    fail(
                        "stale_inspection",
                        (),
                        "Live knowledge or publication policy changed; inspect again.",
                    )
                if target_version is None:
                    fail(
                        "identity_collision",
                        ("version", "semantic_id"),
                        "Existing identity is not a proven unchanged retry; "
                        "select an explicit target.",
                    )
                if data["base_revision"] != current:
                    fail(
                        "stale_revision",
                        ("base_revision",),
                        "The complete live revision changed; export again before editing.",
                    )
            elif data["base_revision"] is not None:
                fail(
                    "invalid_base_revision",
                    ("base_revision",),
                    "A new draft must have a null base revision.",
                )
            if inspection_precondition is not None and inspection_precondition != precondition:
                fail(
                    "stale_inspection",
                    (),
                    "Live knowledge or publication policy changed; inspect again.",
                )
            before = _capture(data, version) if inspect else {}
            changes: list[dict[str, Any]] = []
            new_services = _catalog(data["catalog"], actor, changes)
            if version is None:
                version = m.ProcedureVersion(**_values(data["version"], VERSION, ("version",)))
                _save(version, ("version",))
                changes.append({"kind": "add", "path": ["version"]})
            _setup(data["service_setup"], new_services, version, actor, changes)
            _risks(data["risks"], version, actor, changes)
            _reconcile(
                data, version, dry_run=dry_run, allow_deletions=allow_deletions, changes=changes
            )
            _validate_snapshot(data, version)
            post_revision = revision(version)
            changed = any(change["kind"] != "shared_reuse" for change in changes)
            # The receipt is internal and excluded from the complete live revision.
            receipt = m.DraftPackImportReceipt.objects.filter(version=version).first()
            if receipt is None:
                m.DraftPackImportReceipt.objects.create(
                    version=version, request_digest=request_digest, post_revision=post_revision
                )
            elif receipt.request_digest != request_digest or receipt.post_revision != post_revision:
                receipt.request_digest, receipt.post_revision = request_digest, post_revision
                receipt.save(update_fields=("request_digest", "post_revision"))
            manual_actions = _manual(version)
            changes.extend(
                {"kind": "scenario_stale", "path": action["path"]}
                for action in manual_actions
                if action["code"] == "scenario_stale"
            )
            result = {
                "status": "dry_run" if dry_run else "written" if changed else "noop",
                "version": version.semantic_id,
                "revision": post_revision,
                "changes": changes,
                "manual_actions": manual_actions,
            }
            if inspect:
                checked = _inspection(result, precondition, before, data, version, actor)
                transaction.set_rollback(True)
                return checked
            if dry_run:
                transaction.set_rollback(True)
            return result
    except ValidationError as exc:
        raise _validation(exc, ()) from None
    except DatabaseError as exc:
        _database_failure(exc)
    raise AssertionError("unreachable")


def export_draft_pack(version_semantic_id: str, *, actor: Any) -> dict[str, Any]:
    try:
        with locked_snapshot():
            actor_for(actor, "knowledge.view_procedureversion")
            version = m.ProcedureVersion.objects.filter(semantic_id=version_semantic_id).first()
            if version is None:
                fail("not_found", ("version",), "Procedure Version does not exist.")
            return snapshot(version)
    except DatabaseError as exc:
        _database_failure(exc)
    raise AssertionError("unreachable")


def export_draft_context(service_semantic_id: str | None = None, *, actor: Any) -> dict[str, Any]:
    try:
        with locked_snapshot():
            actor_for(actor, "knowledge.view_procedureversion")
            return context(service_semantic_id)
    except DatabaseError as exc:
        _database_failure(exc)
    raise AssertionError("unreachable")
