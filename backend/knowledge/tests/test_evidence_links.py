from __future__ import annotations

from datetime import date
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.test import TransactionTestCase

from knowledge import (
    eligibility_bases,
    fees,
    procedure_dependencies,
    runtime_integrity,
    service_point_routing,
)
from knowledge.fees import Fee
from knowledge.models import (
    EVIDENCE_OWNER_FIELDS,
    ChecklistItem,
    EligibilityBasis,
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    Step,
    Warning,
)
from knowledge.procedure_dependencies import ProcedureDependency
from knowledge.service_point_routing import (
    ProcedureServicePointAssociation,
    ServicePoint,
    ServicePointVersion,
)


class EvidenceLinkContractTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        self.fact, _ = FactDefinition.objects.get_or_create(
            key="is_student",
            defaults={
                "kind": FactDefinition.Kind.BOOLEAN,
                "enum_values": [],
                "is_published": True,
            },
        )
        self.rule = {"op": "eq", "fact": self.fact.key, "value": True}
        self.service = Service.objects.create(
            semantic_id="evidence.contract.service",
            text_ar="خدمة",
            text_en="Service",
        )
        self.procedure = Procedure.objects.create(
            semantic_id="evidence.contract.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=self.service,
        )
        self.target_procedure = Procedure.objects.create(
            semantic_id="evidence.contract.target",
            text_ar="إجراء سابق",
            text_en="Prerequisite",
            primary_service=self.service,
        )
        self.version = self._version("evidence.contract.procedure.v1")
        self.shared_version = self._version("evidence.contract.procedure.v2")
        self.checklist = ChecklistItem.objects.create(
            procedure_version=self.version,
            semantic_id="evidence.contract.checklist",
            text_ar="متطلب",
            text_en="Requirement",
            classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
        )
        self.step = Step.objects.create(
            procedure_version=self.version,
            semantic_id="evidence.contract.step",
            text_ar="خطوة",
            text_en="Step",
            phase="submit",
        )
        self.warning = Warning.objects.create(
            procedure_version=self.version,
            semantic_id="evidence.contract.warning",
            text_ar="تحذير",
            text_en="Warning",
            kind=Warning.Kind.ADMINISTRATIVE,
        )
        self.fee = Fee.objects.create(
            procedure_version=self.version,
            semantic_id="evidence.contract.fee",
            text_ar="رسم",
            text_en="Fee",
            value_state=Fee.ValueState.UNKNOWN,
            currency="EGP",
        )
        self.basis = EligibilityBasis.objects.create(
            procedure_version=self.version,
            semantic_id="evidence.contract.basis",
            text_ar="أساس",
            text_en="Basis",
            qualification=self.rule,
        )
        self.dependency = ProcedureDependency.objects.create(
            procedure_version=self.version,
            semantic_id="evidence.contract.dependency",
            text_ar="إجراء سابق",
            text_en="Prerequisite",
            target_procedure=self.target_procedure,
            satisfied_when=self.rule,
        )
        self.point = ServicePoint.objects.create(
            semantic_id="evidence.contract.point",
            name_ar="مكتب",
            name_en="Office",
        )
        self.material = ServicePointVersion.objects.create(
            semantic_id="evidence.contract.point.v1",
            service_point=self.point,
            address_ar="عنوان",
            address_en="Address",
            availability=ServicePointVersion.Availability.AVAILABLE,
            effective_from=date(2026, 1, 1),
        )
        self.association = ProcedureServicePointAssociation.objects.create(
            procedure_version=self.version,
            semantic_id="evidence.contract.association",
            service_point_version=self.material,
            applicability=self.rule,
        )
        ProcedureServicePointAssociation.objects.create(
            procedure_version=self.shared_version,
            semantic_id="evidence.contract.association.shared",
            service_point_version=self.material,
            applicability=self.rule,
        )
        self.owners: dict[str, Any] = {
            "checklist_item": self.checklist,
            "step": self.step,
            "warning": self.warning,
            "fee": self.fee,
            "eligibility_basis": self.basis,
            "procedure_dependency": self.dependency,
            "service_point_version": self.material,
            "procedure_service_point_association": self.association,
        }

    def _version(self, semantic_id: str) -> ProcedureVersion:
        return ProcedureVersion.objects.create(
            semantic_id=semantic_id,
            procedure=self.procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability=self.rule,
        )

    @staticmethod
    def _link(owner_field: str, owner: Any, semantic_id: str = "") -> EvidenceLink:
        return EvidenceLink(
            **{owner_field: owner},
            semantic_id=semantic_id,
            passage="Relied-upon passage",
            location="Section 1",
            applicability_context="Applies to this claim",
        )

    def test_app_registry_contract_is_declared_without_runtime_installers(self) -> None:
        self.assertEqual(
            EVIDENCE_OWNER_FIELDS,
            (
                "checklist_item",
                "step",
                "warning",
                "fee",
                "eligibility_basis",
                "procedure_dependency",
                "service_point_version",
                "procedure_service_point_association",
            ),
        )
        self.assertEqual(EvidenceLink._meta.db_table, "knowledge_evidencelink")
        self.assertEqual(
            tuple(field.name for field in EvidenceLink._meta.fields),
            (
                "id",
                "semantic_id",
                "checklist_item",
                "step",
                "warning",
                "passage",
                "location",
                "applicability_context",
                "effective_from",
                "effective_to",
                "retrieved_on",
                "verified_on",
                "reverify_on",
                "verification_state",
                "support_status",
                "fee",
                "eligibility_basis",
                "procedure_dependency",
                "service_point_version",
                "procedure_service_point_association",
            ),
        )
        expected_targets = {
            "checklist_item": "knowledge.checklistitem",
            "step": "knowledge.step",
            "warning": "knowledge.warning",
            "fee": "knowledge.fee",
            "eligibility_basis": "knowledge.eligibilitybasis",
            "procedure_dependency": "knowledge.proceduredependency",
            "service_point_version": "knowledge.servicepointversion",
            "procedure_service_point_association": "knowledge.procedureservicepointassociation",
        }
        for field_name, target in expected_targets.items():
            with self.subTest(field=field_name):
                field = EvidenceLink._meta.get_field(field_name)
                self.assertIsInstance(field, models.ForeignKey)
                assert isinstance(field, models.ForeignKey)
                self.assertTrue(field.null)
                self.assertTrue(field.blank)
                self.assertIs(field.remote_field.on_delete, models.CASCADE)
                self.assertEqual(field.remote_field.related_name, "evidence_links")
                self.assertEqual(field.remote_field.model._meta.label_lower, target)

        self.assertEqual(
            tuple(constraint.name for constraint in EvidenceLink._meta.constraints),
            (
                "unique_evidence_id_checklist_owner",
                "unique_evidence_id_step_owner",
                "unique_evidence_id_warning_owner",
                "evidence_verification_supported",
                "evidence_support_supported",
                "evidence_dates_ordered",
                "evidence_exactly_one_owner",
                "evidence_semantic_id_blank_or_nonblank",
                "unique_evidence_id_fee_owner",
                "unique_evidence_id_basis_owner",
                "unique_evidence_id_dependency_owner",
                "unique_evidence_id_point_version_owner",
                "unique_evidence_id_point_association_owner",
            ),
        )
        owner_getter = EvidenceLink.owner.fget
        assert owner_getter is not None
        self.assertEqual(owner_getter.__module__, "knowledge.models")
        self.assertEqual(EvidenceLink.owning_versions.__module__, "knowledge.models")
        self.assertEqual(EvidenceLink.owning_version.__module__, "knowledge.models")
        self.assertEqual(EvidenceLink.clean.__module__, "knowledge.models")
        for module, installer in (
            (fees, "_install_fee_evidence_owner"),
            (eligibility_bases, "_install_basis_evidence_owner"),
            (procedure_dependencies, "_install_dependency_evidence_owner"),
            (service_point_routing, "_install_routing_evidence_owners"),
            (runtime_integrity, "install_evidence_identity_validation"),
        ):
            with self.subTest(installer=installer):
                self.assertFalse(hasattr(module, installer))

    def test_every_supported_owner_resolves_and_owns_expected_versions(self) -> None:
        for field_name, owner in self.owners.items():
            with self.subTest(owner=field_name):
                link = self._link(field_name, owner)
                link.full_clean()
                self.assertEqual(link.owner, owner)
                versions = link.owning_versions()
                if field_name == "service_point_version":
                    self.assertEqual(versions, (self.version, self.shared_version))
                    self.assertEqual(link.owning_version(), self.version)
                else:
                    self.assertEqual(versions, (self.version,))
                    self.assertEqual(link.owning_version(), self.version)

    def test_zero_and_multiple_owners_fail_model_and_database_validation(self) -> None:
        ownerless = EvidenceLink(passage="Ownerless")
        with self.assertRaisesMessage(ValidationError, "exactly one claim owner"):
            ownerless.full_clean()

        multiple = self._link("checklist_item", self.checklist)
        multiple.step = self.step
        with self.assertRaisesMessage(ValidationError, "exactly one claim owner"):
            multiple.full_clean()

        with self.assertRaises(IntegrityError), transaction.atomic():
            EvidenceLink.objects.bulk_create([EvidenceLink(passage="Ownerless database row")])
        with self.assertRaises(IntegrityError), transaction.atomic():
            EvidenceLink.objects.bulk_create(
                [
                    EvidenceLink(
                        checklist_item=self.checklist,
                        step=self.step,
                        passage="Multiple-owner database row",
                    )
                ]
            )

    def test_owner_scoped_semantic_identity_is_unique_but_blank_is_repeatable(self) -> None:
        for field_name, owner in self.owners.items():
            with self.subTest(owner=field_name):
                first = self._link(field_name, owner, f"duplicate-{field_name}")
                first.save()
                duplicate = self._link(field_name, owner, first.semantic_id)
                with self.assertRaises(ValidationError):
                    duplicate.full_clean()

        checklist_identity = self._link("checklist_item", self.checklist, "cross-owner")
        checklist_identity.save()
        step_identity = self._link("step", self.step, "cross-owner")
        step_identity.save()

        self._link("checklist_item", self.checklist).save()
        self._link("checklist_item", self.checklist).save()

    def test_whitespace_dates_product_warning_and_owner_reassignment_are_rejected(self) -> None:
        whitespace = self._link("checklist_item", self.checklist, "   ")
        with self.assertRaisesMessage(ValidationError, "Evidence identity cannot be whitespace"):
            whitespace.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            EvidenceLink.objects.bulk_create(
                [
                    EvidenceLink(
                        checklist_item=self.checklist,
                        semantic_id="   ",
                        passage="Whitespace identity",
                    )
                ]
            )

        invalid_dates = self._link("checklist_item", self.checklist)
        invalid_dates.effective_from = date(2026, 9, 2)
        invalid_dates.effective_to = date(2026, 9, 1)
        with self.assertRaisesMessage(ValidationError, "Effective interval is not ordered"):
            invalid_dates.full_clean()

        product_warning = Warning.objects.create(
            procedure_version=self.version,
            semantic_id="evidence.contract.product-warning",
            text_ar="تنبيه",
            text_en="Product warning",
            kind=Warning.Kind.PRODUCT,
        )
        invalid_warning_link = self._link("warning", product_warning)
        with self.assertRaisesMessage(
            ValidationError,
            "Product warnings cannot carry Evidence Links",
        ):
            invalid_warning_link.full_clean()

        persisted = self._link("checklist_item", self.checklist, "protected-owner")
        persisted.save()
        persisted.checklist_item = None
        persisted.step = self.step
        with self.assertRaisesMessage(ValidationError, "ownership cannot be reassigned"):
            persisted.full_clean()
