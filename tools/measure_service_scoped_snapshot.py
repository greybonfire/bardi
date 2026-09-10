"""Disposable PostgreSQL measurement for issue #119.

The probe creates its own namespaced published and draft graph in the supplied disposable
PostgreSQL database, compares both loaders on identical snapshots, and removes every row it
created after each scale.  It is intentionally not a benchmark and makes no query-count-only
performance claim.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

_PREFIX = "issue119.measurement."


@dataclass
class _Dataset:
    actor_id: int
    requested_service_id: str
    authority_ids: list[int] = field(default_factory=list)
    source_ids: list[int] = field(default_factory=list)
    service_ids: list[int] = field(default_factory=list)
    procedure_ids: list[int] = field(default_factory=list)
    version_ids: list[int] = field(default_factory=list)
    checklist_ids: list[int] = field(default_factory=list)
    evidence_ids: list[int] = field(default_factory=list)
    event_ids: list[int] = field(default_factory=list)
    discrepancy_ids: list[int] = field(default_factory=list)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluation-date", default="2026-12-31")
    parser.add_argument("--scales", default="0,100,500")
    parser.add_argument("--settings", default="bardi.settings.test")
    parser.add_argument(
        "--facts",
        default='{"application_location":"inside_egypt"}',
        help="JSON object used for the differential response",
    )
    parser.add_argument("--locale", choices=("ar", "en"), default="en")
    return parser.parse_args()


def _snapshot_rows(snapshot: Any) -> int:
    """Count eagerly detached domain records, including nested feature records."""

    total = (
        len(snapshot.fact_definitions) + len(snapshot.services) + len(snapshot.procedure_versions)
    )
    total += len(snapshot.service_points) + len(snapshot.service_point_versions)
    for service in snapshot.services:
        total += len(service.candidates) + len(service.questions) + len(service.contradictions)
    for version in snapshot.procedure_versions:
        total += sum(
            len(getattr(version, attribute))
            for attribute in (
                "checklist_items",
                "eligibility_bases",
                "steps",
                "fees",
                "warnings",
                "dependencies",
                "service_point_associations",
            )
        )
        for item in (
            *version.checklist_items,
            *version.steps,
            *version.fees,
            *version.warnings,
            *version.eligibility_bases,
            *version.dependencies,
            *version.service_point_associations,
        ):
            total += len(item.evidence_links)
            total += sum(len(link.sources) for link in item.evidence_links)
    for material in snapshot.service_point_versions:
        total += len(material.evidence_links)
        total += sum(len(link.sources) for link in material.evidence_links)
    return total


def _workflow_rows(evaluation_date: date, scope: Any, *, scoped: bool) -> int:
    from knowledge.evidence_workflow import EvidenceReverificationEvent
    from knowledge.evidence_workflow_temporal import EvidenceDiscrepancyTransition

    transitions = EvidenceDiscrepancyTransition.objects.filter(
        occurred_at__date__lte=evaluation_date
    )
    reverifications = EvidenceReverificationEvent.objects.filter(
        meaning_changed=False,
        occurred_at__date__lte=evaluation_date,
    )
    if scoped:
        transitions = transitions.filter(
            discrepancy__anchor_evidence_link_id__in=scope.evidence_link_ids
        )
        reverifications = reverifications.filter(
            anchor_evidence_link_id__in=scope.evidence_link_ids
        )
    return int(transitions.count()) + int(reverifications.count())


def _measure(loader: Any, *, connection: Any) -> tuple[dict[str, float | int], Any]:
    from django.test.utils import CaptureQueriesContext

    connection.force_debug_cursor = True
    connection.queries_log.clear()
    started = time.perf_counter()
    with CaptureQueriesContext(connection) as queries:
        snapshot = loader()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return (
        {
            "sql_queries": len(queries),
            "detached_rows": _snapshot_rows(snapshot),
            "elapsed_ms": round(elapsed_ms, 3),
        },
        snapshot,
    )


def _responses_match(
    service_id: str,
    facts: dict[str, Any],
    locale: Literal["ar", "en"],
    evaluation_date: date,
    full_snapshot: Any,
    scoped_snapshot: Any,
) -> bool:
    from api.application import execute_planning
    from planning.public import PlanningInput

    planning_input = PlanningInput(service_id, facts, locale, evaluation_date)
    return bool(
        execute_planning(planning_input, snapshot_loader=lambda: full_snapshot)
        == execute_planning(planning_input, snapshot_loader=lambda: scoped_snapshot)
    )


def _create_graph(
    dataset: _Dataset,
    *,
    suffix: str,
    state: str,
    actor_id: int,
    source_id: int,
) -> int:
    """Create one small valid graph; published rows are probe-only immutable snapshots."""

    from django.contrib.auth import get_user_model
    from knowledge.models import (
        ChecklistItem,
        EvidenceLink,
        FactDefinition,
        Procedure,
        ProcedureVersion,
        Service,
        ServiceProcedureCandidate,
        ServiceQuestion,
    )

    service_id = f"{_PREFIX}{suffix}.service"
    procedure_id = f"{_PREFIX}{suffix}.procedure"
    version_id = f"{_PREFIX}{suffix}.version"
    service = Service.objects.create(
        semantic_id=service_id,
        text_ar="خدمة القياس",
        text_en="Measurement service",
        is_active=True,
    )
    procedure = Procedure.objects.create(
        semantic_id=procedure_id,
        text_ar="إجراء القياس",
        text_en="Measurement procedure",
        primary_service=service,
    )
    ServiceQuestion.objects.create(
        semantic_id=f"{_PREFIX}{suffix}.question",
        service=service,
        fact=FactDefinition.objects.get(key="application_location"),
        text_ar="أين؟",
        text_en="Where?",
        priority=1,
    )
    predicate = {"op": "eq", "fact": "application_location", "value": "inside_egypt"}
    ServiceProcedureCandidate.objects.create(
        service=service,
        procedure=procedure,
        selection_predicate=predicate,
    )
    version = ProcedureVersion(
        semantic_id=version_id,
        procedure=procedure,
        state=ProcedureVersion.State.DRAFT,
        text_ar="إجراء القياس",
        text_en="Measurement procedure",
        applicability=predicate,
    )
    ProcedureVersion.objects.bulk_create([version])
    version.refresh_from_db()
    item = ChecklistItem(
        procedure_version=version,
        semantic_id="measurement.requirement",
        text_ar="مستند القياس",
        text_en="Measurement document",
        classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
        quantity=1,
        display_order=1,
        verification_state="current",
        verified_on=date(2026, 8, 1),
    )
    ChecklistItem.objects.bulk_create([item])
    item.refresh_from_db()
    link = EvidenceLink(
        checklist_item=item,
        semantic_id="measurement.evidence",
        passage="Deterministic measurement passage",
        location="Measurement section 1",
        applicability_context="The disposable measurement graph",
        support_status=EvidenceLink.SupportStatus.SUPPORTS,
        verification_state="current",
        verified_on=date(2026, 8, 1),
        retrieved_on=date(2026, 8, 1),
    )
    EvidenceLink.objects.bulk_create([link])
    link.refresh_from_db()
    from knowledge.models import Source
    from knowledge.publication import publish_procedure_version
    from knowledge.services import set_evidence_link_sources

    set_evidence_link_sources(link, (Source.objects.get(pk=source_id),))
    if state == "published":
        publish_procedure_version(
            version.pk,
            actor=get_user_model().objects.get(pk=actor_id),
        )

    dataset.service_ids.append(service.pk)
    dataset.procedure_ids.append(procedure.pk)
    dataset.version_ids.append(version.pk)
    dataset.checklist_ids.append(item.pk)
    assert link.pk is not None
    dataset.evidence_ids.append(link.pk)
    return link.pk


def _create_dataset(scale: int) -> _Dataset:
    from django.contrib.auth import get_user_model
    from knowledge.models import Authority, Source

    actor = get_user_model().objects.create_user(username=f"{_PREFIX}actor", is_staff=True)
    dataset = _Dataset(actor.pk, f"{_PREFIX}requested.service")
    authority = Authority.objects.create(
        semantic_id=f"{_PREFIX}authority",
        name_ar="جهة القياس",
        name_en="Measurement authority",
    )
    source = Source.objects.create(
        semantic_id=f"{_PREFIX}source",
        authority=authority,
        title="Disposable measurement source",
        locator="https://example.test/issue119-measurement",
        classification=Source.Classification.OFFICIAL,
        retrieved_on=date(2026, 8, 1),
    )
    dataset.authority_ids.append(authority.pk)
    dataset.source_ids.append(source.pk)

    # The fixed baseline contains requested, unrelated published, and authoring-draft graphs.
    _create_graph(
        dataset, suffix="requested", state="published", actor_id=actor.pk, source_id=source.pk
    )
    _create_graph(
        dataset,
        suffix="baseline-published",
        state="published",
        actor_id=actor.pk,
        source_id=source.pk,
    )
    _create_graph(
        dataset, suffix="baseline-draft", state="draft", actor_id=actor.pk, source_id=source.pk
    )

    # Each scale grows both unrelated published graph records and unrelated authoring drafts.
    generated_event_inputs: list[int] = []
    for index in range(scale):
        generated_event_inputs.append(
            _create_graph(
                dataset,
                suffix=f"published-{index}",
                state="published",
                actor_id=actor.pk,
                source_id=source.pk,
            )
        )
        _create_graph(
            dataset,
            suffix=f"draft-{index}",
            state="draft",
            actor_id=actor.pk,
            source_id=source.pk,
        )

    from knowledge.evidence_workflow import (
        EvidenceReverificationEvent,
        EvidenceReverificationEvidence,
        open_evidence_discrepancy,
        resolve_evidence_discrepancy,
    )
    from knowledge.evidence_workflow_temporal import EvidenceDiscrepancyTransition
    from knowledge.models import EvidenceLink

    # Each unrelated published anchor has two discrepancy transitions (open/resolved) and
    # two repeated semantic-preserving reviews.  The repeated rows intentionally share one
    # anchor so validation_row_counts can distinguish event rows from unique owner rows.
    event_time = datetime(2026, 8, 15, tzinfo=UTC)
    actor_user = get_user_model().objects.get(pk=actor.pk)
    for evidence_id in generated_event_inputs:
        link = EvidenceLink.objects.get(pk=evidence_id)
        discrepancy = open_evidence_discrepancy(
            anchor_evidence_link=link,
            evidence_links=(link,),
            rationale="Issue 119 disposable discrepancy history.",
            actor=actor_user,
            outcome_state="disputed",
        )
        assert discrepancy.pk is not None
        resolve_evidence_discrepancy(
            discrepancy.pk,
            outcome_state="current",
            resolution="Issue 119 disposable discrepancy resolution.",
            actor=actor_user,
        )
        EvidenceDiscrepancyTransition.objects.filter(
            discrepancy=discrepancy,
            event_type=EvidenceDiscrepancyTransition.EventType.OPENED,
        ).update(occurred_at=event_time)
        EvidenceDiscrepancyTransition.objects.filter(
            discrepancy=discrepancy,
            event_type=EvidenceDiscrepancyTransition.EventType.RESOLVED,
        ).update(occurred_at=event_time + timedelta(days=5))
        dataset.discrepancy_ids.append(discrepancy.pk)

    review_values = [
        (evidence_id, event_time + timedelta(days=10 + review_index * 5))
        for evidence_id in generated_event_inputs
        for review_index in range(2)
    ]
    events = EvidenceReverificationEvent.objects.bulk_create(
        [
            EvidenceReverificationEvent(
                anchor_evidence_link_id=evidence_id,
                verification_state="current",
                verified_on=occurred_at.date(),
                reverify_on=date(2027, 8, 15),
                rationale="Issue 119 disposable repeated review event.",
                meaning_changed=False,
                actor_id=actor.pk,
                occurred_at=occurred_at,
            )
            for evidence_id, occurred_at in review_values
        ]
    )
    EvidenceReverificationEvidence.objects.bulk_create(
        [
            EvidenceReverificationEvidence(event_id=event.pk, evidence_link_id=evidence_id)
            for event, (evidence_id, _) in zip(events, review_values, strict=True)
        ]
    )
    dataset.event_ids.extend(event.pk for event in events)
    return dataset


def _vacuum_probe_database() -> None:
    """Keep sequential scale measurements independent of deleted-row table bloat."""

    from django.db import connection

    if connection.in_atomic_block:
        raise RuntimeError("probe database maintenance requires autocommit")
    with connection.cursor() as cursor:
        cursor.execute("VACUUM (ANALYZE)")


def _delete_dataset(dataset: _Dataset) -> None:
    from django.contrib.auth import get_user_model
    from django.db import connection
    from knowledge.aggregate_guard import allow_aggregate_relation_mutation
    from knowledge.evidence_workflow import (
        EvidenceDiscrepancy,
        EvidenceDiscrepancyEvidence,
        EvidenceReverificationEvent,
        EvidenceReverificationEvidence,
    )
    from knowledge.evidence_workflow_temporal import EvidenceDiscrepancyTransition
    from knowledge.models import (
        Authority,
        ChecklistItem,
        EvidenceLink,
        EvidenceLinkSource,
        Procedure,
        ProcedureVersion,
        ProcedureVersionAuditEvent,
        Service,
        ServiceProcedureCandidate,
        Source,
    )

    # Published probe rows are intentionally immutable in production.  This is a disposable
    # database, so disable only the namespaced aggregate guards while removing this probe's rows;
    # PostgreSQL foreign-key triggers remain enabled and deletion order is explicit below.
    guarded_models = (
        EvidenceLinkSource,
        EvidenceLink,
        ChecklistItem,
        ProcedureVersionAuditEvent,
        ProcedureVersion,
    )
    quoted_tables = [connection.ops.quote_name(model._meta.db_table) for model in guarded_models]
    with connection.cursor() as cursor:
        for table in quoted_tables:
            cursor.execute(f"ALTER TABLE {table} DISABLE TRIGGER USER")
    try:
        if dataset.event_ids:
            EvidenceReverificationEvidence.objects.filter(event_id__in=dataset.event_ids).delete()
            EvidenceReverificationEvent.objects.filter(pk__in=dataset.event_ids).delete()
        if dataset.discrepancy_ids:
            EvidenceDiscrepancyEvidence.objects.filter(
                discrepancy_id__in=dataset.discrepancy_ids
            ).delete()
            EvidenceDiscrepancyTransition.objects.filter(
                discrepancy_id__in=dataset.discrepancy_ids
            ).delete()
            EvidenceDiscrepancy.objects.filter(pk__in=dataset.discrepancy_ids).delete()
        if dataset.evidence_ids:
            with allow_aggregate_relation_mutation():
                EvidenceLinkSource.objects.filter(
                    evidence_link_id__in=dataset.evidence_ids
                ).delete()
            EvidenceLink.objects.filter(pk__in=dataset.evidence_ids).delete()
        if dataset.checklist_ids:
            ChecklistItem.objects.filter(pk__in=dataset.checklist_ids).delete()
        if dataset.version_ids:
            ProcedureVersionAuditEvent.objects.filter(version_id__in=dataset.version_ids).delete()
            ProcedureVersion.objects.filter(pk__in=dataset.version_ids).delete()
    finally:
        with connection.cursor() as cursor:
            for table in quoted_tables:
                cursor.execute(f"ALTER TABLE {table} ENABLE TRIGGER USER")
    if dataset.procedure_ids:
        ServiceProcedureCandidate.objects.filter(procedure_id__in=dataset.procedure_ids).delete()
        Procedure.objects.filter(pk__in=dataset.procedure_ids).delete()
    if dataset.service_ids:
        Service.objects.filter(pk__in=dataset.service_ids).delete()
    if dataset.source_ids:
        Source.objects.filter(pk__in=dataset.source_ids).delete()
    if dataset.authority_ids:
        Authority.objects.filter(pk__in=dataset.authority_ids).delete()
    get_user_model().objects.filter(pk=dataset.actor_id).delete()


def main() -> None:
    args = _parse_args()
    try:
        facts = json.loads(args.facts)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--facts must be a JSON object: {exc}") from exc
    if not isinstance(facts, dict):
        raise SystemExit("--facts must be a JSON object")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", args.settings)

    import django

    django.setup()

    from django.db import connection, transaction
    from knowledge.evidence_workflow_temporal import (
        load_consistent_knowledge_snapshot_as_of,
        load_consistent_service_knowledge_snapshot_as_of,
    )
    from knowledge.planning_scope import discover_planning_scope
    from knowledge.snapshot_validation import validation_row_counts

    evaluation_date = date.fromisoformat(args.evaluation_date)
    scales = tuple(int(value) for value in args.scales.split(",") if value.strip())
    if any(value < 0 for value in scales):
        raise SystemExit("--scales values must be non-negative")

    for scale in scales:
        dataset: _Dataset | None = None
        try:
            with transaction.atomic():
                dataset = _create_dataset(scale)
            assert dataset is not None
            scope = discover_planning_scope(dataset.requested_service_id)
            full_metrics, full_snapshot = _measure(
                lambda: load_consistent_knowledge_snapshot_as_of(evaluation_date),
                connection=connection,
            )
            scoped_metrics, scoped_snapshot = _measure(
                lambda current_dataset=dataset: load_consistent_service_knowledge_snapshot_as_of(
                    current_dataset.requested_service_id, evaluation_date
                ),
                connection=connection,
            )
            validation_counts = validation_row_counts(evaluation_date)
            validation_total = sum(validation_counts.values())
            print(
                json.dumps(
                    {
                        "unrelated_published_graphs": scale + 1,
                        "unrelated_draft_graphs": scale + 1,
                        "unrelated_workflow_events": 4 * scale,
                        "catalog_validation_rows": validation_total,
                        "global_validation_rows": {
                            "total": validation_total,
                            "by_queryset": validation_counts,
                        },
                        "detached_object_distinctions": {
                            "shared_fact_definitions": len(scoped_snapshot.fact_definitions),
                            "requested_graph_rows": scoped_metrics["detached_rows"]
                            - len(scoped_snapshot.fact_definitions),
                            "full_catalog_rows": full_metrics["detached_rows"],
                            "unrelated_materialized_rows": full_metrics["detached_rows"]
                            - scoped_metrics["detached_rows"],
                        },
                        "workflow_rows": {
                            "full": _workflow_rows(evaluation_date, scope, scoped=False),
                            "scoped": _workflow_rows(evaluation_date, scope, scoped=True),
                        },
                        "responses_match": _responses_match(
                            dataset.requested_service_id,
                            facts,
                            args.locale,
                            evaluation_date,
                            full_snapshot,
                            scoped_snapshot,
                        ),
                        "full": full_metrics,
                        "scoped": scoped_metrics,
                    },
                    sort_keys=True,
                )
            )
        finally:
            if dataset is not None:
                # Cleanup must run outside one atomic block: PostgreSQL cannot re-enable a
                # trigger while deferred FK events from the same transaction are pending.
                _delete_dataset(dataset)
                _vacuum_probe_database()


if __name__ == "__main__":
    main()
