from __future__ import annotations

from datetime import date
from typing import Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase

from knowledge.domain import load_knowledge_snapshot
from knowledge.models import (
    Authority,
    EligibilityBasis,
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


class GuidancePublicationTests(TestCase):
    def setUp(self) -> None:
        FactDefinition.objects.get_or_create(
            key="is_student",
            defaults={"kind": "boolean", "enum_values": [], "is_published": True},
        )
        self.actor = get_user_model().objects.create_user(username="guidance-publisher")
        service = Service.objects.create(
            semantic_id="guidance.service", text_ar="خدمة", text_en="Service"
        )
        procedure = Procedure.objects.create(
            semantic_id="guidance.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=service,
        )
        predicate = {"op": "eq", "fact": "is_student", "value": True}
        ServiceProcedureCandidate.objects.create(
            service=service, procedure=procedure, selection_predicate=predicate
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="guidance.version",
            procedure=procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability=predicate,
        )
        self.authority = Authority.objects.create(
            semantic_id="guidance.authority", name_ar="جهة", name_en="Authority"
        )
        self.source = Source.objects.create(
            semantic_id="guidance.source",
            authority=self.authority,
            title="Official guidance",
            locator="https://example.test/guidance",
            classification=Source.Classification.OFFICIAL,
            retrieved_on=date(2026, 8, 1),
        )

    def step(self, **kwargs: Any) -> Step:
        values: dict[str, Any] = {
            "procedure_version": self.version,
            "semantic_id": "guidance.step",
            "text_ar": "قدّم الطلب",
            "text_en": "Submit the application",
            "phase": "submit",
            "phase_order": 10,
            "slot": 10,
            "verification_state": "current",
            "verified_on": date(2026, 8, 1),
        }
        values.update(kwargs)
        return Step.objects.create(**values)

    def warning(self, **kwargs: Any) -> Warning:
        values: dict[str, Any] = {
            "procedure_version": self.version,
            "semantic_id": "guidance.warning",
            "text_ar": "تحقق من الجهة",
            "text_en": "Verify with the authority",
            "severity": Warning.Severity.INFO,
            "kind": Warning.Kind.ADMINISTRATIVE,
            "role": Warning.Role.GENERAL,
            "display_order": 10,
            "verification_state": "current",
            "verified_on": date(2026, 8, 1),
        }
        values.update(kwargs)
        return Warning.objects.create(**values)

    def regeneration_warning(self) -> Warning:
        return self.warning(
            semantic_id="guidance.warning.regenerate",
            text_ar="أعد إنشاء الخطة قبل التنفيذ",
            text_en="Regenerate the plan before acting",
            severity=Warning.Severity.IMPORTANT,
            kind=Warning.Kind.PRODUCT,
            role=Warning.Role.REGENERATION,
            display_order=100,
        )

    def evidence(self, owner: Step | Warning) -> EvidenceLink:
        values: dict[str, object] = {
            "passage": "Exact relied-upon passage",
            "location": "Section 1",
            "applicability_context": "Applies to this procedure",
            "verification_state": "current",
            "support_status": EvidenceLink.SupportStatus.SUPPORTS,
        }
        values["step" if isinstance(owner, Step) else "warning"] = owner
        link = EvidenceLink.objects.create(**values)
        set_evidence_link_sources(link, (self.source,))
        return link

    def rejection_codes(self) -> set[str]:
        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=self.actor)
        return {item.code for item in caught.exception.diagnostics}

    def test_current_steps_and_administrative_warnings_require_evidence(self) -> None:
        self.step()
        self.warning()
        self.regeneration_warning()
        self.assertIn("adequate_evidence_required", self.rejection_codes())

    def test_product_warnings_reject_evidence_and_basis_scope_checks_ownership(self) -> None:
        basis = EligibilityBasis.objects.create(
            procedure_version=self.version, semantic_id="basis.student"
        )
        step = self.step(
            scope=Step.Scope.ELIGIBILITY_BASIS,
            eligibility_basis=basis,
        )
        self.evidence(step)
        other_version = ProcedureVersion.objects.create(
            semantic_id="guidance.version.other",
            procedure=self.version.procedure,
            text_ar="نسخة أخرى",
            text_en="Other version",
        )
        other_basis = EligibilityBasis.objects.create(
            procedure_version=other_version, semantic_id="basis.other"
        )
        Step.objects.filter(pk=step.pk).update(eligibility_basis=other_basis)
        product = self.regeneration_warning()
        administrative = self.warning(semantic_id="guidance.warning.with-evidence")
        link = self.evidence(administrative)
        Warning.objects.filter(pk=administrative.pk).update(kind=Warning.Kind.PRODUCT)

        codes = self.rejection_codes()
        self.assertIn("product_warning_has_evidence", codes)
        self.assertIn("invalid_basis_owner", codes)
        with self.assertRaises(ValidationError):
            EvidenceLink.objects.create(
                warning=product,
                passage="Passage",
                location="Section",
                applicability_context="Context",
                verification_state="current",
            )
        self.assertTrue(EvidenceLink.objects.filter(pk=link.pk).exists())

    def test_authored_guidance_requires_one_regeneration_warning(self) -> None:
        step = self.step()
        self.evidence(step)
        self.assertIn("exactly_one_regeneration_warning_required", self.rejection_codes())

    def test_successful_publication_detaches_and_immutably_preserves_guidance(self) -> None:
        step = self.step()
        step_link = self.evidence(step)
        warning = self.warning()
        warning_link = self.evidence(warning)
        product = self.regeneration_warning()

        publish_procedure_version(self.version.pk, actor=self.actor)
        snapshot = load_knowledge_snapshot()
        detached = next(
            item
            for item in snapshot.procedure_versions
            if item.semantic_id == self.version.semantic_id
        )
        with self.assertNumQueries(0):
            self.assertEqual(detached.steps[0].semantic_id, step.semantic_id)
            self.assertEqual(
                detached.steps[0].evidence_links[0].sources[0].title, "Official guidance"
            )
            self.assertEqual(
                tuple(item.semantic_id for item in detached.warnings),
                (warning.semantic_id, product.semantic_id),
            )

        updates = (
            (Step, step.pk, {"text_en": "Changed"}),
            (Warning, warning.pk, {"text_en": "Changed"}),
            (EvidenceLink, step_link.pk, {"passage": "Changed"}),
            (EvidenceLink, warning_link.pk, {"passage": "Changed"}),
            (Source, self.source.pk, {"title": "Changed"}),
            (Authority, self.authority.pk, {"name_en": "Changed"}),
        )
        for model, primary_key, values in updates:
            with self.subTest(model=model.__name__), self.assertRaises(DatabaseError):
                with transaction.atomic():
                    model.objects.filter(pk=primary_key).update(**values)
