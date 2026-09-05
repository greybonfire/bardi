from __future__ import annotations

from datetime import date
from typing import Any

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from knowledge.admin import ProcedureVersionAdmin
from knowledge.fee_admin import FeeAdmin, FeeEvidenceInline, FeeOwnerInline
from knowledge.fees import Fee
from knowledge.models import (
    Authority,
    EligibilityBasis,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    Source,
    Warning,
)
from knowledge.publication import PublicationRejected, publish_procedure_version


class FeeModelValidationTests(TestCase):
    def setUp(self) -> None:
        service = Service.objects.create(
            semantic_id="fee.validation.service", text_ar="خدمة", text_en="Service"
        )
        procedure = Procedure.objects.create(
            semantic_id="fee.validation.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=service,
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="fee.validation.version",
            procedure=procedure,
            text_ar="نسخة",
            text_en="Version",
        )

    def fee(self, **kwargs: Any) -> Fee:
        values: dict[str, Any] = {
            "procedure_version": self.version,
            "semantic_id": "fee.validation.claim",
            "text_ar": "رسم",
            "text_en": "Fee",
            "value_state": Fee.ValueState.KNOWN,
            "amount": 100,
            "currency": "EGP",
            "verification_state": "current",
        }
        values.update(kwargs)
        return Fee(**values)

    def test_model_rejects_inconsistent_value_shapes_currency_and_states(self) -> None:
        cases = (
            self.fee(minimum_amount=50, maximum_amount=150),
            self.fee(
                value_state=Fee.ValueState.RANGE,
                amount=None,
                minimum_amount=150,
                maximum_amount=100,
            ),
            self.fee(value_state=Fee.ValueState.UNKNOWN, amount=1),
            self.fee(
                value_state=Fee.ValueState.UNVERIFIED,
                amount=999,
                verification_state="current",
            ),
            self.fee(currency=" "),
            self.fee(value_state="unsupported"),
        )

        for fee in cases:
            with self.subTest(value_state=fee.value_state, currency=fee.currency):
                with self.assertRaises(ValidationError):
                    fee.full_clean()

    def test_model_rejects_cross_version_basis_ownership(self) -> None:
        other_version = ProcedureVersion.objects.create(
            semantic_id="fee.validation.other-version",
            procedure=self.version.procedure,
            text_ar="نسخة أخرى",
            text_en="Other version",
        )
        other_basis = EligibilityBasis.objects.create(
            procedure_version=other_version,
            semantic_id="fee.validation.other-basis",
        )
        fee = self.fee(
            scope=Fee.Scope.ELIGIBILITY_BASIS,
            eligibility_basis=other_basis,
        )

        with self.assertRaises(ValidationError):
            fee.full_clean()


