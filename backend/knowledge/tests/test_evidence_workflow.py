from __future__ import annotations

import json
from datetime import date

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TransactionTestCase

from knowledge.domain import load_knowledge_snapshot
from knowledge.evidence_workflow import (
    EvidenceDiscrepancy,
    EvidenceReverificationEvent,
    open_evidence_discrepancy,
    record_evidence_reverification,
    resolve_evidence_discrepancy,
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
    Source,
    Step,
    Warning,
)
from knowledge.publication import PublicationRejected, publish_procedure_version
from knowledge.services import set_evidence_link_sources

TODAY = date(2026, 9, 5)
REVERIFY_DUE = date(2026, 9, 10)
LATER = date(2026, 10, 1)
RENEWED_DUE = date(2026, 12, 1)


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

    def post(self, evaluation_date: date = TODAY) -> dict[str, object]:
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
        return response.json()

    def test_open_discrepancy_is_local_and_internal_rationale_never_leaks(self) -> None:
        self.publish()
        secret = "INTERNAL DISCREPANCY RATIONALE"
        discrepancy = open_evidence_discrepancy(
            anchor_evidence_link=self.checklist_evidence,
            evidence_links=(self.checklist_evidence,),
            rationale=secret,
            actor=self.actor,
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

    def test_resolved_discrepancy_restores_shared_current_trust(self) -> None:
        self.publish()
        discrepancy = open_evidence_discrepancy(
            anchor_evidence_link=self.checklist_evidence,
            evidence_links=(self.checklist_evidence,),
            rationale="Official and field observations conflicted.",
            actor=self.actor,
        )
        resolved = resolve_evidence_discrepancy(
            discrepancy.pk,
            outcome_state="current",
            resolution="Official source confirmed the existing wording.",
            actor=self.actor,
        )

        body = self.post()

        self.assertEqual(body["inconclusive_sections"], [])
        self.assertEqual(
            [item["id"] for item in body["checklist_items"]],
            [self.checklist.semantic_id],
        )
        self.assertEqual(resolved.status, EvidenceDiscrepancy.Status.RESOLVED)
        self.assertEqual(resolved.outcome_state, "current")
        self.assertIsNotNone(resolved.resolved_at)
        self.assertEqual(resolved.resolved_by, self.actor)
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

        event = record_evidence_reverification(
            anchor_evidence_link=self.checklist_evidence,
            reviewed_evidence_links=(self.checklist_evidence,),
            verification_state="current",
            verified_on=TODAY,
            reverify_on=RENEWED_DUE,
            rationale="Rechecked the same requirement against the official source.",
            actor=self.actor,
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
        snapshot = load_knowledge_snapshot()
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

        historical = self.post(date(2026, 9, 4))
        self.assertEqual(historical["checklist_items"], [])
        self.assertEqual(historical["inconclusive_sections"], ["checklist_items"])

    def test_meaning_change_requires_distinct_draft_successor(self) -> None:
        self.publish()
        with self.assertRaises(ValidationError):
            record_evidence_reverification(
                anchor_evidence_link=self.checklist_evidence,
                reviewed_evidence_links=(self.checklist_evidence,),
                verification_state="disputed",
                verified_on=TODAY,
                reverify_on=None,
                rationale="The source now appears to require different public wording.",
                actor=self.actor,
                meaning_changed=True,
            )

        successor = ProcedureVersion.objects.create(
            semantic_id="workflow.procedure.v2",
            procedure=self.procedure,
            text_ar="نسخة لاحقة",
            text_en="Successor version",
            applicability=self.rule,
        )
        event = record_evidence_reverification(
            anchor_evidence_link=self.checklist_evidence,
            reviewed_evidence_links=(self.checklist_evidence,),
            verification_state="disputed",
            verified_on=TODAY,
            reverify_on=None,
            rationale="Public meaning changed; edit the successor instead.",
            actor=self.actor,
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

    def test_fee_discrepancy_hides_amount_without_erasing_reliable_sections(self) -> None:
        self.publish()
        secret = "PRIVATE FEE CONFLICT"
        open_evidence_discrepancy(
            anchor_evidence_link=self.fee_evidence,
            evidence_links=(self.fee_evidence,),
            rationale=secret,
            actor=self.actor,
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
        open_evidence_discrepancy(
            anchor_evidence_link=self.checklist_evidence,
            evidence_links=(self.checklist_evidence,),
            rationale="Resolve before publishing.",
            actor=self.actor,
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
            open_evidence_discrepancy(
                anchor_evidence_link=self.checklist_evidence,
                evidence_links=(self.checklist_evidence, self.step_evidence),
                rationale="These are different subjects.",
                actor=self.actor,
            )

        self.publish()
        event = record_evidence_reverification(
            anchor_evidence_link=self.step_evidence,
            reviewed_evidence_links=(self.step_evidence,),
            verification_state="current",
            verified_on=TODAY,
            reverify_on=RENEWED_DUE,
            rationale="Step wording remains accurate.",
            actor=self.actor,
        )
        self.assertIn(EvidenceDiscrepancy, admin.site._registry)
        self.assertIn(EvidenceReverificationEvent, admin.site._registry)
        request = RequestFactory().get("/admin/")
        discrepancy_admin = admin.site._registry[EvidenceDiscrepancy]
        event_admin = admin.site._registry[EvidenceReverificationEvent]
        self.assertFalse(discrepancy_admin.has_delete_permission(request))
        self.assertFalse(event_admin.has_add_permission(request))
        self.assertFalse(event_admin.has_delete_permission(request, event))
