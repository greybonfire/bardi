from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any, cast
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.test import RequestFactory, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from planning import Predicate, PreparedFacts
from planning.fees import select_fees
from planning.trust import VerificationState

from knowledge.domain import load_knowledge_snapshot
from knowledge.evidence_workflow import (
    EvidenceDiscrepancy,
    EvidenceReverificationEvent,
    _lock_workflow_evidence,
    _overlay_item,
    _TrustOverlay,
    open_evidence_discrepancy,
    record_evidence_reverification,
    resolve_evidence_discrepancy,
)
from knowledge.evidence_workflow_temporal import (
    EvidenceDiscrepancyTransition,
    _workflow_overlays_as_of,
    load_knowledge_snapshot_as_of,
)
from knowledge.fees import Fee
from knowledge.models import (
    Authority,
    ChecklistItem,
    DocumentType,
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
    Source,
    Step,
    Warning,
)
from knowledge.publication import PublicationRejected, publish_procedure_version
from knowledge.services import set_evidence_link_sources

BEFORE_WORKFLOW = date(2026, 9, 4)
TODAY = date(2026, 9, 5)
DURING_DISCREPANCY = date(2026, 9, 6)
AFTER_RESOLUTION = date(2026, 9, 9)
REVERIFY_DUE = date(2026, 9, 10)
LATER = date(2026, 10, 1)
RENEWED_DUE = date(2026, 12, 1)
OPENED_AT = datetime(2026, 9, 5, 9, tzinfo=UTC)
RESOLVED_AT = datetime(2026, 9, 8, 9, tzinfo=UTC)
REVIEWED_AT = datetime(2026, 9, 5, 10, tzinfo=UTC)