class FeePublicationTests(TestCase):
    def setUp(self) -> None:
        self.fact, _ = FactDefinition.objects.get_or_create(
            key="fee_publication_applicable",
            defaults={"kind": "boolean", "enum_values": [], "is_published": True},
        )
        self.actor = get_user_model().objects.create_user(username="fee-publication-publisher")
        service = Service.objects.create(
            semantic_id="fee.publication.service", text_ar="خدمة", text_en="Service"
        )
        procedure = Procedure.objects.create(
            semantic_id="fee.publication.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=service,
        )
        predicate = {"op": "eq", "fact": self.fact.key, "value": True}
        ServiceProcedureCandidate.objects.create(
            service=service,
            procedure=procedure,
            selection_predicate=predicate,
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="fee.publication.version",
            procedure=procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability=predicate,
        )
        self.authority = Authority.objects.create(
            semantic_id="fee.publication.authority", name_ar="جهة", name_en="Authority"
        )
        self.source = Source.objects.create(
            semantic_id="fee.publication.source",
            authority=self.authority,
            title="Official fee schedule",
            locator="https://example.test/fees",
            classification=Source.Classification.OFFICIAL,
            retrieved_on=date(2026, 8, 1),
        )

    def regeneration_warning(self, version: ProcedureVersion | None = None) -> Warning:
        owner = version or self.version
        return Warning.objects.create(
            procedure_version=owner,
            semantic_id=f"{owner.semantic_id}.regenerate",
            text_ar="أعد إنشاء الخطة قبل التنفيذ",
            text_en="Regenerate the plan before acting",
            severity=Warning.Severity.IMPORTANT,
            kind=Warning.Kind.PRODUCT,
            role=Warning.Role.REGENERATION,
            display_order=100,
            verification_state="current",
        )

    def fee(self, semantic_id: str, **kwargs: Any) -> Fee:
        values: dict[str, Any] = {
            "procedure_version": self.version,
            "semantic_id": semantic_id,
            "text_ar": "رسم",
            "text_en": "Fee",
            "value_state": Fee.ValueState.KNOWN,
            "amount": 100,
            "currency": "EGP",
            "verification_state": "current",
            "verified_on": date(2026, 8, 1),
        }
        values.update(kwargs)
        return Fee.objects.create(**values)

    def rejection(self) -> PublicationRejected:
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.actor)
        return caught.exception

    def test_publication_requires_evidence_for_asserted_and_unverified_values(self) -> None:
        self.regeneration_warning()
        self.fee("fee.publication.known")
        self.fee(
            "fee.publication.range",
            value_state=Fee.ValueState.RANGE,
            amount=None,
            minimum_amount=100,
            maximum_amount=150,
        )
        self.fee(
            "fee.publication.unverified",
            value_state=Fee.ValueState.UNVERIFIED,
            amount=999,
            verification_state="disputed",
        )
        self.fee(
            "fee.publication.unknown",
            value_state=Fee.ValueState.UNKNOWN,
            amount=None,
        )

        diagnostics = self.rejection().diagnostics
        evidence_required = {
            item.detail for item in diagnostics if item.code == "evidence_required"
        }
        self.assertEqual(
            evidence_required,
            {
                "fee.publication.known",
                "fee.publication.range",
                "fee.publication.unverified",
            },
        )
        self.assertNotIn("fee.publication.unknown", evidence_required)
        self.assertTrue(
            {
                item.detail for item in diagnostics if item.code == "adequate_evidence_required"
            }
            >= {"fee.publication.known", "fee.publication.range"}
        )

    def test_publication_rejects_cross_version_basis_ownership_even_if_db_was_bypassed(self) -> None:
        self.regeneration_warning()
        basis = EligibilityBasis.objects.create(
            procedure_version=self.version,
            semantic_id="fee.publication.basis",
        )
        fee = self.fee(
            "fee.publication.basis-fee",
            value_state=Fee.ValueState.UNKNOWN,
            amount=None,
            scope=Fee.Scope.ELIGIBILITY_BASIS,
            eligibility_basis=basis,
        )
        other_version = ProcedureVersion.objects.create(
            semantic_id="fee.publication.other-version",
            procedure=self.version.procedure,
            text_ar="نسخة أخرى",
            text_en="Other version",
        )
        other_basis = EligibilityBasis.objects.create(
            procedure_version=other_version,
            semantic_id="fee.publication.other-basis",
        )
        Fee.objects.filter(pk=fee.pk).update(eligibility_basis=other_basis)

        diagnostics = self.rejection().diagnostics
        self.assertIn(
            "invalid_basis_owner",
            {item.code for item in diagnostics},
        )

    def test_explicit_unknown_publishes_without_invented_amount_or_evidence(self) -> None:
        self.regeneration_warning()
        fee = self.fee(
            "fee.publication.unknown-only",
            value_state=Fee.ValueState.UNKNOWN,
            amount=None,
        )

        publish_procedure_version(self.version.pk, actor=self.actor)
        fee.refresh_from_db()
        self.version.refresh_from_db()

        self.assertEqual(self.version.state, ProcedureVersion.State.PUBLISHED)
        self.assertIsNone(fee.amount)
        self.assertIsNone(fee.minimum_amount)
        self.assertIsNone(fee.maximum_amount)
        self.assertFalse(fee.evidence_links.exists())


class FeeAdminTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_superuser(username="fee-admin")
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.user
        service = Service.objects.create(
            semantic_id="fee.admin.service", text_ar="خدمة", text_en="Service"
        )
        procedure = Procedure.objects.create(
            semantic_id="fee.admin.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=service,
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="fee.admin.version",
            procedure=procedure,
            text_ar="نسخة",
            text_en="Version",
        )
        self.fee_admin = FeeAdmin(Fee, admin.site)

    def post_fee(self, identifier: str, **overrides: str) -> int:
        data = {
            "procedure_version": str(self.version.pk),
            "semantic_id": identifier,
            "text_ar": "رسم",
            "text_en": "Fee",
            "value_state": Fee.ValueState.KNOWN,
            "amount": "100",
            "minimum_amount": "",
            "maximum_amount": "",
            "currency": "EGP",
            "fee_type": "service_fee",
            "display_order": "10",
            "applicability": "{}",
            "scope": Fee.Scope.PROCEDURE,
            "eligibility_basis": "",
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
        }
        data.update(overrides)
        response = self.client.post(reverse("admin:knowledge_fee_add"), data)
        return response.status_code

    def test_admin_authors_every_fee_value_state(self) -> None:
        self.client.force_login(self.user)
        cases = (
            (
                "fee.admin.known",
                {
                    "value_state": Fee.ValueState.KNOWN,
                    "amount": "705",
                },
            ),
            (
                "fee.admin.range",
                {
                    "value_state": Fee.ValueState.RANGE,
                    "amount": "",
                    "minimum_amount": "100",
                    "maximum_amount": "150",
                },
            ),
            (
                "fee.admin.unknown",
                {
                    "value_state": Fee.ValueState.UNKNOWN,
                    "amount": "",
                },
            ),
            (
                "fee.admin.unverified",
                {
                    "value_state": Fee.ValueState.UNVERIFIED,
                    "amount": "999",
                    "verification_state": "disputed",
                },
            ),
        )

        for identifier, overrides in cases:
            with self.subTest(value_state=overrides["value_state"]):
                self.assertEqual(self.post_fee(identifier, **overrides), 302)

        authored = {
            fee.semantic_id: fee for fee in Fee.objects.filter(procedure_version=self.version)
        }
        self.assertEqual(set(authored), {identifier for identifier, _ in cases})
        self.assertEqual(authored["fee.admin.known"].amount, 705)
        self.assertEqual(
            (
                authored["fee.admin.range"].minimum_amount,
                authored["fee.admin.range"].maximum_amount,
            ),
            (100, 150),
        )
        self.assertIsNone(authored["fee.admin.unknown"].amount)
        self.assertEqual(authored["fee.admin.unverified"].verification_state, "disputed")

    def test_fee_admin_is_wired_into_version_navigation_and_locks_published_rows(self) -> None:
        fees = (
            Fee.objects.create(
                procedure_version=self.version,
                semantic_id="fee.admin.known",
                text_ar="رسم معلوم",
                text_en="Known fee",
                value_state=Fee.ValueState.KNOWN,
                amount=100,
                currency="EGP",
                verification_state="current",
            ),
            Fee.objects.create(
                procedure_version=self.version,
                semantic_id="fee.admin.range",
                text_ar="نطاق رسوم",
                text_en="Fee range",
                value_state=Fee.ValueState.RANGE,
                minimum_amount=100,
                maximum_amount=150,
                currency="EGP",
                verification_state="current",
            ),
            Fee.objects.create(
                procedure_version=self.version,
                semantic_id="fee.admin.unknown",
                text_ar="رسم غير معلوم",
                text_en="Unknown fee",
                value_state=Fee.ValueState.UNKNOWN,
                currency="EGP",
                verification_state="current",
            ),
            Fee.objects.create(
                procedure_version=self.version,
                semantic_id="fee.admin.unverified",
                text_ar="رسم غير متحقق",
                text_en="Unverified fee",
                value_state=Fee.ValueState.UNVERIFIED,
                amount=999,
                currency="EGP",
                verification_state="disputed",
            ),
        )
        ProcedureVersion.objects.filter(pk=self.version.pk).update(
            state=ProcedureVersion.State.PUBLISHED
        )

        self.assertIn(FeeOwnerInline, ProcedureVersionAdmin.inlines)
        for original in fees:
            fee = Fee.objects.select_related("procedure_version").get(pk=original.pk)
            with self.subTest(value_state=fee.value_state):
                self.assertEqual(
                    set(self.fee_admin.get_readonly_fields(self.request, fee)),
                    {field.name for field in Fee._meta.fields},
                )
                self.assertFalse(self.fee_admin.has_delete_permission(self.request, fee))
                inline = FeeEvidenceInline(Fee, admin.site)
                self.assertFalse(inline.has_add_permission(self.request, fee))
                self.assertFalse(inline.has_change_permission(self.request, fee))
                self.assertFalse(inline.has_delete_permission(self.request, fee))
