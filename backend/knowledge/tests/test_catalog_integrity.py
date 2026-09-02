from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms.models import inlineformset_factory
from django.test import RequestFactory, TestCase

from knowledge.admin import ContradictionAdmin, QuestionAdmin
from knowledge.forms import ContradictionFactFormSet, QuestionResolvedFactFormSet
from knowledge.models import (
    FactDefinition,
    Goal,
    GoalContradiction,
    GoalContradictionFact,
    GoalProcedureCandidate,
    GoalQuestion,
    GoalQuestionResolvedFact,
    Procedure,
)
from knowledge.services import set_contradiction_facts, set_question_resolved_facts


class CatalogAcceptanceIntegrityTests(TestCase):
    def setUp(self) -> None:
        self.goal = Goal.objects.create(
            semantic_id="goal.integrity", text_ar="هدف", text_en="Integrity Goal"
        )
        self.other_goal = Goal.objects.create(
            semantic_id="goal.integrity.other", text_ar="هدف آخر", text_en="Other Goal"
        )
        self.primary = FactDefinition.objects.get(key="national_id_expiry_date")
        self.other = FactDefinition.objects.get(key="is_student")
        self.second = FactDefinition.objects.get(key="has_current_enrollment_certificate")

    def test_duplicate_stable_identities_and_candidate_membership_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Goal(
                semantic_id=self.goal.semantic_id,
                text_ar="هدف مكرر",
                text_en="Duplicate Goal",
            ).full_clean()

        procedure = Procedure.objects.create(
            semantic_id="procedure.integrity",
            text_ar="إجراء",
            text_en="Procedure",
            primary_goal=self.goal,
        )
        with self.assertRaises(ValidationError):
            Procedure(
                semantic_id=procedure.semantic_id,
                text_ar="إجراء آخر",
                text_en="Duplicate Procedure",
                primary_goal=self.goal,
            ).full_clean()

        question = GoalQuestion.objects.create(
            semantic_id="question.integrity",
            goal=self.goal,
            fact=self.primary,
            text_ar="سؤال؟",
            text_en="Question?",
            priority=10,
        )
        with self.assertRaises(ValidationError):
            GoalQuestion(
                semantic_id=question.semantic_id,
                goal=self.goal,
                fact=self.primary,
                text_ar="سؤال آخر؟",
                text_en="Duplicate Question?",
                priority=20,
            ).full_clean()

        contradiction = GoalContradiction.objects.create(
            semantic_id="contradiction.integrity",
            goal=self.goal,
            condition={
                "op": "all",
                "children": [
                    {"op": "eq", "fact": self.other.key, "value": True},
                    {"op": "eq", "fact": self.second.key, "value": False},
                ],
            },
        )
        set_contradiction_facts(contradiction, [self.other, self.second])
        with self.assertRaises(ValidationError):
            GoalContradiction(
                semantic_id=contradiction.semantic_id,
                goal=self.goal,
                condition={"op": "exists", "fact": self.other.key},
            ).full_clean()

        candidate = GoalProcedureCandidate.objects.create(
            goal=self.goal,
            procedure=procedure,
            selection_predicate={"op": "exists", "fact": self.other.key},
        )
        self.assertIsNotNone(candidate.pk)
        with self.assertRaises(ValidationError):
            GoalProcedureCandidate(
                goal=self.goal,
                procedure=procedure,
                selection_predicate={"op": "eq", "fact": self.other.key, "value": True},
            ).full_clean()

    def test_question_fact_set_rejects_direct_row_writes_and_deletes(self) -> None:
        question = GoalQuestion.objects.create(
            semantic_id="question.boundary",
            goal=self.goal,
            fact=self.primary,
            text_ar="تاريخ؟",
            text_en="Date?",
            priority=1,
        )

        with self.assertRaisesMessage(ValidationError, "set_question_resolved_facts()"):
            GoalQuestionResolvedFact.objects.create(question=question, fact=self.other, position=1)
        self.assertFalse(question.resolved_fact_links.exists())

        set_question_resolved_facts(question, [self.primary, self.other])
        primary_link = question.resolved_fact_links.get(fact=self.primary)
        with self.assertRaisesMessage(ValidationError, "set_question_resolved_facts()"):
            with transaction.atomic():
                primary_link.delete()
        self.assertEqual(question.resolved_fact_keys, (self.primary.key, self.other.key))

        set_question_resolved_facts(question, [])
        self.assertEqual(question.resolved_fact_keys, (self.primary.key,))

    def test_contradiction_fact_set_rejects_direct_row_writes_and_deletes(self) -> None:
        contradiction = GoalContradiction.objects.create(
            semantic_id="contradiction.boundary",
            goal=self.goal,
            condition={
                "op": "all",
                "children": [
                    {"op": "eq", "fact": self.other.key, "value": True},
                    {"op": "eq", "fact": self.second.key, "value": False},
                ],
            },
        )

        with self.assertRaisesMessage(ValidationError, "set_contradiction_facts()"):
            GoalContradictionFact.objects.create(
                contradiction=contradiction, fact=self.other, position=1
            )
        self.assertFalse(contradiction.fact_links.exists())

        set_contradiction_facts(contradiction, [self.other, self.second])
        first_link = contradiction.fact_links.get(fact=self.other)
        with self.assertRaisesMessage(ValidationError, "set_contradiction_facts()"):
            with transaction.atomic():
                first_link.delete()
        self.assertEqual(contradiction.fact_keys, (self.other.key, self.second.key))

        set_contradiction_facts(contradiction, [self.second, self.other])
        self.assertEqual(contradiction.fact_keys, (self.second.key, self.other.key))

    def test_admin_question_inline_persists_through_transactional_service(self) -> None:
        question = GoalQuestion.objects.create(
            semantic_id="question.admin-boundary",
            goal=self.goal,
            fact=self.primary,
            text_ar="تاريخ؟",
            text_en="Date?",
            priority=1,
        )
        formset_class: Any = inlineformset_factory(
            GoalQuestion,
            GoalQuestionResolvedFact,
            formset=QuestionResolvedFactFormSet,
            fields=("fact", "position"),
            extra=0,
        )
        prefix = formset_class.get_default_prefix()
        formset = formset_class(
            data={
                f"{prefix}-TOTAL_FORMS": "2",
                f"{prefix}-INITIAL_FORMS": "0",
                f"{prefix}-MIN_NUM_FORMS": "0",
                f"{prefix}-MAX_NUM_FORMS": "1000",
                f"{prefix}-0-fact": str(self.other.pk),
                f"{prefix}-0-position": "2",
                f"{prefix}-1-fact": str(self.primary.pk),
                f"{prefix}-1-position": "1",
            },
            instance=question,
            prefix=prefix,
        )
        self.assertTrue(formset.is_valid(), formset.errors)

        model_admin = QuestionAdmin(GoalQuestion, AdminSite())
        request = RequestFactory().post("/admin/knowledge/goalquestion/")
        fake_form = cast(Any, SimpleNamespace(instance=question))
        model_admin.save_formset(request, fake_form, formset, False)

        self.assertEqual(question.resolved_fact_keys, (self.primary.key, self.other.key))

    def test_admin_contradiction_inline_persists_through_transactional_service(self) -> None:
        contradiction = GoalContradiction.objects.create(
            semantic_id="contradiction.admin-boundary",
            goal=self.goal,
            condition={
                "op": "all",
                "children": [
                    {"op": "eq", "fact": self.other.key, "value": True},
                    {"op": "eq", "fact": self.second.key, "value": False},
                ],
            },
        )
        formset_class: Any = inlineformset_factory(
            GoalContradiction,
            GoalContradictionFact,
            formset=ContradictionFactFormSet,
            fields=("fact", "position"),
            extra=0,
        )
        prefix = formset_class.get_default_prefix()
        formset = formset_class(
            data={
                f"{prefix}-TOTAL_FORMS": "2",
                f"{prefix}-INITIAL_FORMS": "0",
                f"{prefix}-MIN_NUM_FORMS": "0",
                f"{prefix}-MAX_NUM_FORMS": "1000",
                f"{prefix}-0-fact": str(self.second.pk),
                f"{prefix}-0-position": "2",
                f"{prefix}-1-fact": str(self.other.pk),
                f"{prefix}-1-position": "1",
            },
            instance=contradiction,
            prefix=prefix,
        )
        self.assertTrue(formset.is_valid(), formset.errors)

        model_admin = ContradictionAdmin(GoalContradiction, AdminSite())
        request = RequestFactory().post("/admin/knowledge/goalcontradiction/")
        fake_form = cast(Any, SimpleNamespace(instance=contradiction))
        model_admin.save_formset(request, fake_form, formset, False)

        self.assertEqual(contradiction.fact_keys, (self.other.key, self.second.key))
