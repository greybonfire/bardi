from __future__ import annotations

from datetime import date
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase

from knowledge import eligibility_bases
from knowledge.domain import load_knowledge_snapshot
from knowledge.models import (
    Authority,
    ChecklistItem,
    EligibilityBasis,
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
    Source,
    Warning,
)
from knowledge.publication import PublicationRejected, publish_procedure_version
from knowledge.services import set_evidence_link_sources


class EligibilityBasisKnowledgeTests(TestCase):
    def setUp(self) -> None:
        self.gate = FactDefinition.objects.create(
            key="basis_gate",
            kind="boolean",
            enum_values=[],
            is_published=True,
        )
        self.qualification = FactDefinition.objects.create(
            key="basis_qualification",
            kind="boolean",
            enum_values=[],
            is_published=True,
        )
        self.actor = get_user_model().objects.create_user(username="basis-publisher")
        self.service = Service.objects.create(
            semantic_id="basis.service",
            text_ar="خدمة",
            text_en="Service",
        )
        self.procedure = Procedure.objects.create(
            semantic_id="basis.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=self.service,
        )
        self.predicate = {"op": "eq", "fact": self.gate.key, "value": True}
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate=self.predicate,
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="basis.version",
            procedure=self.procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability=self.predicate,
        )
        self.authority = Authority.objects.create(
            semantic_id="basis.authority",
            name_ar="جهة",
            name_en="Authority",
        )
        self.source = Source.objects.create(
            semantic_id="basis.source",
            authority=self.authority,
            title="Official basis source",
            locator="https://example.test/basis",
            classification=Source.Classification.OFFICIAL,
            retrieved_on=date(2026, 8, 1),
        )

    def add_question(self, fact: FactDefinition, *, priority: int) -> ServiceQuestion:
        return ServiceQuestion.objects.create(
            semantic_id=f"question.{fact.key}",
            service=self.service,
            fact=fact,
            text_ar=f"سؤال {fact.key}",
            text_en=f"Question {fact.key}",
            priority=priority,
        )

    def regeneration_warning(self) -> Warning:
        return Warning.objects.create(
            procedure_version=self.version,
            semantic_id="basis.regenerate",
            text_ar="أعد إنشاء الخطة قبل التنفيذ",
            text_en="Regenerate the plan before acting",
            severity=Warning.Severity.IMPORTANT,
            kind=Warning.Kind.PRODUCT,
            role=Warning.Role.REGENERATION,
            display_order=100,
            verification_state="current",
        )

    def basis(self, **overrides: Any) -> EligibilityBasis:
        values: dict[str, Any] = {
            "procedure_version": self.version,
            "semantic_id": "basis.route",
            "text_ar": "مسار الأهلية",
            "text_en": "Eligibility route",
            "reachability": self.predicate,
            "qualification": {
                "op": "eq",
                "fact": self.qualification.key,
                "value": True,
            },
            "display_order": 10,
            "verification_state": "current",
            "verified_on": date(2026, 8, 1),
        }
        values.update(overrides)
        return EligibilityBasis.objects.create(**values)

    def evidence(self, basis: EligibilityBasis) -> EvidenceLink:
        link = EvidenceLink.objects.create(
            eligibility_basis=basis,
            passage="Basis passage",
            location="Section 1",
            applicability_context="Ordinary applicant",
            support_status=EvidenceLink.SupportStatus.SUPPORTS,
            verification_state="current",
            verified_on=date(2026, 8, 1),
        )
        set_evidence_link_sources(link, (self.source,))
        return link

    def rejection(self) -> PublicationRejected:
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.actor)
        return caught.exception

    def test_basis_contract_is_declared_on_the_model(self) -> None:
        self.assertEqual(
            tuple(field.name for field in EligibilityBasis._meta.fields),
            (
                "id",
                "procedure_version",
                "semantic_id",
                "text_ar",
                "text_en",
                "reachability",
                "qualification",
                "display_order",
                "effective_from",
                "effective_to",
                "verified_on",
                "reverify_on",
                "verification_state",
            ),
        )
        self.assertEqual(
            EligibilityBasis._meta.ordering,
            ("procedure_version_id", "semantic_id"),
        )
        self.assertEqual(
            tuple(constraint.name for constraint in EligibilityBasis._meta.constraints),
            (
                "unique_basis_id_per_version",
                "basis_id_nonblank",
                "basis_ar_nonblank",
                "basis_en_nonblank",
                "basis_dates_ordered",
                "basis_verification_supported",
            ),
        )
        self.assertEqual(EligibilityBasis.clean.__module__, "knowledge.models")
        self.assertFalse(hasattr(eligibility_bases, "_install_basis_fields"))

    def test_draft_basis_edits_use_declared_validation(self) -> None:
        basis = self.basis(
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
        )
        basis.text_en = "Updated eligibility route"
        basis.effective_to = date(2027, 1, 1)
        basis.save()
        basis.refresh_from_db()
        self.assertEqual(basis.text_en, "Updated eligibility route")
        self.assertEqual(basis.effective_to, date(2027, 1, 1))

        basis.effective_from = date(2027, 1, 2)
        basis.effective_to = date(2027, 1, 1)
        with self.assertRaisesMessage(ValidationError, "Effective interval is not ordered"):
            basis.save()

    def test_published_basis_rejects_model_save_and_delete(self) -> None:
        self.regeneration_warning()
        self.add_question(self.gate, priority=1)
        self.add_question(self.qualification, priority=2)
        basis = self.basis()
        self.evidence(basis)
        publish_procedure_version(self.version.pk, actor=self.actor)
        basis.refresh_from_db()

        basis.text_en = "Changed"
        message = "Published and withdrawn Procedure Version children are immutable."
        with self.assertRaisesMessage(ValidationError, message):
            basis.save()
        with self.assertRaisesMessage(ValidationError, message):
            basis.delete()

    def test_basis_requires_bilingual_identity_and_explicit_qualification(self) -> None:
        invalid = (
            EligibilityBasis(
                procedure_version=self.version,
                semantic_id="basis.missing-text",
                text_ar="",
                text_en="Basis",
                qualification=self.predicate,
            ),
            EligibilityBasis(
                procedure_version=self.version,
                semantic_id="basis.missing-qualification",
                text_ar="أساس",
                text_en="Basis",
                qualification={},
            ),
        )
        for basis in invalid:
            with self.subTest(semantic_id=basis.semantic_id), self.assertRaises(ValidationError):
                basis.full_clean()

    def test_basis_evidence_is_an_exact_claim_owner(self) -> None:
        basis = self.basis()
        warning = self.regeneration_warning()
        invalid = EvidenceLink(
            eligibility_basis=basis,
            warning=warning,
            passage="Passage",
            location="Section",
            applicability_context="Context",
            verification_state="current",
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_publication_requires_evidence_and_question_coverage_for_both_stages(self) -> None:
        self.regeneration_warning()
        self.add_question(self.gate, priority=1)
        self.basis()

        diagnostics = self.rejection().diagnostics
        codes = {(item.code, item.detail) for item in diagnostics}
        self.assertIn(("evidence_required", "basis.route"), codes)
        self.assertIn(("adequate_evidence_required", "basis.route"), codes)
        self.assertIn(("missing_service_question", self.qualification.key), codes)

    def test_publication_rejects_malformed_persisted_rule_stages(self) -> None:
        self.regeneration_warning()
        self.add_question(self.gate, priority=1)
        self.add_question(self.qualification, priority=2)
        basis = self.basis()
        self.evidence(basis)

        EligibilityBasis.objects.filter(pk=basis.pk).update(
            reachability={"op": "unsupported", "fact": self.gate.key}
        )
        reachability_diagnostics = self.rejection().diagnostics
        self.assertTrue(
            any(item.detail == "basis.route:reachability" for item in reachability_diagnostics)
        )

        EligibilityBasis.objects.filter(pk=basis.pk).update(
            reachability=self.predicate,
            qualification={},
        )
        qualification_diagnostics = self.rejection().diagnostics
        self.assertIn(
            ("qualification_required", "basis.route"),
            {(item.code, item.detail) for item in qualification_diagnostics},
        )

    def test_publication_rejects_unknown_basis_scope_ownership(self) -> None:
        self.regeneration_warning()
        self.add_question(self.gate, priority=1)
        self.add_question(self.qualification, priority=2)
        basis = self.basis()
        self.evidence(basis)
        ChecklistItem.objects.create(
            procedure_version=self.version,
            semantic_id="basis.orphaned.claim",
            text_ar="مطالبة",
            text_en="Claim",
            classification=ChecklistItem.Classification.CANDIDATE,
            scope=ChecklistItem.Scope.ELIGIBILITY_BASIS,
            scope_reference="basis.missing",
            verification_state="needs_reverification",
        )

        diagnostics = self.rejection().diagnostics
        self.assertIn(
            ("invalid_basis_owner", "basis.orphaned.claim"),
            {(item.code, item.detail) for item in diagnostics},
        )

    def test_published_snapshot_contains_detached_two_stage_basis_and_evidence(self) -> None:
        self.regeneration_warning()
        self.add_question(self.gate, priority=1)
        self.add_question(self.qualification, priority=2)
        basis = self.basis()
        self.evidence(basis)

        publish_procedure_version(self.version.pk, actor=self.actor)
        snapshot = load_knowledge_snapshot()
        version = next(
            item
            for item in snapshot.procedure_versions
            if item.semantic_id == self.version.semantic_id
        )
        self.assertEqual(len(version.eligibility_bases), 1)
        detached = version.eligibility_bases[0]
        self.assertEqual(detached.semantic_id, "basis.route")
        self.assertIsNotNone(detached.reachability)
        self.assertIsNotNone(detached.qualification)
        self.assertEqual(detached.text.en, "Eligibility route")
        self.assertEqual(detached.evidence_links[0].sources[0].semantic_id, self.source.semantic_id)

    def test_published_basis_and_evidence_are_database_immutable(self) -> None:
        self.regeneration_warning()
        self.add_question(self.gate, priority=1)
        self.add_question(self.qualification, priority=2)
        basis = self.basis()
        evidence = self.evidence(basis)
        publish_procedure_version(self.version.pk, actor=self.actor)

        for model, primary_key, values in (
            (EligibilityBasis, basis.pk, {"text_en": "Changed"}),
            (EvidenceLink, evidence.pk, {"passage": "Changed"}),
            (Source, self.source.pk, {"title": "Changed"}),
            (Authority, self.authority.pk, {"name_en": "Changed"}),
        ):
            with self.subTest(model=model.__name__), self.assertRaises(DatabaseError):
                with transaction.atomic():
                    model.objects.filter(pk=primary_key).update(**values)

        persisted = cast(Any, EligibilityBasis.objects.get(pk=basis.pk))
        self.assertEqual(persisted.text_en, "Eligibility route")


__all__ = ("EligibilityBasisKnowledgeTests",)