class EvidenceWorkflowTests(TransactionTestCase):
    def setUp(self) -> None:
        self.fact = FactDefinition.objects.create(
            key="workflow_fact",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        self.rule = {"op": "eq", "fact": self.fact.key, "value": True}
        self.actor = get_user_model().objects.create_user(username="workflow-reviewer")
        self.service = Service.objects.create(
            semantic_id="workflow.service",
            text_ar="خدمة",
            text_en="Service",
            is_active=True,
        )
        ServiceQuestion.objects.create(
            semantic_id="workflow.service.question.applicability",
            service=self.service,
            fact=self.fact,
            text_ar="هل ينطبق عليك شرط الخدمة؟",
            text_en="Does the service condition apply to you?",
            priority=100,
        )
        self.procedure = Procedure.objects.create(
            semantic_id="workflow.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=self.service,
        )
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate=self.rule,
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="workflow.procedure.v1",
            procedure=self.procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability=self.rule,
        )
        self.authority = Authority.objects.create(
            semantic_id="workflow.authority",
            name_ar="جهة",
            name_en="Authority",
        )
        self.source = Source.objects.create(
            semantic_id="workflow.source",
            authority=self.authority,
            title="Official workflow source",
            locator="https://example.test/workflow",
            classification=Source.Classification.OFFICIAL,
            retrieved_on=date(2026, 9, 1),
        )
        self.document_type = DocumentType.objects.create(
            semantic_id="workflow.document",
            name_ar="مستند",
            name_en="Document",
        )
        self.checklist = ChecklistItem.objects.create(
            procedure_version=self.version,
            semantic_id="workflow.checklist",
            text_ar="أحضر المستند",
            text_en="Bring the document",
            classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
            document_type=self.document_type,
            quantity=1,
            display_order=1,
            verification_state="current",
            verified_on=date(2026, 9, 1),
            reverify_on=REVERIFY_DUE,
        )
        self.step = Step.objects.create(
            procedure_version=self.version,
            semantic_id="workflow.step",
            text_ar="قدّم الطلب",
            text_en="Submit the application",
            phase="submit",
            phase_order=1,
            slot=1,
            verification_state="current",
            verified_on=date(2026, 9, 1),
        )
        self.fee = Fee.objects.create(
            procedure_version=self.version,
            semantic_id="workflow.fee",
            text_ar="رسم الخدمة",
            text_en="Service fee",
            value_state=Fee.ValueState.KNOWN,
            amount=100,
            currency="EGP",
            fee_type="service_fee",
            display_order=1,
            verification_state="current",
            verified_on=date(2026, 9, 1),
        )
        Warning.objects.create(
            procedure_version=self.version,
            semantic_id="workflow.regeneration",
            text_ar="أعد إنشاء الخطة قبل التنفيذ",
            text_en="Regenerate the plan before acting",
            severity=Warning.Severity.IMPORTANT,
            kind=Warning.Kind.PRODUCT,
            role=Warning.Role.REGENERATION,
            display_order=1,
            verification_state="current",
        )
        self.checklist_evidence = self.evidence(
            "checklist_item",
            self.checklist,
            reverify_on=REVERIFY_DUE,
        )
        self.step_evidence = self.evidence("step", self.step)
        self.fee_evidence = self.evidence("fee", self.fee)

    def evidence(
        self,
        owner_field: str,
        owner: object,
        *,
        reverify_on: date | None = None,
    ) -> EvidenceLink:
        link = EvidenceLink.objects.create(
            **{owner_field: owner},
            passage="Relied-upon passage",
            location="Section 1",
            applicability_context="Applies to this procedure",
            verification_state="current",
            verified_on=date(2026, 9, 1),
            reverify_on=reverify_on,
            support_status=EvidenceLink.SupportStatus.SUPPORTS,
        )
        set_evidence_link_sources(link, (self.source,))
        return link

    def publish(self) -> None:
        publish_procedure_version(self.version.pk, actor=self.actor)
        self.version.refresh_from_db()
        self.assertEqual(self.version.state, ProcedureVersion.State.PUBLISHED)

    def post(self, evaluation_date: date = TODAY) -> dict[str, Any]:
        response = self.client.post(
            "/v1/planning",
            data=json.dumps(
                {
                    "service_id": self.service.semantic_id,
                    "facts": {self.fact.key: True},
                    "locale": "en",
                    "evaluation_context": {"evaluation_date": evaluation_date.isoformat()},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return cast(dict[str, Any], response.json())

    def open_discrepancy(
        self,
        *,
        anchor_evidence_link: EvidenceLink,
        evidence_links: tuple[EvidenceLink, ...],
        rationale: str,
        outcome_state: VerificationState = "disputed",
        occurred_at: datetime = OPENED_AT,
    ) -> EvidenceDiscrepancy:
        with patch("django.utils.timezone.now", return_value=occurred_at):
            return open_evidence_discrepancy(
                anchor_evidence_link=anchor_evidence_link,
                evidence_links=evidence_links,
                rationale=rationale,
                actor=self.actor,
                outcome_state=outcome_state,
            )

    def resolve_discrepancy(
        self,
        discrepancy: EvidenceDiscrepancy,
        *,
        outcome_state: VerificationState = "current",
        resolution: str = "Confirmed existing public meaning.",
        occurred_at: datetime = RESOLVED_AT,
    ) -> EvidenceDiscrepancy:
        with patch("django.utils.timezone.now", return_value=occurred_at):
            return resolve_evidence_discrepancy(
                discrepancy.pk,
                outcome_state=outcome_state,
                resolution=resolution,
                actor=self.actor,
            )

    def record_review(
        self,
        *,
        anchor_evidence_link: EvidenceLink,
        reviewed_evidence_links: tuple[EvidenceLink, ...],
        verification_state: VerificationState = "current",
        verified_on: date = TODAY,
        reverify_on: date | None = RENEWED_DUE,
        rationale: str = "Rechecked the same public meaning.",
        meaning_changed: bool = False,
        successor_version: ProcedureVersion | None = None,
        occurred_at: datetime = REVIEWED_AT,
    ) -> EvidenceReverificationEvent:
        with patch("django.utils.timezone.now", return_value=occurred_at):
            return record_evidence_reverification(
                anchor_evidence_link=anchor_evidence_link,
                reviewed_evidence_links=reviewed_evidence_links,
                verification_state=verification_state,
                verified_on=verified_on,
                reverify_on=reverify_on,
                rationale=rationale,
                actor=self.actor,
                meaning_changed=meaning_changed,
                successor_version=successor_version,
            )

    def test_open_discrepancy_is_local_and_internal_rationale_never_leaks(self) -> None:
        self.publish()
        secret = "INTERNAL DISCREPANCY RATIONALE"
        discrepancy = self.open_discrepancy(
            anchor_evidence_link=self.checklist_evidence,
            evidence_links=(self.checklist_evidence,),
            rationale=secret,
            outcome_state="disputed",
        )

        body = self.post()

        self.assertEqual(body["type"], "plan")
        self.assertEqual(body["checklist_items"], [])
        self.assertEqual(body["inconclusive_sections"], ["checklist_items"])
        self.assertEqual([item["id"] for item in body["steps"]], [self.step.semantic_id])
        self.assertEqual(body["fees"][0]["value_state"], "known")
        self.assertNotIn(secret, json.dumps(body))
        self.assertEqual(discrepancy.outcome_state, "disputed")
        self.assertEqual(
            tuple(discrepancy.evidence_links.values_list("pk", flat=True)),
            (self.checklist_evidence.pk,),
        )

    def test_discrepancy_history_is_applied_only_during_its_established_interval(self) -> None:
        self.publish()
        discrepancy = self.open_discrepancy(
            anchor_evidence_link=self.checklist_evidence,
            evidence_links=(self.checklist_evidence,),
            rationale="Official and field observations conflicted.",
        )
        with self.assertRaises(ValidationError):
            discrepancy.outcome_state = "unknown"
            discrepancy.save()
        discrepancy.refresh_from_db()
        resolved = self.resolve_discrepancy(
            discrepancy,
            outcome_state="current",
            resolution="Official source confirmed the existing wording.",
        )

        before = self.post(BEFORE_WORKFLOW)
        during = self.post(DURING_DISCREPANCY)
        after = self.post(AFTER_RESOLUTION)

        self.assertEqual(
            [item["id"] for item in before["checklist_items"]],
            [self.checklist.semantic_id],
        )
        self.assertEqual(before["inconclusive_sections"], [])
        self.assertEqual(during["checklist_items"], [])
        self.assertEqual(during["inconclusive_sections"], ["checklist_items"])
        self.assertEqual(
            [item["id"] for item in after["checklist_items"]],
            [self.checklist.semantic_id],
        )
        self.assertEqual(after["inconclusive_sections"], [])
        self.assertEqual(resolved.status, EvidenceDiscrepancy.Status.RESOLVED)
        self.assertEqual(resolved.outcome_state, "current")
        self.assertIsNotNone(resolved.resolved_at)
        self.assertEqual(resolved.resolved_by, self.actor)
        self.assertEqual(
            list(
                EvidenceDiscrepancyTransition.objects.filter(discrepancy=resolved).values_list(
                    "event_type", "verification_state"
                )
            ),
            [("opened", "disputed"), ("resolved", "current")],
        )
        with self.assertRaises(ValidationError):
            resolved.delete()

    def test_reverification_overlays_metadata_without_rewriting_published_rows(self) -> None:
        self.publish()
        before_item = ChecklistItem.objects.values(
            "verification_state", "verified_on", "reverify_on", "text_en"
        ).get(pk=self.checklist.pk)
        before_evidence = EvidenceLink.objects.values(
            "verification_state", "verified_on", "reverify_on", "passage"
        ).get(pk=self.checklist_evidence.pk)
        self.assertEqual(self.post(LATER)["inconclusive_sections"], ["checklist_items"])
        historical_before_review = self.post(BEFORE_WORKFLOW)
        self.assertEqual(
            [item["id"] for item in historical_before_review["checklist_items"]],
            [self.checklist.semantic_id],
        )

        event = self.record_review(
            anchor_evidence_link=self.checklist_evidence,
            reviewed_evidence_links=(self.checklist_evidence,),
            verification_state="current",
            verified_on=TODAY,
            reverify_on=RENEWED_DUE,
            rationale="Rechecked the same requirement against the official source.",
        )

        self.assertEqual(
            ChecklistItem.objects.values(
                "verification_state", "verified_on", "reverify_on", "text_en"
            ).get(pk=self.checklist.pk),
            before_item,
        )
        self.assertEqual(
            EvidenceLink.objects.values(
                "verification_state", "verified_on", "reverify_on", "passage"
            ).get(pk=self.checklist_evidence.pk),
            before_evidence,
        )
        current = self.post(LATER)
        self.assertEqual(current["inconclusive_sections"], [])
        self.assertEqual(
            [item["id"] for item in current["checklist_items"]],
            [self.checklist.semantic_id],
        )
        snapshot = load_knowledge_snapshot_as_of(LATER)
        loaded_version = next(
            item
            for item in snapshot.procedure_versions
            if item.semantic_id == self.version.semantic_id
        )
        loaded_item = loaded_version.checklist_items[0]
        self.assertEqual(loaded_item.verification_state, "current")
        self.assertEqual(loaded_item.verified_on, TODAY)
        self.assertEqual(loaded_item.reverify_on, RENEWED_DUE)
        self.assertEqual(loaded_item.evidence_links[0].verified_on, TODAY)
        self.assertEqual(loaded_item.evidence_links[0].reverify_on, RENEWED_DUE)
        self.assertEqual(event.verification_state, "current")

        historical = self.post(BEFORE_WORKFLOW)
        self.assertEqual(
            [item["id"] for item in historical["checklist_items"]],
            [self.checklist.semantic_id],
        )
        self.assertEqual(historical["inconclusive_sections"], [])

    def test_meaning_change_requires_distinct_draft_successor(self) -> None:
        self.publish()
        with self.assertRaises(ValidationError):
            self.record_review(
                anchor_evidence_link=self.checklist_evidence,
                reviewed_evidence_links=(self.checklist_evidence,),
                verification_state="disputed",
                verified_on=TODAY,
                reverify_on=None,
                rationale="The source now appears to require different public wording.",
                meaning_changed=True,
            )

        successor = ProcedureVersion.objects.create(
            semantic_id="workflow.procedure.v2",
            procedure=self.procedure,
            text_ar="نسخة لاحقة",
            text_en="Successor version",
            applicability=self.rule,
        )
        event = self.record_review(
            anchor_evidence_link=self.checklist_evidence,
            reviewed_evidence_links=(self.checklist_evidence,),
            verification_state="disputed",
            verified_on=TODAY,
            reverify_on=None,
            rationale="Public meaning changed; edit the successor instead.",
            meaning_changed=True,
            successor_version=successor,
        )

        body = self.post()
        self.assertEqual(body["inconclusive_sections"], [])
        self.assertEqual(
            [item["id"] for item in body["checklist_items"]],
            [self.checklist.semantic_id],
        )
        successor.refresh_from_db()
        self.assertEqual(successor.state, ProcedureVersion.State.DRAFT)
        self.assertTrue(event.meaning_changed)
        self.assertEqual(event.successor_version, successor)
        event.verification_state = "stale"
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()

    def test_current_overlay_never_exposes_authored_unverified_researched_amount(self) -> None:
        self.publish()
        snapshot = load_knowledge_snapshot()
        version = next(
            item
            for item in snapshot.procedure_versions
            if item.semantic_id == self.version.semantic_id
        )
        authored_unverified = replace(
            version.fees[0],
            value_state="unverified",
            amount=900,
            verification_state="needs_reverification",
            applicability=Predicate("eq", "overlay_fee_applies", True),
        )
        current = _overlay_item(
            authored_unverified,
            _TrustOverlay(state="current", owner_verified_on=TODAY),
        )
        overlaid_version = replace(version, fees=(current,))

        unknown = select_fees(
            overlaid_version,
            PreparedFacts({}, frozenset(), {}),
            TODAY,
        )
        self.assertEqual(unknown.missing_facts, frozenset({"overlay_fee_applies"}))
        self.assertFalse(unknown.items)

        selected = select_fees(
            overlaid_version,
            PreparedFacts(
                {"overlay_fee_applies": True},
                frozenset({"overlay_fee_applies"}),
                {},
            ),
            TODAY,
        )
        fee = selected.items[0]
        self.assertEqual(fee.value_state, "unverified")
        self.assertIsNone(fee.amount)
        self.assertIsNone(fee.minimum_amount)
        self.assertIsNone(fee.maximum_amount)
        self.assertTrue(fee.current_value_unknown)
        self.assertEqual(fee.sources[0].id, self.source.semantic_id)
        self.assertEqual(fee.freshness.state, "current")

    def test_fee_discrepancy_hides_amount_without_erasing_reliable_sections(self) -> None:
        self.publish()
        secret = "PRIVATE FEE CONFLICT"
        self.open_discrepancy(
            anchor_evidence_link=self.fee_evidence,
            evidence_links=(self.fee_evidence,),
            rationale=secret,
            outcome_state="needs_reverification",
        )

        body = self.post()

        self.assertEqual(body["type"], "plan")
        self.assertEqual(body["inconclusive_sections"], [])
        self.assertEqual(
            [item["id"] for item in body["checklist_items"]],
            [self.checklist.semantic_id],
        )
        self.assertEqual([item["id"] for item in body["steps"]], [self.step.semantic_id])
        fee = body["fees"][0]
        self.assertEqual(fee["value_state"], "unverified")
        self.assertIsNone(fee["amount"])
        self.assertTrue(fee["current_value_unknown"])
        self.assertNotIn(secret, json.dumps(body))

    def test_publication_rejects_open_discrepancy_on_draft_material(self) -> None:
        self.open_discrepancy(
            anchor_evidence_link=self.checklist_evidence,
            evidence_links=(self.checklist_evidence,),
            rationale="Resolve before publishing.",
        )

        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.actor)

        self.assertIn(
            "open_evidence_discrepancy",
            {diagnostic.code for diagnostic in caught.exception.diagnostics},
        )
        self.version.refresh_from_db()
        self.assertEqual(self.version.state, ProcedureVersion.State.DRAFT)

    def test_workflow_rejects_cross_subject_evidence_and_admin_history(self) -> None:
        with self.assertRaises(ValidationError):
            self.open_discrepancy(
                anchor_evidence_link=self.checklist_evidence,
                evidence_links=(self.checklist_evidence, self.step_evidence),
                rationale="These are different subjects.",
            )

        self.publish()
        event = self.record_review(
            anchor_evidence_link=self.step_evidence,
            reviewed_evidence_links=(self.step_evidence,),
            verification_state="current",
            verified_on=TODAY,
            reverify_on=RENEWED_DUE,
            rationale="Step wording remains accurate.",
        )
        self.assertIn(EvidenceDiscrepancy, admin.site._registry)
        self.assertIn(EvidenceReverificationEvent, admin.site._registry)
        request = RequestFactory().get("/admin/")
        discrepancy_admin = admin.site._registry[EvidenceDiscrepancy]
        event_admin = admin.site._registry[EvidenceReverificationEvent]
        self.assertFalse(discrepancy_admin.has_delete_permission(request))
        self.assertFalse(event_admin.has_add_permission(request))
        self.assertFalse(event_admin.has_delete_permission(request, event))

    def test_open_discrepancy_survives_later_current_review(self) -> None:
        self.open_discrepancy(
            anchor_evidence_link=self.checklist_evidence,
            evidence_links=(self.checklist_evidence,),
            rationale="Keep discrepancy open while evidence is rechecked.",
            outcome_state="disputed",
            occurred_at=OPENED_AT,
        )
        reviewed_on = date(2026, 9, 6)
        self.record_review(
            anchor_evidence_link=self.checklist_evidence,
            reviewed_evidence_links=(self.checklist_evidence,),
            verification_state="current",
            verified_on=reviewed_on,
            reverify_on=RENEWED_DUE,
            occurred_at=datetime(2026, 9, 6, 10, tzinfo=UTC),
        )

        owner_key = ("checklist", self.version.semantic_id, self.checklist.semantic_id)
        overlay = _workflow_overlays_as_of(date(2026, 9, 7))[owner_key]

        self.assertEqual(overlay.state, "disputed")
        self.assertEqual(overlay.evidence_state, "current")
        self.assertEqual(overlay.evidence_verified_on, reviewed_on)

    def test_resolving_one_discrepancy_preserves_another_and_historical_open_state(self) -> None:
        first = self.open_discrepancy(
            anchor_evidence_link=self.checklist_evidence,
            evidence_links=(self.checklist_evidence,),
            rationale="First discrepancy",
            outcome_state="needs_reverification",
            occurred_at=OPENED_AT,
        )
        second = self.open_discrepancy(
            anchor_evidence_link=self.checklist_evidence,
            evidence_links=(self.checklist_evidence,),
            rationale="Second discrepancy",
            outcome_state="disputed",
            occurred_at=datetime(2026, 9, 6, 9, tzinfo=UTC),
        )
        owner_key = ("checklist", self.version.semantic_id, self.checklist.semantic_id)

        both_open = _workflow_overlays_as_of(date(2026, 9, 6))[owner_key]
        self.assertEqual(both_open.state, "disputed")

        self.resolve_discrepancy(
            second,
            outcome_state="current",
            occurred_at=datetime(2026, 9, 7, 9, tzinfo=UTC),
        )
        one_open = _workflow_overlays_as_of(date(2026, 9, 7))[owner_key]
        self.assertEqual(one_open.state, "needs_reverification")

        historical = _workflow_overlays_as_of(date(2026, 9, 6))[owner_key]
        self.assertEqual(historical.state, "disputed")

        self.resolve_discrepancy(
            first,
            outcome_state="unknown",
            occurred_at=datetime(2026, 9, 8, 9, tzinfo=UTC),
        )
        fully_resolved = _workflow_overlays_as_of(date(2026, 9, 8))[owner_key]
        self.assertEqual(fully_resolved.state, "unknown")

    def test_workflow_lock_helper_locks_all_versions_before_any_evidence(self) -> None:
        successor = ProcedureVersion.objects.create(
            semantic_id="workflow.procedure.v2.lock-order",
            procedure=self.procedure,
            text_ar="نسخة لاحقة",
            text_en="Successor",
            applicability=self.rule,
        )

        with transaction.atomic():
            with CaptureQueriesContext(connection) as queries:
                _lock_workflow_evidence(
                    {self.checklist_evidence.pk},
                    successor_version_id=successor.pk,
                )

        locking_sql = [query["sql"] for query in queries if "FOR UPDATE" in query["sql"].upper()]
        version_lock_positions = [
            index for index, sql in enumerate(locking_sql) if "knowledge_procedureversion" in sql
        ]
        evidence_lock_positions = [
            index for index, sql in enumerate(locking_sql) if "knowledge_evidencelink" in sql
        ]
        self.assertTrue(version_lock_positions, locking_sql)
        self.assertTrue(evidence_lock_positions, locking_sql)
        self.assertLess(max(version_lock_positions), min(evidence_lock_positions), locking_sql)