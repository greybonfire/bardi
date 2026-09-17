"""Staff-only, rollback-only advisory checks of stored drafts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import DatabaseError, transaction
from planning import PlanningResult

from knowledge.models import ProcedureVersion
from knowledge.planning_scenarios import (
    PlanningScenario,
    _run_stored_scenarios,
    _scenario_matches,
    planning_behavior_signature,
)
from knowledge.publication import (
    PublicationContext,
    PublicationDiagnostic,
    _load_published_fact_definitions,
    _publication_diagnostics,
)


@dataclass(frozen=True, slots=True)
class PublicationReadiness:
    version: str
    prospective_publisher_id: int
    review_mode: str
    diagnostics: tuple[PublicationDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class ScenarioPreview:
    version: str
    scenario_id: int
    scenario_name: str
    evaluation_date: str
    authored_locale: str
    stale: bool
    matches_expectations: bool | None
    result: PlanningResult | None
    diagnostics: tuple[PublicationDiagnostic, ...]


def _check_publication(version_id: int, *, actor: Any) -> PublicationReadiness:
    """Internal entry for an already-authorized importer; no extra view permission."""
    version = ProcedureVersion.objects.get(pk=version_id)
    identity = version.semantic_id
    publisher_id = actor.pk
    mode = settings.PROCEDURE_VERSION_REVIEW_MODE
    failures = []
    if not actor.has_perm("knowledge.publish_procedureversion"):
        failures.append(PublicationDiagnostic("core.state_actor", "missing_publish_permission"))
    try:
        with transaction.atomic():
            # Never return ORM instances mutated or cached by trusted gates.
            context = PublicationContext(version, actor, _load_published_fact_definitions())
            failures.extend(_publication_diagnostics(context))
            transaction.set_rollback(True)
    except Exception:
        failures.append(PublicationDiagnostic("policy", "gate_execution_failed"))
    return PublicationReadiness(
        identity,
        publisher_id,
        mode,
        tuple(sorted(failures, key=lambda item: (item.gate, item.code, item.detail))),
    )


def _draft(version_id: int) -> ProcedureVersion:
    from knowledge.draft_packs.state import fail

    version = ProcedureVersion.objects.filter(pk=version_id).first()
    if version is None:
        fail("not_found", ("version",), "Procedure Version does not exist.")
    if version.state != ProcedureVersion.State.DRAFT:
        fail("immutable_version", ("version",), "Only a draft may be previewed.")
    return version


def check_draft_publication(version_id: int, *, actor: Any) -> PublicationReadiness:
    from knowledge.draft_packs.service import _database_failure
    from knowledge.draft_packs.state import actor_for, locked_snapshot

    try:
        with locked_snapshot():
            actor = actor_for(actor, "knowledge.view_procedureversion")
            version = _draft(version_id)
            return _check_publication(version.pk, actor=actor)
    except DatabaseError as exc:
        _database_failure(exc)
    raise AssertionError("unreachable")


def preview_draft_scenario(version_id: int, scenario_id: int, *, actor: Any) -> ScenarioPreview:
    from knowledge.draft_packs.service import _database_failure
    from knowledge.draft_packs.state import actor_for, fail, locked_snapshot

    try:
        with locked_snapshot():
            actor = actor_for(actor, "knowledge.view_procedureversion")
            version = _draft(version_id)
            scenario = PlanningScenario.objects.filter(
                pk=scenario_id, procedure_version=version
            ).first()
            if scenario is None:
                fail("not_found", ("scenario",), "Stored scenario does not belong to this draft.")
            stale = scenario.behavior_signature != planning_behavior_signature(version)
            diagnostics: tuple[PublicationDiagnostic, ...] = ()
            result = None
            try:
                with transaction.atomic():
                    scenario.full_clean()
                    transaction.set_rollback(True)
            except Exception:
                # Legacy malformed JSON can fail model validation before ValidationError.
                # Catch outside the savepoint so a database failure cannot poison the caller.
                diagnostics = (
                    PublicationDiagnostic(
                        "core.planning_scenarios", "invalid_scenario", scenario.name
                    ),
                )
            else:
                # The runner uses the date-aware snapshot's Fact registry, not this mapping.
                context = PublicationContext(version, actor, {})
                results, diagnostics = _run_stored_scenarios(context, (scenario,))
                result = results.get(scenario.pk)
            raw_context = scenario.evaluation_context
            return ScenarioPreview(
                version.semantic_id,
                scenario.pk,
                scenario.name,
                str(raw_context.get("evaluation_date", ""))
                if isinstance(raw_context, dict)
                else "",
                str(raw_context.get("locale", "")) if isinstance(raw_context, dict) else "",
                stale,
                _scenario_matches(scenario, result) if result is not None else None,
                result,
                diagnostics,
            )
    except DatabaseError as exc:
        _database_failure(exc)
    raise AssertionError("unreachable")
