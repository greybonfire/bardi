from __future__ import annotations

from datetime import date

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from knowledge.admin import (
    AuthorityAdmin,
    ChecklistItemAdmin,
    DocumentTypeAdmin,
    EligibilityBasisAdmin,
    EvidenceLinkAdmin,
    EvidenceOwnerInline,
    EvidenceSourceInline,
    ProcedureVersionAdmin,
    ProcedureVersionAuditEventAdmin,
    SourceAdmin,
    StepAdmin,
    StepEvidenceInline,
    WarningAdmin,
    WarningEvidenceInline,
)
from knowledge.models import (
    Authority,
    ChecklistItem,
    DocumentType,
    EligibilityBasis,
    EvidenceLink,
    EvidenceLinkSource,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    ProcedureVersionAuditEvent,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
    Source,
    Step,
    Warning,
)
from knowledge.publication import publish_procedure_version
from knowledge.services import set_evidence_link_sources


class ProcedureVersionAdminTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="staff", is_staff=True, is_superuser=False
        )
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.user
        service = Service.objects.create(
            semantic_id="admin.service", text_ar="خدمة", text_en="Service"
        )
        procedure = Procedure.objects.create(
            semantic_id="admin.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=service,
        )
        self.draft = ProcedureVersion.objects.create(
            semantic_id="admin.version",
            procedure=procedure,
            applicability={"op": "eq", "fact": "is_student", "value": True},
        )
        self.version_admin = ProcedureVersionAdmin(ProcedureVersion, admin.site)
        self.audit_admin = ProcedureVersionAuditEventAdmin(ProcedureVersionAuditEvent, admin.site)

    def test_lifecycle_fields_are_readonly_for_drafts(self) -> None:
        fields = self.version_admin.get_readonly_fields(self.request, self.draft)
        self.assertTrue(
            {"state", "published_at", "published_by", "withdrawn_at", "withdrawn_by"} <= set(fields)
        )
        self.assertNotIn("text_en", fields)

    def test_every_field_is_readonly_and_deletion_denied_after_lifecycle_transition(self) -> None:
        self.draft.state = ProcedureVersion.State.PUBLISHED
        fields = self.version_admin.get_readonly_fields(self.request, self.draft)
        self.assertEqual(set(fields), {field.name for field in ProcedureVersion._meta.fields})
        self.assertFalse(self.version_admin.has_delete_permission(self.request, self.draft))

    def test_audit_admin_is_history_only(self) -> None:
        self.assertFalse(self.audit_admin.has_add_permission(self.request))
        self.assertFalse(self.audit_admin.has_change_permission(self.request))
        self.assertFalse(self.audit_admin.has_delete_permission(self.request))

    def test_custom_actions_require_explicit_permissions(self) -> None:
        self.assertFalse(self.version_admin.has_publish_procedureversion_permission(self.request))
        self.assertFalse(self.version_admin.has_withdraw_procedureversion_permission(self.request))


class ChecklistAdminTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_superuser(username="checklist-admin")
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.user
        service = Service.objects.create(
            semantic_id="checklist.admin.service", text_ar="خدمة", text_en="Service"
        )
        ServiceQuestion.objects.create(
            semantic_id="checklist.admin.service.question.applicability",
            service=service,
            fact=FactDefinition.objects.get(key="is_student"),
            text_ar="هل ينطبق عليك شرط الخدمة؟",
            text_en="Does the service condition apply to you?",
            priority=100,
        )
        procedure = Procedure.objects.create(
            semantic_id="checklist.admin.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=service,
        )
        predicate = {"op": "eq", "fact": "is_student", "value": True}
        ServiceProcedureCandidate.objects.create(
            service=service, procedure=procedure, selection_predicate=predicate
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="checklist.admin.version",
            procedure=procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability=predicate,
        )
        self.authority = Authority.objects.create(
            semantic_id="checklist.admin.authority", name_ar="جهة", name_en="Authority"
        )
        self.document_type = DocumentType.objects.create(
            semantic_id="checklist.admin.document", name_ar="مستند", name_en="Document"
        )
        self.source = Source.objects.create(
            semantic_id="checklist.admin.source",
            authority=self.authority,
            title="Official source",
            locator="https://example.test/source",
            classification=Source.Classification.OFFICIAL,
            retrieved_on=date(2026, 8, 1),
        )
        self.item = ChecklistItem.objects.create(
            procedure_version=self.version,
            semantic_id="checklist.admin.claim",
            text_ar="أحضر المستند",
            text_en="Bring the document",
            classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
            document_type=self.document_type,
            verification_state="current",
        )
        self.evidence = EvidenceLink.objects.create(
            checklist_item=self.item,
            passage="Passage",
            location="Section",
            applicability_context="Procedure context",
            verification_state="current",
        )
        set_evidence_link_sources(self.evidence, (self.source,))

    def test_staff_can_author_a_draft_claim_and_its_evidence(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("admin:knowledge_checklistitem_add"),
            {
                "procedure_version": self.version.pk,
                "semantic_id": "checklist.admin.authored",
                "text_ar": "مستند إضافي",
                "text_en": "Additional document",
                "classification": ChecklistItem.Classification.PRACTICAL_PREPARATION,
                "document_type": self.document_type.pk,
                "quantity": 1,
                "original_quantity": 1,
                "copy_quantity": 0,
                "display_order": 2,
                "applicability": "{}",
                "scope": ChecklistItem.Scope.PROCEDURE,
                "scope_reference": "",
                "effective_from": "",
                "effective_to": "",
                "verified_on": "",
                "reverify_on": "",
                "verification_state": "current",
                "evidence_links-TOTAL_FORMS": "0",
                "evidence_links-INITIAL_FORMS": "0",
                "evidence_links-MIN_NUM_FORMS": "0",
                "evidence_links-MAX_NUM_FORMS": "1000",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        item = ChecklistItem.objects.get(semantic_id="checklist.admin.authored")

        response = self.client.post(
            reverse("admin:knowledge_evidencelink_add"),
            {
                "checklist_item": item.pk,
                "passage": "Relied-upon passage",
                "location": "Section 2",
                "applicability_context": "Applies to the selected procedure",
                "effective_from": "",
                "effective_to": "",
                "retrieved_on": "",
                "verified_on": "",
                "reverify_on": "",
                "verification_state": "current",
                "support_status": EvidenceLink.SupportStatus.SUPPORTS,
                "source_links-TOTAL_FORMS": "1",
                "source_links-INITIAL_FORMS": "0",
                "source_links-MIN_NUM_FORMS": "0",
                "source_links-MAX_NUM_FORMS": "1000",
                "source_links-0-source": self.source.pk,
                "source_links-0-position": 0,
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        authored = EvidenceLink.objects.get(checklist_item=item)
        self.assertEqual(tuple(authored.sources.all()), (self.source,))

    def test_draft_evidence_aggregate_is_editable(self) -> None:
        item_admin = ChecklistItemAdmin(ChecklistItem, admin.site)
        evidence_admin = EvidenceLinkAdmin(EvidenceLink, admin.site)
        owner_inline = EvidenceOwnerInline(ChecklistItem, admin.site)
        source_inline = EvidenceSourceInline(EvidenceLink, admin.site)

        self.assertEqual(item_admin.get_readonly_fields(self.request, self.item), ())
        self.assertEqual(evidence_admin.get_readonly_fields(self.request, self.evidence), ())
        self.assertTrue(owner_inline.has_add_permission(self.request, self.item))
        self.assertTrue(owner_inline.has_change_permission(self.request, self.item))
        self.assertTrue(source_inline.has_add_permission(self.request, self.evidence))
        self.assertTrue(source_inline.has_change_permission(self.request, self.evidence))

    def test_published_claims_and_reused_provenance_are_readonly(self) -> None:
        publish_procedure_version(self.version.pk, actor=self.user)
        self.item.refresh_from_db()
        self.evidence.refresh_from_db()
        item_admin = ChecklistItemAdmin(ChecklistItem, admin.site)
        evidence_admin = EvidenceLinkAdmin(EvidenceLink, admin.site)
        owner_inline = EvidenceOwnerInline(ChecklistItem, admin.site)
        source_inline = EvidenceSourceInline(EvidenceLink, admin.site)

        self.assertEqual(
            set(item_admin.get_readonly_fields(self.request, self.item)),
            {field.name for field in ChecklistItem._meta.fields},
        )
        self.assertEqual(
            set(evidence_admin.get_readonly_fields(self.request, self.evidence)),
            {field.name for field in EvidenceLink._meta.fields},
        )
        self.assertFalse(item_admin.has_delete_permission(self.request, self.item))
        self.assertFalse(evidence_admin.has_delete_permission(self.request, self.evidence))
        self.assertFalse(owner_inline.has_change_permission(self.request, self.item))
        self.assertFalse(source_inline.has_change_permission(self.request, self.evidence))

        authority_admin = AuthorityAdmin(Authority, admin.site)
        self.assertEqual(
            set(authority_admin.get_readonly_fields(self.request, self.authority)),
            {field.name for field in Authority._meta.fields},
        )
        self.assertFalse(authority_admin.has_delete_permission(self.request, self.authority))
        document_type_admin = DocumentTypeAdmin(DocumentType, admin.site)
        self.assertEqual(
            set(document_type_admin.get_readonly_fields(self.request, self.document_type)),
            {field.name for field in DocumentType._meta.fields},
        )
        self.assertFalse(
            document_type_admin.has_delete_permission(self.request, self.document_type)
        )
        source_admin = SourceAdmin(Source, admin.site)
        self.assertEqual(
            set(source_admin.get_readonly_fields(self.request, self.source)),
            {field.name for field in Source._meta.fields},
        )
        self.assertFalse(source_admin.has_delete_permission(self.request, self.source))
        self.assertEqual(EvidenceLinkSource.objects.filter(evidence_link=self.evidence).count(), 1)


class GuidanceAdminTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_superuser(username="guidance-admin")
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.user
        basis_fact, _ = FactDefinition.objects.get_or_create(
            key="guidance_admin_basis",
            defaults={"kind": "boolean", "enum_values": [], "is_published": True},
        )
        service = Service.objects.create(
            semantic_id="guidance.admin.service", text_ar="خدمة", text_en="Service"
        )
        procedure = Procedure.objects.create(
            semantic_id="guidance.admin.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=service,
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="guidance.admin.version",
            procedure=procedure,
            text_ar="نسخة",
            text_en="Version",
        )
        self.basis = EligibilityBasis.objects.create(
            procedure_version=self.version,
            semantic_id="basis.admin",
            text_ar="أساس",
            text_en="Basis",
            qualification={"op": "eq", "fact": basis_fact.key, "value": True},
        )
        self.authority = Authority.objects.create(
            semantic_id="guidance.admin.authority", name_ar="جهة", name_en="Authority"
        )
        self.source = Source.objects.create(
            semantic_id="guidance.admin.source",
            authority=self.authority,
            title="Official source",
            locator="https://example.test/guidance",
            classification=Source.Classification.OFFICIAL,
            retrieved_on=date(2026, 8, 1),
        )

    def test_staff_can_author_draft_steps_and_product_warnings(self) -> None:
        self.client.force_login(self.user)
        step_response = self.client.post(
            reverse("admin:knowledge_step_add"),
            {
                "procedure_version": self.version.pk,
                "semantic_id": "guidance.admin.step",
                "text_ar": "قدّم الطلب",
                "text_en": "Submit the application",
                "phase": "submit",
                "phase_order": 10,
                "slot": 20,
                "applicability": "{}",
                "scope": Step.Scope.ELIGIBILITY_BASIS,
                "eligibility_basis": self.basis.pk,
                "effective_from": "",
                "effective_to": "",
                "verified_on": "",
                "reverify_on": "",
                "verification_state": "current",
                "evidence_links-TOTAL_FORMS": "0",
                "evidence_links-INITIAL_FORMS": "0",
                "evidence_links-MIN_NUM_FORMS": "0",
                "evidence_links-MAX_NUM_FORMS": "1000",
                "_save": "Save",
            },
        )
        self.assertEqual(step_response.status_code, 302)
        step = Step.objects.get(semantic_id="guidance.admin.step")
        evidence_response = self.client.post(
            reverse("admin:knowledge_evidencelink_add"),
            {
                "checklist_item": "",
                "step": step.pk,
                "warning": "",
                "passage": "Relied-upon passage",
                "location": "Section 1",
                "applicability_context": "Applies to this procedure",
                "effective_from": "",
                "effective_to": "",
                "retrieved_on": "",
                "verified_on": "",
                "reverify_on": "",
                "verification_state": "current",
                "support_status": EvidenceLink.SupportStatus.SUPPORTS,
                "source_links-TOTAL_FORMS": "1",
                "source_links-INITIAL_FORMS": "0",
                "source_links-MIN_NUM_FORMS": "0",
                "source_links-MAX_NUM_FORMS": "1000",
                "source_links-0-source": self.source.pk,
                "source_links-0-position": 0,
                "_save": "Save",
            },
        )
        self.assertEqual(evidence_response.status_code, 302)
        self.assertEqual(tuple(EvidenceLink.objects.get(step=step).sources.all()), (self.source,))

        warning_response = self.client.post(
            reverse("admin:knowledge_warning_add"),
            {
                "procedure_version": self.version.pk,
                "semantic_id": "guidance.admin.warning",
                "text_ar": "أعد إنشاء الخطة",
                "text_en": "Regenerate the plan",
                "severity": Warning.Severity.IMPORTANT,
                "kind": Warning.Kind.PRODUCT,
                "role": Warning.Role.REGENERATION,
                "display_order": 10,
                "applicability": "{}",
                "effective_from": "",
                "effective_to": "",
                "verified_on": "",
                "reverify_on": "",
                "verification_state": "current",
                "evidence_links-TOTAL_FORMS": "0",
                "evidence_links-INITIAL_FORMS": "0",
                "evidence_links-MIN_NUM_FORMS": "0",
                "evidence_links-MAX_NUM_FORMS": "1000",
                "_save": "Save",
            },
        )
        self.assertEqual(warning_response.status_code, 302)
        self.assertTrue(Warning.objects.filter(semantic_id="guidance.admin.warning").exists())

    def test_guidance_admin_becomes_readonly_with_its_version(self) -> None:
        step = Step.objects.create(
            procedure_version=self.version,
            semantic_id="guidance.admin.step",
            text_ar="قدّم الطلب",
            text_en="Submit the application",
            phase="submit",
            verification_state="needs_reverification",
        )
        warning = Warning.objects.create(
            procedure_version=self.version,
            semantic_id="guidance.admin.warning",
            text_ar="تنبيه",
            text_en="Warning",
            severity=Warning.Severity.IMPORTANT,
            kind=Warning.Kind.PRODUCT,
            role=Warning.Role.REGENERATION,
            verification_state="current",
        )
        self.version.state = ProcedureVersion.State.PUBLISHED

        step_admin = StepAdmin(Step, admin.site)
        warning_admin = WarningAdmin(Warning, admin.site)
        basis_admin = EligibilityBasisAdmin(EligibilityBasis, admin.site)
        step_inline = StepEvidenceInline(Step, admin.site)
        warning_inline = WarningEvidenceInline(Warning, admin.site)
        self.assertEqual(
            set(step_admin.get_readonly_fields(self.request, step)),
            {field.name for field in Step._meta.fields},
        )
        self.assertEqual(
            set(warning_admin.get_readonly_fields(self.request, warning)),
            {field.name for field in Warning._meta.fields},
        )
        self.assertFalse(step_admin.has_delete_permission(self.request, step))
        self.assertFalse(warning_admin.has_delete_permission(self.request, warning))
        self.assertFalse(basis_admin.has_delete_permission(self.request, self.basis))
        self.assertFalse(step_inline.has_add_permission(self.request, step))
        self.assertFalse(warning_inline.has_add_permission(self.request, warning))
