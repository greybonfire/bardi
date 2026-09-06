from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from knowledge.models import (
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
)
from knowledge.publication import PublicationContext, _load_published_fact_definitions
from knowledge.selection_questions import SelectionQuestionPublicationGate
from knowledge.services import set_question_resolved_facts


@override_settings(SELECTION_QUESTIONS_REQUIRED=True)
class SelectionQuestionPublicationGateTests(TestCase):
    def setUp(self) -> None:
        self.actor = get_user_model().objects.create_user(username="selection-publisher")
        self.service = Service.objects.create(
            semantic_id="selection.service", text_ar="خدمة", text_en="Service"
        )
        self.procedure = Procedure.objects.create(
            semantic_id="selection.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=self.service,
        )
        self.citizenship = FactDefinition.objects.get(key="citizenship")
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate={
                "op": "eq",
                "fact": "citizenship",
                "value": "egyptian",
            },
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="selection.v1",
            procedure=self.procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability={"op": "eq", "fact": "citizenship", "value": "egyptian"},
        )

    def context(self) -> PublicationContext:
        return PublicationContext(
            self.version,
            self.actor,
            _load_published_fact_definitions(),
        )

    def test_equivalent_missing_citizenship_question_is_rejected(self) -> None:
        diagnostics = tuple(SelectionQuestionPublicationGate().validate(self.context()))
        self.assertEqual(
            [(item.code, item.detail) for item in diagnostics],
            [("missing_service_question", "citizenship")],
        )

    def test_same_service_question_permits_gate(self) -> None:
        question = ServiceQuestion.objects.create(
            semantic_id="q.citizenship",
            service=self.service,
            fact=self.citizenship,
            text_ar="هل أنت مواطن مصري؟",
            text_en="Are you an Egyptian citizen?",
            priority=0,
        )
        set_question_resolved_facts(question, (self.citizenship,))
        self.assertEqual(tuple(SelectionQuestionPublicationGate().validate(self.context())), ())

    def test_derived_fact_expands_to_pinned_source_dependency(self) -> None:
        candidate = ServiceProcedureCandidate.objects.get(procedure=self.procedure)
        candidate.selection_predicate = {
            "op": "gte",
            "fact": "age_years_on_evaluation_date",
            "value": 15,
        }
        candidate.save()
        birth_date = FactDefinition.objects.get(key="birth_date")
        question = ServiceQuestion.objects.create(
            semantic_id="q.birth_date",
            service=self.service,
            fact=birth_date,
            text_ar="ما تاريخ ميلادك؟",
            text_en="What is your date of birth?",
            priority=1,
        )
        set_question_resolved_facts(question, (birth_date,))
        self.assertEqual(tuple(SelectionQuestionPublicationGate().validate(self.context())), ())

    def test_wrong_service_question_does_not_cover_fact(self) -> None:
        other = Service.objects.create(
            semantic_id="selection.other", text_ar="أخرى", text_en="Other"
        )
        question = ServiceQuestion.objects.create(
            semantic_id="q.other.citizenship",
            service=other,
            fact=self.citizenship,
            text_ar="هل أنت مواطن مصري؟",
            text_en="Are you an Egyptian citizen?",
            priority=0,
        )
        set_question_resolved_facts(question, (self.citizenship,))
        diagnostics = tuple(SelectionQuestionPublicationGate().validate(self.context()))
        self.assertEqual(diagnostics[0].detail, "citizenship")
