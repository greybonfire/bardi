from __future__ import annotations

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from knowledge.admin import ProcedureVersionAdmin, ProcedureVersionAuditEventAdmin
from knowledge.models import Procedure, ProcedureVersion, ProcedureVersionAuditEvent, Service


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
