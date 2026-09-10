from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime

from api.application import execute_planning
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from planning import KnowledgeSnapshot, plan_stateless
from planning.public import PlanningInput

from knowledge.domain import KnowledgeSnapshotLoadError
from knowledge.evidence_workflow import (
    open_evidence_discrepancy,
    record_evidence_reverification,
    resolve_evidence_discrepancy,
)
from knowledge.evidence_workflow_temporal import (
    EvidenceDiscrepancyTransition,
    load_consistent_service_knowledge_snapshot_as_of,
    load_knowledge_snapshot_as_of,
)
from knowledge.models import (
    Authority,
    ChecklistItem,
    EligibilityBasis,
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceContradiction,
    ServiceProcedureCandidate,
    ServiceQuestion,
    Source,
    Step,
    Warning,
)
from knowledge.planning_scope import _discover_procedure_graph, discover_planning_scope
from knowledge.procedure_dependencies import ProcedureDependency
from knowledge.publication import publish_procedure_version
from knowledge.service_point_routing import (
    ProcedureServicePointAssociation,
    ServicePoint,
    ServicePointVersion,
)
from knowledge.services import set_evidence_link_sources
from knowledge.snapshot_validation import (
    _OWNER_FIELDS,
    _load_validation_data,
    validation_row_counts,
)


class ServiceScopedSnapshotTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        self.actor = get_user_model().objects.create_user(username="scoped-publisher")
        self.fact, _ = FactDefinition.objects.get_or_create(
            key="is_student",
            defaults={"kind": FactDefinition.Kind.BOOLEAN, "is_published": True},
        )
        FactDefinition.objects.filter(pk=self.fact.pk).update(is_published=True)
        self.requested = Service.objects.create(
            semantic_id="scoped.requested",
            text_ar="الخدمة المطلوبة",
            text_en="Requested service",
            is_active=True,
        )
        ServiceQuestion.objects.create(
            semantic_id="scoped.requested.question",
            service=self.requested,
            fact=self.fact,
            text_ar="هل؟",
            text_en="Is it?",
            priority=1,
        )
        self.unrelated = Service.objects.create(
            semantic_id="scoped.unrelated",
            text_ar="خدمة أخرى",
            text_en="Unrelated service",
            is_active=True,
        )
        ServiceQuestion.objects.create(
            semantic_id="scoped.unrelated.question",
            service=self.unrelated,
            fact=self.fact,
            text_ar="هل؟",
            text_en="Is it?",
            priority=1,
        )
        self.evidence_by_service: dict[str, EvidenceLink] = {}
        self.requested_procedure = self._procedure(
            self.requested, "scoped.requested.procedure", "Requested procedure"
        )
        self.unrelated_procedure = self._procedure(
            self.unrelated, "scoped.unrelated.procedure", "Unrelated procedure"
        )

    def _draft_procedure(
        self,
        service: Service,
        semantic_id: str,
        title: str,
        *,
        selection_value: bool = True,
    ) -> tuple[Procedure, ProcedureVersion]:
        procedure = Procedure.objects.create(
            semantic_id=semantic_id,
            text_ar=title,
            text_en=title,
            primary_service=service,
        )
        ServiceProcedureCandidate.objects.create(
            service=service,
            procedure=procedure,
            selection_predicate={
                "op": "eq",
                "fact": self.fact.key,
                "value": selection_value,
            },
        )
        version = ProcedureVersion.objects.create(
            semantic_id=f"{semantic_id}.v1",
            procedure=procedure,
            text_ar=title,
            text_en=title,
            applicability={"op": "eq", "fact": self.fact.key, "value": True},
        )
        return procedure, version

    def _procedure(self, service: Service, semantic_id: str, title: str) -> Procedure:
        procedure, version = self._draft_procedure(service, semantic_id, title)
        item = ChecklistItem.objects.create(
            procedure_version=version,
            semantic_id="required",
            text_ar="مطلوب",
            text_en="Required",
            classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
            verification_state="current",
            verified_on=date(2026, 8, 1),
        )
        authority = Authority.objects.create(
            semantic_id=f"{semantic_id}.authority",
            name_ar="جهة",
            name_en="Authority",
        )
        source = Source.objects.create(
            semantic_id=f"{semantic_id}.source",
            authority=authority,
            title="Probe source",
            locator="https://example.test/probe",
            classification=Source.Classification.OFFICIAL,
            retrieved_on=date(2026, 8, 1),
        )
        link = EvidenceLink.objects.create(
            checklist_item=item,
            semantic_id="required.evidence",
            passage="Relied-upon passage",
            location="Section 1",
            applicability_context="Applies to this procedure",
            verification_state="current",
            verified_on=date(2026, 8, 1),
            support_status=EvidenceLink.SupportStatus.SUPPORTS,
        )
        set_evidence_link_sources(link, (source,))
        self.evidence_by_service[service.semantic_id] = link
        publish_procedure_version(version.pk, actor=self.actor)
        return procedure

    def _add_dependency(
        self, version: ProcedureVersion, target: Procedure, semantic_id: str
    ) -> ProcedureDependency:
        dependency = ProcedureDependency.objects.create(
            procedure_version=version,
            semantic_id=semantic_id,
            text_ar="استوفِ الإجراء السابق",
            text_en="Complete the prerequisite procedure",
            target_procedure=target,
            relation=ProcedureDependency.Relation.BLOCKING_PREREQUISITE,
            applicability={},
            satisfied_when={"op": "eq", "fact": self.fact.key, "value": True},
            verification_state="current",
            verified_on=date(2026, 8, 1),
        )
        source_id = (
            self.evidence_by_service[target.primary_service.semantic_id]
            .source_links.values_list("source_id", flat=True)
            .first()
        )
        assert source_id is not None
        source = Source.objects.get(pk=source_id)
        link = EvidenceLink.objects.create(
            procedure_dependency=dependency,
            semantic_id=f"{semantic_id}.evidence",
            passage="Prerequisite passage",
            location="Section 2",
            applicability_context="Applies to this procedure",
            verification_state="current",
            verified_on=date(2026, 8, 1),
            support_status=EvidenceLink.SupportStatus.SUPPORTS,
        )
        set_evidence_link_sources(link, (source,))
        return dependency

    def _published_workflow_owner_probe(
        self, service: Service, semantic_id: str
    ) -> tuple[Procedure, ChecklistItem, Step, EvidenceLink]:
        procedure, version = self._draft_procedure(service, semantic_id, "Workflow owner probe")
        item = ChecklistItem.objects.create(
            procedure_version=version,
            semantic_id="workflow-checklist",
            text_ar="متطلب فحص سير العمل",
            text_en="Workflow probe requirement",
            classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
            verification_state="current",
            verified_on=date(2026, 8, 1),
        )
        step = Step.objects.create(
            procedure_version=version,
            semantic_id="workflow-step",
            text_ar="خطوة فحص سير العمل",
            text_en="Workflow probe step",
            phase="probe",
            verification_state="unknown",
        )
        Warning.objects.create(
            procedure_version=version,
            semantic_id="workflow-regeneration-warning",
            text_ar="تحقق من التجديد",
            text_en="Check regeneration",
            severity=Warning.Severity.IMPORTANT,
            kind=Warning.Kind.PRODUCT,
            role=Warning.Role.REGENERATION,
        )
        source_id = (
            self.evidence_by_service[service.semantic_id]
            .source_links.values_list("source_id", flat=True)
            .first()
        )
        assert source_id is not None
        link = EvidenceLink.objects.create(
            checklist_item=item,
            semantic_id="workflow-owner-evidence",
            passage="Workflow owner probe passage",
            location="Workflow owner probe section",
            applicability_context="Workflow owner probe context",
            verification_state="current",
            verified_on=date(2026, 8, 1),
            support_status=EvidenceLink.SupportStatus.SUPPORTS,
        )
        set_evidence_link_sources(link, (Source.objects.get(pk=source_id),))
        publish_procedure_version(version.pk, actor=self.actor)
        event = record_evidence_reverification(
            anchor_evidence_link=link,
            reviewed_evidence_links=(link,),
            verification_state="disputed",
            verified_on=date(2026, 8, 1),
            reverify_on=None,
            rationale="Create visible multiple-owner workflow history.",
            actor=self.actor,
        )
        from knowledge.evidence_workflow import EvidenceReverificationEvent

        EvidenceReverificationEvent.objects.filter(pk=event.pk).update(
            occurred_at=datetime(2026, 8, 1, tzinfo=UTC)
        )
        return procedure, item, step, link

    @contextmanager
    def _persist_malformed_workflow_owner(
        self, link: EvidenceLink, *, owner_field: str | None = None, owner_id: int | None = None
    ) -> Iterator[None]:
        """Temporarily bypass the PostgreSQL owner guard for persisted-row loader tests."""

        if owner_field is not None and owner_field not in set(_OWNER_FIELDS):
            raise ValueError(f"Unsupported workflow owner field: {owner_field}")
        if owner_field is not None and owner_id is None:
            raise ValueError("An owner id is required when adding a second owner")
        owner_columns = tuple(f"{field}_id" for field in _OWNER_FIELDS)
        table = connection.ops.quote_name(EvidenceLink._meta.db_table)
        constraint_name = "evidence_exactly_one_owner"
        quoted_constraint = connection.ops.quote_name(constraint_name)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_get_constraintdef(c.oid) "
                "FROM pg_constraint AS c "
                "WHERE c.conrelid = %s::regclass AND c.conname = %s",
                [EvidenceLink._meta.db_table, constraint_name],
            )
            row = cursor.fetchone()
            if row is None:
                raise AssertionError("The production EvidenceLink owner constraint is missing")
            constraint_definition = row[0]
            cursor.execute(f"ALTER TABLE {table} DISABLE TRIGGER USER")
            cursor.execute(f"ALTER TABLE {table} DROP CONSTRAINT {quoted_constraint}")

        original = tuple(EvidenceLink.objects.filter(pk=link.pk).values_list(*owner_columns).get())
        malformed = list(original)
        if owner_field is None:
            malformed = [None] * len(owner_columns)
        else:
            malformed[owner_columns.index(f"{owner_field}_id")] = owner_id
        assignments = ", ".join(f"{column} = %s" for column in owner_columns)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"UPDATE {table} SET {assignments} WHERE id = %s",
                    [*malformed, link.pk],
                )
            yield
        finally:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {table} SET {assignments} WHERE id = %s",
                        [*original, link.pk],
                    )
            finally:
                with connection.cursor() as cursor:
                    cursor.execute(f"ALTER TABLE {table} ENABLE TRIGGER USER")
                    cursor.execute(
                        f"ALTER TABLE {table} ADD CONSTRAINT {quoted_constraint} "
                        f"{constraint_definition}"
                    )
            restored = tuple(
                EvidenceLink.objects.filter(pk=link.pk).values_list(*owner_columns).get()
            )
            if restored != original:
                raise AssertionError("Malformed workflow owner fixture did not restore its row")

    def _published_ownerless_workflow_anchor(
        self, service: Service, semantic_id: str
    ) -> EvidenceLink:
        _, version = self._draft_procedure(service, semantic_id, "Published ownerless probe")
        step = Step.objects.create(
            procedure_version=version,
            semantic_id="ownerless-workflow-step",
            text_ar="خطوة فحص المالك",
            text_en="Ownerless workflow step",
            phase="probe",
            verification_state="unknown",
        )
        Warning.objects.create(
            procedure_version=version,
            semantic_id="ownerless-regeneration-warning",
            text_ar="تحقق من التجديد",
            text_en="Check regeneration",
            severity=Warning.Severity.IMPORTANT,
            kind=Warning.Kind.PRODUCT,
            role=Warning.Role.REGENERATION,
        )
        source_id = (
            self.evidence_by_service[service.semantic_id]
            .source_links.values_list("source_id", flat=True)
            .first()
        )
        assert source_id is not None
        link = EvidenceLink.objects.create(
            step=step,
            semantic_id="ownerless-workflow-evidence",
            passage="Ownerless workflow anchor passage",
            location="Ownerless workflow section",
            applicability_context="Ownerless workflow context",
            verification_state="current",
            verified_on=date(2026, 8, 1),
            support_status=EvidenceLink.SupportStatus.SUPPORTS,
        )
        set_evidence_link_sources(link, (Source.objects.get(pk=source_id),))
        publish_procedure_version(version.pk, actor=self.actor)
        from knowledge.evidence_workflow import (
            EvidenceReverificationEvent,
            EvidenceReverificationEvidence,
        )

        event = EvidenceReverificationEvent.objects.create(
            anchor_evidence_link=link,
            verification_state="current",
            verified_on=date(2026, 8, 1),
            reverify_on=date(2027, 8, 1),
            rationale="Create a visible published workflow anchor for owner validation.",
            meaning_changed=False,
            actor=self.actor,
        )
        EvidenceReverificationEvent.objects.filter(pk=event.pk).update(
            occurred_at=datetime(2026, 8, 1, tzinfo=UTC)
        )
        EvidenceReverificationEvidence.objects.create(event=event, evidence_link=link)
        return link

    def test_consistent_loader_materializes_only_requested_graph(self) -> None:
        snapshot = load_consistent_service_knowledge_snapshot_as_of(
            self.requested.semantic_id, date(2026, 9, 1)
        )

        self.assertEqual(
            tuple(service.semantic_id for service in snapshot.services),
            (self.requested.semantic_id,),
        )
        self.assertEqual(
            tuple(version.procedure_semantic_id for version in snapshot.procedure_versions),
            (self.requested_procedure.semantic_id,),
        )
        planning_input = PlanningInput(
            self.requested.semantic_id,
            {self.fact.key: True},
            "en",
            date(2026, 9, 1),
        )
        full = load_knowledge_snapshot_as_of(date(2026, 9, 1))
        self.assertEqual(
            plan_stateless(snapshot, planning_input),
            plan_stateless(full, planning_input),
        )
        self.assertEqual(
            execute_planning(planning_input, snapshot_loader=lambda: snapshot),
            execute_planning(planning_input, snapshot_loader=lambda: full),
        )

    def test_temporal_history_is_reconstructed_only_for_scoped_owners(self) -> None:
        record_evidence_reverification(
            anchor_evidence_link=self.evidence_by_service[self.requested.semantic_id],
            reviewed_evidence_links=(self.evidence_by_service[self.requested.semantic_id],),
            verification_state="disputed",
            verified_on=date(2026, 9, 1),
            reverify_on=None,
            rationale="Requested-service historical dispute.",
            actor=self.actor,
        )
        record_evidence_reverification(
            anchor_evidence_link=self.evidence_by_service[self.unrelated.semantic_id],
            reviewed_evidence_links=(self.evidence_by_service[self.unrelated.semantic_id],),
            verification_state="disputed",
            verified_on=date(2026, 9, 1),
            reverify_on=None,
            rationale="Unrelated historical dispute.",
            actor=self.actor,
        )

        snapshot = load_consistent_service_knowledge_snapshot_as_of(
            self.requested.semantic_id, date(2026, 12, 31)
        )
        self.assertEqual(len(snapshot.procedure_versions), 1)
        self.assertEqual(
            snapshot.procedure_versions[0].checklist_items[0].verification_state, "disputed"
        )
        self.assertEqual(
            snapshot.procedure_versions[0].checklist_items[0].evidence_links[0].verification_state,
            "disputed",
        )
        planning_input = PlanningInput(
            self.requested.semantic_id,
            {self.fact.key: True},
            "en",
            date(2026, 12, 31),
        )
        full = load_knowledge_snapshot_as_of(date(2026, 12, 31))
        self.assertEqual(
            execute_planning(planning_input, snapshot_loader=lambda: snapshot),
            execute_planning(planning_input, snapshot_loader=lambda: full),
        )

    def test_temporal_discrepancy_open_and_resolution_are_scoped(self) -> None:
        requested_discrepancy = open_evidence_discrepancy(
            anchor_evidence_link=self.evidence_by_service[self.requested.semantic_id],
            evidence_links=(self.evidence_by_service[self.requested.semantic_id],),
            rationale="Requested-service discrepancy.",
            actor=self.actor,
            outcome_state="disputed",
        )
        unrelated_discrepancy = open_evidence_discrepancy(
            anchor_evidence_link=self.evidence_by_service[self.unrelated.semantic_id],
            evidence_links=(self.evidence_by_service[self.unrelated.semantic_id],),
            rationale="Unrelated discrepancy.",
            actor=self.actor,
            outcome_state="disputed",
        )
        assert requested_discrepancy.pk is not None
        resolve_evidence_discrepancy(
            requested_discrepancy.pk,
            outcome_state="current",
            resolution="Resolved for the requested service.",
            actor=self.actor,
        )

        snapshot = load_consistent_service_knowledge_snapshot_as_of(
            self.requested.semantic_id, date(2026, 12, 31)
        )
        self.assertEqual(
            snapshot.procedure_versions[0].checklist_items[0].verification_state,
            "current",
        )
        self.assertNotEqual(requested_discrepancy.pk, unrelated_discrepancy.pk)
        self.assertEqual(len(snapshot.procedure_versions), 1)
        planning_input = PlanningInput(
            self.requested.semantic_id,
            {self.fact.key: True},
            "en",
            date(2026, 12, 31),
        )
        full = load_knowledge_snapshot_as_of(date(2026, 12, 31))
        self.assertEqual(
            execute_planning(planning_input, snapshot_loader=lambda: snapshot),
            execute_planning(planning_input, snapshot_loader=lambda: full),
        )

    def test_consistent_loader_rejects_nested_transactions(self) -> None:
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                load_consistent_service_knowledge_snapshot_as_of(
                    self.requested.semantic_id, date(2026, 9, 1)
                )

    def test_consistent_loader_establishes_outer_read_only_repeatable_read_snapshot(self) -> None:
        with CaptureQueriesContext(connection) as queries:
            load_consistent_service_knowledge_snapshot_as_of(
                self.requested.semantic_id, date(2026, 9, 1)
            )

        self.assertTrue(
            any(
                query["sql"].startswith(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                )
                for query in queries
            )
        )

    def _promote_corrupt_probe_version(self, version: ProcedureVersion) -> None:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('bardi.procedure_version_lifecycle', 'publish', true)"
                )
            ProcedureVersion.objects.filter(pk=version.pk).update(
                state=ProcedureVersion.State.PUBLISHED,
                published_at=datetime(2026, 8, 1, tzinfo=UTC),
                published_by_id=self.actor.pk,
            )

    def _assert_full_and_scoped_failures_match(self) -> None:
        with self.assertRaises(KnowledgeSnapshotLoadError) as full_error:
            load_knowledge_snapshot_as_of(date(2026, 9, 1))
        with self.assertRaises(KnowledgeSnapshotLoadError) as scoped_error:
            load_consistent_service_knowledge_snapshot_as_of(
                self.requested.semantic_id, date(2026, 9, 1)
            )
        self.assertEqual(full_error.exception.owner_ids, scoped_error.exception.owner_ids)

    def test_relevant_and_unrelated_invalid_checklist_rules_are_fail_closed(self) -> None:
        probes: list[tuple[Service, str]] = [
            (self.requested, "scoped.invalid.relevant-checklist"),
            (self.unrelated, "scoped.invalid.unrelated-checklist"),
        ]
        for service, semantic_id in probes:
            procedure, version = self._draft_procedure(service, semantic_id, "Invalid checklist")
            ChecklistItem.objects.bulk_create(
                [
                    ChecklistItem(
                        procedure_version=version,
                        semantic_id="invalid-checklist",
                        text_ar="عنصر غير صالح",
                        text_en="Invalid checklist",
                        classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
                        applicability={"op": "not-a-rule"},
                        verification_state="unknown",
                    )
                ]
            )
            self._promote_corrupt_probe_version(version)
            self.assertEqual(procedure.primary_service_id, service.pk)

        self._assert_full_and_scoped_failures_match()

    def test_relevant_and_unrelated_invalid_evidence_are_fail_closed(self) -> None:
        for service, semantic_id in (
            (self.requested, "scoped.invalid.relevant-evidence"),
            (self.unrelated, "scoped.invalid.unrelated-evidence"),
        ):
            _, version = self._draft_procedure(service, semantic_id, "Invalid evidence")
            ChecklistItem.objects.create(
                procedure_version=version,
                semantic_id="missing-evidence",
                text_ar="دليل ناقص",
                text_en="Missing evidence",
                classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
                verification_state="current",
            )
            self._promote_corrupt_probe_version(version)

        self._assert_full_and_scoped_failures_match()

    def test_relevant_and_unrelated_invalid_bases_are_fail_closed(self) -> None:
        for service, semantic_id in (
            (self.requested, "scoped.invalid.relevant-basis"),
            (self.unrelated, "scoped.invalid.unrelated-basis"),
        ):
            _, version = self._draft_procedure(service, semantic_id, "Invalid basis")
            EligibilityBasis.objects.bulk_create(
                [
                    EligibilityBasis(
                        procedure_version=version,
                        semantic_id="invalid-basis",
                        text_ar="أساس غير صالح",
                        text_en="Invalid basis",
                        reachability={},
                        qualification={},
                        verification_state="current",
                    )
                ]
            )
            self._promote_corrupt_probe_version(version)

        self._assert_full_and_scoped_failures_match()

    def test_relevant_and_unrelated_invalid_dependencies_are_fail_closed(self) -> None:
        for service, target, semantic_id in (
            (self.requested, self.unrelated_procedure, "scoped.invalid.relevant-dependency"),
            (self.unrelated, self.requested_procedure, "scoped.invalid.unrelated-dependency"),
        ):
            _, version = self._draft_procedure(service, semantic_id, "Invalid dependency")
            ProcedureDependency.objects.bulk_create(
                [
                    ProcedureDependency(
                        procedure_version=version,
                        semantic_id="invalid-dependency",
                        text_ar="تبعية غير صالحة",
                        text_en="Invalid dependency",
                        target_procedure=target,
                        relation=ProcedureDependency.Relation.BLOCKING_PREREQUISITE,
                        applicability={},
                        satisfied_when={},
                        verification_state="current",
                    )
                ]
            )
            self._promote_corrupt_probe_version(version)

        self._assert_full_and_scoped_failures_match()

    def test_relevant_and_unrelated_invalid_routing_are_fail_closed(self) -> None:
        point = ServicePoint.objects.create(
            semantic_id="scoped.invalid-routing-point",
            name_ar="نقطة غير صالحة",
            name_en="Invalid routing point",
        )
        material = ServicePointVersion.objects.create(
            semantic_id="scoped.invalid-routing-material",
            service_point=point,
            address_ar="عنوان",
            address_en="Address",
            availability=ServicePointVersion.Availability.AVAILABLE,
            effective_from=date(2026, 1, 1),
            verification_state="unknown",
        )
        for service, semantic_id in (
            (self.requested, "scoped.invalid.relevant-routing"),
            (self.unrelated, "scoped.invalid.unrelated-routing"),
        ):
            _, version = self._draft_procedure(service, semantic_id, "Invalid routing")
            ProcedureServicePointAssociation.objects.bulk_create(
                [
                    ProcedureServicePointAssociation(
                        procedure_version=version,
                        semantic_id="invalid-routing",
                        service_point_version=material,
                        applicability={},
                        verification_state="current",
                    )
                ]
            )
            self._promote_corrupt_probe_version(version)

        self._assert_full_and_scoped_failures_match()

    def test_validation_row_counts_preserves_repeated_history_rows(self) -> None:
        link = self.evidence_by_service[self.requested.semantic_id]
        discrepancy = open_evidence_discrepancy(
            anchor_evidence_link=link,
            evidence_links=(link,),
            rationale="Repeated history row accounting probe.",
            actor=self.actor,
            outcome_state="disputed",
        )
        assert discrepancy.pk is not None
        resolve_evidence_discrepancy(
            discrepancy.pk,
            outcome_state="current",
            resolution="Repeated history row accounting probe resolved.",
            actor=self.actor,
        )
        EvidenceDiscrepancyTransition.objects.filter(
            discrepancy=discrepancy,
            event_type=EvidenceDiscrepancyTransition.EventType.OPENED,
        ).update(occurred_at=datetime(2026, 9, 1, tzinfo=UTC))
        EvidenceDiscrepancyTransition.objects.filter(
            discrepancy=discrepancy,
            event_type=EvidenceDiscrepancyTransition.EventType.RESOLVED,
        ).update(occurred_at=datetime(2026, 9, 2, tzinfo=UTC))
        for verified_on in (date(2026, 9, 3), date(2026, 9, 4)):
            event = record_evidence_reverification(
                anchor_evidence_link=link,
                reviewed_evidence_links=(link,),
                verification_state="current",
                verified_on=verified_on,
                reverify_on=date(2027, 9, 3),
                rationale="Repeated history row accounting review.",
                actor=self.actor,
            )
            from knowledge.evidence_workflow import EvidenceReverificationEvent

            EvidenceReverificationEvent.objects.filter(pk=event.pk).update(
                occurred_at=datetime(
                    verified_on.year, verified_on.month, verified_on.day, tzinfo=UTC
                )
            )

        counts = validation_row_counts(date(2026, 12, 31))
        self.assertEqual(counts["workflow_discrepancy_transitions"], 2)
        self.assertEqual(counts["workflow_reverification_events"], 2)
        self.assertEqual(counts["workflow_owner_rows"], 1)

    def test_actual_full_and_scoped_loaders_accept_multiple_owners_with_first_match(
        self,
    ) -> None:
        probes = (
            (self.requested, "scoped.multiple-owner.requested"),
            (self.unrelated, "scoped.multiple-owner.unrelated"),
        )
        for service, semantic_id in probes:
            with self.subTest(service=service.semantic_id):
                procedure, checklist_item, step, link = self._published_workflow_owner_probe(
                    service, semantic_id
                )
                with self._persist_malformed_workflow_owner(
                    link, owner_field="step", owner_id=step.pk
                ):
                    full = load_knowledge_snapshot_as_of(date(2026, 9, 1))
                    scoped = load_consistent_service_knowledge_snapshot_as_of(
                        service.semantic_id, date(2026, 9, 1)
                    )
                    planning_input = PlanningInput(
                        service.semantic_id,
                        {self.fact.key: True},
                        "en",
                        date(2026, 9, 1),
                    )

                    def full_loader(snapshot: KnowledgeSnapshot = full) -> KnowledgeSnapshot:
                        return snapshot

                    def scoped_loader(snapshot: KnowledgeSnapshot = scoped) -> KnowledgeSnapshot:
                        return snapshot

                    self.assertEqual(
                        execute_planning(planning_input, snapshot_loader=full_loader),
                        execute_planning(planning_input, snapshot_loader=scoped_loader),
                    )
                    if service is self.unrelated:
                        requested_input = PlanningInput(
                            self.requested.semantic_id,
                            {self.fact.key: True},
                            "en",
                            date(2026, 9, 1),
                        )
                        requested_scoped = load_consistent_service_knowledge_snapshot_as_of(
                            self.requested.semantic_id, date(2026, 9, 1)
                        )

                        def full_requested_loader(
                            snapshot: KnowledgeSnapshot = full,
                        ) -> KnowledgeSnapshot:
                            return snapshot

                        def requested_scoped_loader(
                            snapshot: KnowledgeSnapshot = requested_scoped,
                        ) -> KnowledgeSnapshot:
                            return snapshot

                        self.assertEqual(
                            execute_planning(
                                requested_input, snapshot_loader=full_requested_loader
                            ),
                            execute_planning(
                                requested_input, snapshot_loader=requested_scoped_loader
                            ),
                        )
                    for snapshot in (full, scoped):
                        version = next(
                            version
                            for version in snapshot.procedure_versions
                            if version.procedure_semantic_id == procedure.semantic_id
                        )
                        loaded_item = next(
                            candidate
                            for candidate in version.checklist_items
                            if candidate.semantic_id == checklist_item.semantic_id
                        )
                        loaded_step = next(
                            candidate
                            for candidate in version.steps
                            if candidate.semantic_id == step.semantic_id
                        )
                        self.assertEqual(loaded_item.semantic_id, checklist_item.semantic_id)
                        self.assertEqual(loaded_item.verification_state, "disputed")
                        self.assertEqual(
                            tuple(evidence.semantic_id for evidence in loaded_item.evidence_links),
                            (link.semantic_id,),
                        )
                        self.assertEqual(
                            loaded_item.evidence_links[0].verification_state, "disputed"
                        )
                        self.assertEqual(loaded_step.verification_state, "unknown")
                        self.assertEqual(loaded_step.evidence_links, ())

    def test_actual_full_and_scoped_loaders_reject_ownerless_persisted_workflow_anchors(
        self,
    ) -> None:
        for service, semantic_id in (
            (self.requested, "scoped.ownerless.requested"),
            (self.unrelated, "scoped.ownerless.unrelated"),
        ):
            with self.subTest(service=service.semantic_id):
                link = self._published_ownerless_workflow_anchor(service, semantic_id)
                with self._persist_malformed_workflow_owner(link):
                    with self.assertRaises(ValidationError) as full_error:
                        load_knowledge_snapshot_as_of(date(2026, 9, 1))
                    with self.assertRaises(ValidationError) as scoped_error:
                        load_consistent_service_knowledge_snapshot_as_of(
                            service.semantic_id, date(2026, 9, 1)
                        )
                    if service is self.unrelated:
                        with self.assertRaises(ValidationError) as requested_scoped_error:
                            load_consistent_service_knowledge_snapshot_as_of(
                                self.requested.semantic_id, date(2026, 9, 1)
                            )
                    else:
                        requested_scoped_error = scoped_error
                self.assertEqual(str(full_error.exception), str(scoped_error.exception))
                self.assertEqual(str(full_error.exception), str(requested_scoped_error.exception))

    def test_unknown_service_is_an_explicit_empty_scope(self) -> None:
        snapshot = load_consistent_service_knowledge_snapshot_as_of(
            "scoped.unknown", date(2026, 9, 1)
        )
        self.assertEqual(snapshot.services, ())
        self.assertEqual(snapshot.procedure_versions, ())
        self.assertTrue(snapshot.fact_definitions)

    def test_unrelated_global_rule_failure_is_retained(self) -> None:
        ServiceProcedureCandidate.objects.filter(service=self.unrelated).update(
            selection_predicate={"op": "not-a-rule"}
        )

        with self.assertRaises(KnowledgeSnapshotLoadError) as caught:
            load_consistent_service_knowledge_snapshot_as_of(
                self.requested.semantic_id, date(2026, 9, 1)
            )
        self.assertEqual(
            caught.exception.owner_ids,
            ("candidate:scoped.unrelated:scoped.unrelated.procedure",),
        )

    def test_scoped_graph_closure_terminates_on_a_cycle(self) -> None:
        versions = {1: (11,), 2: (22,), 3: (33,)}
        targets = {11: (2,), 22: (3,), 33: (1,)}

        procedure_ids, version_ids = _discover_procedure_graph(
            (1,),
            lambda procedure_ids: (
                version
                for procedure_id in procedure_ids
                for version in versions.get(procedure_id, ())
            ),
            lambda current_versions: (
                target for version in current_versions for target in targets.get(version, ())
            ),
        )

        self.assertEqual(procedure_ids, frozenset({1, 2, 3}))
        self.assertEqual(version_ids, frozenset({11, 22, 33}))

    def test_scoped_graph_includes_transitive_dependency_targets(self) -> None:
        grand_target = self._procedure(self.unrelated, "scoped.grand-target", "Grand target")
        target, target_version = self._draft_procedure(
            self.unrelated,
            "scoped.target",
            "Target",
            selection_value=False,
        )
        self._add_dependency(target_version, grand_target, "scoped.target.requires-grand")
        publish_procedure_version(target_version.pk, actor=self.actor)

        dependent, dependent_version = self._draft_procedure(
            self.requested,
            "scoped.dependent",
            "Dependent",
            selection_value=False,
        )
        self._add_dependency(dependent_version, target, "scoped.dependent.requires-target")
        publish_procedure_version(dependent_version.pk, actor=self.actor)

        scope = discover_planning_scope(self.requested.semantic_id)
        self.assertEqual(
            {self.requested_procedure, target, grand_target, dependent},
            set(Procedure.objects.filter(pk__in=scope.procedure_ids)),
        )
        snapshot = load_consistent_service_knowledge_snapshot_as_of(
            self.requested.semantic_id, date(2026, 9, 1)
        )
        self.assertEqual(
            {version.procedure_semantic_id for version in snapshot.procedure_versions},
            {
                self.requested_procedure.semantic_id,
                dependent.semantic_id,
                target.semantic_id,
                grand_target.semantic_id,
            },
        )
        planning_input = PlanningInput(
            self.requested.semantic_id,
            {self.fact.key: True},
            "en",
            date(2026, 9, 1),
        )
        full = load_knowledge_snapshot_as_of(date(2026, 9, 1))
        self.assertEqual(
            plan_stateless(snapshot, planning_input), plan_stateless(full, planning_input)
        )
        self.assertEqual(
            execute_planning(planning_input, snapshot_loader=lambda: snapshot),
            execute_planning(planning_input, snapshot_loader=lambda: full),
        )

    def test_shared_service_point_material_is_loaded_without_unrelated_association(self) -> None:
        point = ServicePoint.objects.create(
            semantic_id="scoped.shared-point",
            name_ar="نقطة مشتركة",
            name_en="Shared point",
        )
        material = ServicePointVersion.objects.create(
            semantic_id="scoped.shared-point.v1",
            service_point=point,
            address_ar="العنوان",
            address_en="Address",
            availability=ServicePointVersion.Availability.AVAILABLE,
            effective_from=date(2026, 1, 1),
            verification_state="current",
            verified_on=date(2026, 8, 1),
        )
        source_id = (
            self.evidence_by_service[self.unrelated.semantic_id]
            .source_links.values_list("source_id", flat=True)
            .first()
        )
        assert source_id is not None
        source = Source.objects.get(pk=source_id)
        ServiceProcedureCandidate.objects.filter(
            service=self.requested, procedure=self.requested_procedure
        ).update(selection_predicate={"op": "eq", "fact": self.fact.key, "value": False})
        requested_procedure, requested_version = self._draft_procedure(
            self.requested, "scoped.routed-request", "Routed requested", selection_value=True
        )
        unrelated_procedure, unrelated_version = self._draft_procedure(
            self.unrelated, "scoped.routed-unrelated", "Routed unrelated", selection_value=False
        )
        for version, semantic_id in (
            (requested_version, "scoped.routed-request.association"),
            (unrelated_version, "scoped.routed-unrelated.association"),
        ):
            association = ProcedureServicePointAssociation.objects.create(
                procedure_version=version,
                semantic_id=semantic_id,
                service_point_version=material,
                applicability={"op": "eq", "fact": self.fact.key, "value": True},
                verification_state="current",
                verified_on=date(2026, 8, 1),
            )
            link = EvidenceLink.objects.create(
                procedure_service_point_association=association,
                semantic_id=f"{semantic_id}.evidence",
                passage="Association passage",
                location="Section 4",
                applicability_context="Requested jurisdiction",
                verification_state="current",
                verified_on=date(2026, 8, 1),
                support_status=EvidenceLink.SupportStatus.SUPPORTS,
            )
            set_evidence_link_sources(link, (source,))
        material_link = EvidenceLink.objects.create(
            service_point_version=material,
            semantic_id="scoped.shared-point.evidence",
            passage="Shared point passage",
            location="Section 3",
            applicability_context="Shared jurisdiction",
            verification_state="current",
            verified_on=date(2026, 8, 1),
            support_status=EvidenceLink.SupportStatus.SUPPORTS,
        )
        set_evidence_link_sources(material_link, (source,))
        publish_procedure_version(requested_version.pk, actor=self.actor)
        publish_procedure_version(unrelated_version.pk, actor=self.actor)

        snapshot = load_consistent_service_knowledge_snapshot_as_of(
            self.requested.semantic_id, date(2026, 9, 1)
        )
        loaded_version_ids = {
            version.procedure_semantic_id for version in snapshot.procedure_versions
        }
        self.assertIn(requested_procedure.semantic_id, loaded_version_ids)
        self.assertNotIn(unrelated_procedure.semantic_id, loaded_version_ids)
        self.assertEqual(
            tuple(
                material_version.semantic_id for material_version in snapshot.service_point_versions
            ),
            (material.semantic_id,),
        )
        self.assertEqual(
            snapshot.service_point_versions[0].evidence_links[0].sources[0].semantic_id,
            source.semantic_id,
        )
        routed = next(
            version
            for version in snapshot.procedure_versions
            if version.procedure_semantic_id == requested_procedure.semantic_id
        )
        self.assertEqual(
            tuple(item.semantic_id for item in routed.service_point_associations),
            ("scoped.routed-request.association",),
        )
        planning_input = PlanningInput(
            self.requested.semantic_id,
            {self.fact.key: True},
            "en",
            date(2026, 9, 1),
        )
        full = load_knowledge_snapshot_as_of(date(2026, 9, 1))
        self.assertEqual(
            execute_planning(planning_input, snapshot_loader=lambda: snapshot),
            execute_planning(planning_input, snapshot_loader=lambda: full),
        )

    def test_draft_evidence_is_outside_validation_owner_universe(self) -> None:
        baseline = _load_validation_data()
        draft_procedure, draft_version = self._draft_procedure(
            self.unrelated, "scoped.unrelated.draft-evidence", "Unrelated draft evidence"
        )
        draft_item = ChecklistItem.objects.create(
            procedure_version=draft_version,
            semantic_id="draft-only-item",
            text_ar="عنصر مسودة",
            text_en="Draft-only item",
            classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
            verification_state="current",
        )
        source_id = (
            self.evidence_by_service[self.unrelated.semantic_id]
            .source_links.values_list("source_id", flat=True)
            .first()
        )
        assert source_id is not None
        source = Source.objects.get(pk=source_id)
        draft_link = EvidenceLink.objects.create(
            checklist_item=draft_item,
            semantic_id="draft-only-evidence",
            passage="Draft passage",
            location="Draft section",
            applicability_context="Draft context",
            verification_state="current",
            verified_on=date(2026, 8, 1),
            support_status=EvidenceLink.SupportStatus.SUPPORTS,
        )
        set_evidence_link_sources(draft_link, (source,))

        expanded = _load_validation_data()
        self.assertEqual(expanded.evidence, baseline.evidence)
        self.assertNotIn(("checklist_item", draft_item.pk), expanded.evidence)
        self.assertEqual(draft_procedure.primary_service_id, self.unrelated.pk)

    def test_scoped_object_and_sql_work_do_not_grow_with_unrelated_services(self) -> None:
        def load() -> tuple[tuple[str, ...], int, int]:
            with CaptureQueriesContext(connection) as queries:
                snapshot = load_consistent_service_knowledge_snapshot_as_of(
                    self.requested.semantic_id, date(2026, 9, 1)
                )
            detached_rows = len(snapshot.fact_definitions) + len(snapshot.services)
            detached_rows += len(snapshot.procedure_versions)
            for service in snapshot.services:
                detached_rows += (
                    len(service.candidates) + len(service.questions) + len(service.contradictions)
                )
            for version in snapshot.procedure_versions:
                for attribute in (
                    "checklist_items",
                    "eligibility_bases",
                    "steps",
                    "fees",
                    "warnings",
                    "dependencies",
                    "service_point_associations",
                ):
                    items = getattr(version, attribute)
                    detached_rows += len(items)
                    detached_rows += sum(
                        1
                        + len(item.evidence_links)
                        + sum(len(link.sources) for link in item.evidence_links)
                        for item in items
                    )
            detached_rows += len(snapshot.service_points) + len(snapshot.service_point_versions)
            detached_rows += sum(
                len(item.evidence_links) + sum(len(link.sources) for link in item.evidence_links)
                for item in snapshot.service_point_versions
            )
            return (
                tuple(service.semantic_id for service in snapshot.services),
                detached_rows,
                len(queries),
            )

        before_services, before_rows, before_queries = load()
        Service.objects.bulk_create(
            [
                Service(
                    semantic_id=f"scoped.growth.{index}",
                    text_ar="خدمة نمو",
                    text_en="Growth service",
                    is_active=True,
                )
                for index in range(10)
            ]
        )
        for index in range(3):
            growth_service = Service.objects.create(
                semantic_id=f"scoped.published-growth.{index}",
                text_ar="خدمة منشورة إضافية",
                text_en="Additional published service",
                is_active=True,
            )
            ServiceQuestion.objects.create(
                semantic_id=f"scoped.published-growth.{index}.question",
                service=growth_service,
                fact=self.fact,
                text_ar="هل؟",
                text_en="Is it?",
                priority=1,
            )
            self._procedure(
                growth_service,
                f"scoped.published-growth.{index}.procedure",
                "Published growth procedure",
            )
            _, draft_version = self._draft_procedure(
                growth_service,
                f"scoped.draft-growth.{index}.procedure",
                "Draft growth procedure",
                selection_value=False,
            )
            draft_item = ChecklistItem.objects.create(
                procedure_version=draft_version,
                semantic_id="draft-growth-item",
                text_ar="عنصر نمو مسودة",
                text_en="Draft growth item",
                classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
                verification_state="current",
            )
            draft_link = EvidenceLink.objects.create(
                checklist_item=draft_item,
                semantic_id="draft-growth-evidence",
                passage="Draft growth passage",
                location="Draft growth section",
                applicability_context="Draft growth context",
                verification_state="current",
                verified_on=date(2026, 8, 1),
                support_status=EvidenceLink.SupportStatus.SUPPORTS,
            )
            source_id = (
                self.evidence_by_service[growth_service.semantic_id]
                .source_links.values_list("source_id", flat=True)
                .first()
            )
            assert source_id is not None
            set_evidence_link_sources(draft_link, (Source.objects.get(pk=source_id),))
            published_link = self.evidence_by_service[growth_service.semantic_id]
            event = record_evidence_reverification(
                anchor_evidence_link=published_link,
                reviewed_evidence_links=(published_link,),
                verification_state="current",
                verified_on=date(2026, 8, 30),
                reverify_on=date(2027, 8, 30),
                rationale="Unrelated published growth history.",
                actor=self.actor,
            )
            from knowledge.evidence_workflow import EvidenceReverificationEvent

            EvidenceReverificationEvent.objects.filter(pk=event.pk).update(
                occurred_at=datetime(2026, 8, 30, tzinfo=UTC)
            )
        after_services, after_rows, after_queries = load()

        self.assertEqual(before_services, (self.requested.semantic_id,))
        self.assertEqual(after_services, before_services)
        self.assertEqual(after_rows, before_rows)
        # One extra query is the approved, necessary workflow-owner integrity read once history
        # exists; unrelated graph DTO materialization remains constant.
        self.assertLessEqual(after_queries - before_queries, 1)

    def test_full_and_scoped_loaders_preserve_unknown_inactive_and_extra_fact_behavior(
        self,
    ) -> None:
        extra = FactDefinition.objects.create(
            key="scoped.extra.fact",
            kind=FactDefinition.Kind.BOOLEAN,
            is_published=True,
        )
        Service.objects.create(
            semantic_id="scoped.inactive",
            text_ar="خدمة غير نشطة",
            text_en="Inactive service",
            is_active=False,
        )
        evaluation_date = date(2026, 9, 1)
        full = load_knowledge_snapshot_as_of(evaluation_date)
        scoped = load_consistent_service_knowledge_snapshot_as_of(
            self.requested.semantic_id, evaluation_date
        )
        for service_id in ("scoped.inactive", "scoped.unknown"):
            facts = {self.fact.key: True, extra.key: True}
            full_result = plan_stateless(
                full, PlanningInput(service_id, facts, "en", evaluation_date)
            )
            scoped_result = plan_stateless(
                load_consistent_service_knowledge_snapshot_as_of(service_id, evaluation_date),
                PlanningInput(service_id, facts, "en", evaluation_date),
            )
            self.assertEqual(scoped_result, full_result)
        self.assertIn(extra.key, full.fact_definitions)
        self.assertEqual(scoped.fact_definitions, full.fact_definitions)

    def test_unrelated_unpublished_fact_rule_matches_full_loader_failure(self) -> None:
        hidden = FactDefinition.objects.create(
            key="scoped.hidden.unpublished",
            kind=FactDefinition.Kind.BOOLEAN,
        )
        ServiceProcedureCandidate.objects.filter(service=self.unrelated).update(
            selection_predicate={"op": "eq", "fact": hidden.key, "value": True}
        )

        with self.assertRaises(KnowledgeSnapshotLoadError) as full_error:
            load_knowledge_snapshot_as_of(date(2026, 9, 1))
        with self.assertRaises(KnowledgeSnapshotLoadError) as scoped_error:
            load_consistent_service_knowledge_snapshot_as_of(
                self.requested.semantic_id, date(2026, 9, 1)
            )
        self.assertEqual(full_error.exception.owner_ids, scoped_error.exception.owner_ids)

    def test_relevant_malformed_rule_matches_full_loader_failure(self) -> None:
        ServiceProcedureCandidate.objects.filter(service=self.requested).update(
            selection_predicate={"op": "not-a-rule"}
        )

        with self.assertRaises(KnowledgeSnapshotLoadError) as full_error:
            load_knowledge_snapshot_as_of(date(2026, 9, 1))
        with self.assertRaises(KnowledgeSnapshotLoadError) as scoped_error:
            load_consistent_service_knowledge_snapshot_as_of(
                self.requested.semantic_id, date(2026, 9, 1)
            )
        self.assertEqual(full_error.exception.owner_ids, scoped_error.exception.owner_ids)

    def test_unrelated_malformed_contradiction_and_derived_definition_fail_closed(self) -> None:
        contradiction = ServiceContradiction.objects.create(
            semantic_id="scoped.unrelated.contradiction",
            service=self.unrelated,
            condition={"op": "exists", "fact": self.fact.key},
        )
        ServiceContradiction.objects.filter(pk=contradiction.pk).update(
            condition={"op": "not-a-rule"}
        )
        with self.assertRaises(KnowledgeSnapshotLoadError) as contradiction_error:
            load_consistent_service_knowledge_snapshot_as_of(
                self.requested.semantic_id, date(2026, 9, 1)
            )
        self.assertEqual(
            contradiction_error.exception.owner_ids,
            ("contradiction:scoped.unrelated.contradiction",),
        )

        derived = FactDefinition.objects.create(
            key="scoped.invalid.derived",
            kind=FactDefinition.Kind.BOOLEAN,
        )
        FactDefinition.objects.filter(pk=derived.pk).update(derived=True, is_published=True)
        with self.assertRaises(KnowledgeSnapshotLoadError) as derived_error:
            load_consistent_service_knowledge_snapshot_as_of(
                self.requested.semantic_id, date(2026, 9, 1)
            )
        self.assertEqual(
            derived_error.exception.owner_ids,
            ("contradiction:scoped.unrelated.contradiction", "fact:scoped.invalid.derived"),
        )
