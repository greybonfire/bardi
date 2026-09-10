from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from knowledge.models import (
    ChecklistItem,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceQuestion,
    Step,
)
from knowledge.publication import (
    ApplicabilityGate,
    PublicationContext,
    _load_published_fact_definitions,
)

TODAY = date(2026, 9, 5)


class RecentApplicabilityPublicationRegressionTests(TestCase):
    """Durable publication coverage for issues #115 and #116."""

    def setUp(self) -> None:
        self.actor = get_user_model().objects.create_user(username="recent-applicability-gate")
        self.service = Service.objects.create(
            semantic_id="recent.applicability.service",
            text_ar="خدمة",
            text_en="Service",
        )
        self.other_service = Service.objects.create(
            semantic_id="recent.applicability.other-service",
            text_ar="خدمة أخرى",
            text_en="Other service",
        )
        self.procedure = Procedure.objects.create(
            semantic_id="recent.applicability.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=self.service,
        )
        self.facts = {
            key: FactDefinition.objects.create(
                key=key,
                kind=FactDefinition.Kind.BOOLEAN,
                enum_values=[],
                is_published=True,
            )
            for key in (
                "recent_version_applies",
                "recent_checklist_applies",
                "recent_step_applies",
                "recent_practical_applies",
            )
        }
        self.version = ProcedureVersion.objects.create(
            semantic_id="recent.applicability.procedure.v1",
            procedure=self.procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability=self.rule("recent_version_applies"),
        )

    @staticmethod
    def rule(key: str) -> dict[str, object]:
        return {"op": "eq", "fact": key, "value": True}

    def question(self, key: str, *, service: Service | None = None) -> ServiceQuestion:
        target_service = self.service if service is None else service
        return ServiceQuestion.objects.create(
            semantic_id=f"{target_service.semantic_id}.question.{key}",
            service=target_service,
            fact=self.facts[key],
            text_ar="هل؟",
            text_en="Does it apply?",
            priority=10,
        )

    def diagnostics(self) -> set[tuple[str, str]]:
        context = PublicationContext(
            self.version,
            self.actor,
            _load_published_fact_definitions(),
        )
        return {(item.code, item.detail) for item in ApplicabilityGate().validate(context)}

    def test_version_applicability_requires_same_service_question(self) -> None:
        key = "recent_version_applies"
        self.assertIn(("missing_service_question", key), self.diagnostics())

        self.question(key, service=self.other_service)
        self.assertIn(("missing_service_question", key), self.diagnostics())

        self.question(key)
        self.assertNotIn(("missing_service_question", key), self.diagnostics())

    def test_official_checklist_and_steps_require_structural_coverage_even_when_future_or_stale(
        self,
    ) -> None:
        self.question("recent_version_applies")
        ChecklistItem.objects.create(
            procedure_version=self.version,
            semantic_id="recent.applicability.future-checklist",
            text_ar="متطلب",
            text_en="Requirement",
            classification=ChecklistItem.Classification.OFFICIAL_REQUIREMENT,
            applicability=self.rule("recent_checklist_applies"),
            effective_from=TODAY + timedelta(days=30),
            verification_state="stale",
        )
        Step.objects.create(
            procedure_version=self.version,
            semantic_id="recent.applicability.future-step",
            text_ar="خطوة",
            text_en="Step",
            phase="submit",
            applicability=self.rule("recent_step_applies"),
            effective_from=TODAY + timedelta(days=30),
            verification_state="stale",
        )

        missing = self.diagnostics()
        self.assertIn(("missing_service_question", "recent_checklist_applies"), missing)
        self.assertIn(("missing_service_question", "recent_step_applies"), missing)

        self.question("recent_checklist_applies")
        self.question("recent_step_applies")
        covered = self.diagnostics()
        self.assertNotIn(("missing_service_question", "recent_checklist_applies"), covered)
        self.assertNotIn(("missing_service_question", "recent_step_applies"), covered)

    def test_optional_practical_preparation_predicate_does_not_expand_mandatory_question_coverage(
        self,
    ) -> None:
        self.question("recent_version_applies")
        ChecklistItem.objects.create(
            procedure_version=self.version,
            semantic_id="recent.applicability.practical",
            text_ar="تحضير",
            text_en="Preparation",
            classification=ChecklistItem.Classification.PRACTICAL_PREPARATION,
            applicability=self.rule("recent_practical_applies"),
            verification_state="current",
        )

        self.assertNotIn(
            ("missing_service_question", "recent_practical_applies"),
            self.diagnostics(),
        )
