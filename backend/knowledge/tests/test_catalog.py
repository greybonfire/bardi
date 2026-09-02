from __future__ import annotations

from typing import Any, ClassVar

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.forms.models import inlineformset_factory
from django.test import TestCase, TransactionTestCase
from planning.facts import FACT_DEFINITIONS

from knowledge.domain import compatibility_errors, load_fact_definitions
from knowledge.forms import QuestionResolvedFactFormSet
from knowledge.models import (
    FactDefinition,
    Goal,
    GoalContradiction,
    GoalProcedureCandidate,
    GoalQuestion,
    GoalQuestionResolvedFact,
    Procedure,
)
from knowledge.services import set_contradiction_facts, set_question_resolved_facts


class CatalogModelTests(TestCase):
    goal: ClassVar[Goal]
    other_goal: ClassVar[Goal]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.goal = Goal.objects.create(semantic_id="goal.one", text_ar="هدف", text_en="Goal")
        cls.other_goal = Goal.objects.create(
            semantic_id="goal_two", text_ar="هدف ثان", text_en="Other"
        )

    def test_seed_exactly_matches_pure_registry(self) -> None:
        self.assertEqual(FactDefinition.objects.count(), 39)
        self.assertEqual(load_fact_definitions(), FACT_DEFINITIONS)
        self.assertEqual(compatibility_errors(FactDefinition.objects.all()), ())

    def test_nonblank_validation(self) -> None:
        with self.assertRaises(ValidationError):
            Goal(semantic_id=" ", text_ar=" ", text_en=" ").full_clean()

    def test_candidate_requires_procedure_owner_and_database_rule(self) -> None:
        procedure = Procedure.objects.create(
            semantic_id="procedure.one",
            text_ar="إجراء",
            text_en="Procedure",
            primary_goal=self.goal,
        )
        candidate = GoalProcedureCandidate(
            goal=self.other_goal,
            procedure=procedure,
            selection_predicate={"op": "eq", "fact": "is_student", "value": True},
        )
        with self.assertRaises(ValidationError):
            candidate.full_clean()
        candidate.goal = self.goal
        candidate.selection_predicate = {"op": "eq", "fact": "missing", "value": True}
        with self.assertRaises(ValidationError) as caught:
            candidate.full_clean()
        self.assertIn("unsupported_rule_fact:missing", str(caught.exception))

    def test_procedure_cannot_be_reassigned_away_from_candidate_goal(self) -> None:
        procedure = Procedure.objects.create(
            semantic_id="procedure.owner",
            text_ar="إجراء",
            text_en="Procedure",
            primary_goal=self.goal,
        )
        GoalProcedureCandidate.objects.create(
            goal=self.goal,
            procedure=procedure,
            selection_predicate={"op": "exists", "fact": "is_student"},
        )
        procedure.primary_goal = self.other_goal
        with self.assertRaises(ValidationError):
            procedure.save()

    def test_question_resolution_semantics_and_order(self) -> None:
        primary = FactDefinition.objects.get(key="national_id_expiry_date")
        equivalent = FactDefinition.objects.get(key="is_student")
        derived = FactDefinition.objects.get(key="card_expired_before_evaluation_date")
        question = GoalQuestion.objects.create(
            semantic_id="question.expiry",
            goal=self.goal,
            fact=primary,
            text_ar="تاريخ؟",
            text_en="Date?",
            priority=1,
        )
        self.assertEqual(question.resolved_fact_keys, (primary.key,))
        set_question_resolved_facts(question, [equivalent, primary])
        self.assertEqual(question.resolved_fact_keys, (equivalent.key, primary.key))
        with self.assertRaises(ValidationError):
            set_question_resolved_facts(question, [primary, derived])
        self.assertEqual(question.resolved_fact_keys, (equivalent.key, primary.key))

    def test_question_resolved_fact_admin_formset_rejects_derived_fact(self) -> None:
        primary = FactDefinition.objects.get(key="national_id_expiry_date")
        derived = FactDefinition.objects.get(key="card_expired_before_evaluation_date")
        question = GoalQuestion.objects.create(
            semantic_id="question.admin",
            goal=self.goal,
            fact=primary,
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
                f"{prefix}-0-fact": str(primary.pk),
                f"{prefix}-0-position": "1",
                f"{prefix}-1-fact": str(derived.pk),
                f"{prefix}-1-position": "2",
            },
            instance=question,
            prefix=prefix,
        )
        self.assertFalse(formset.is_valid())
        self.assertIn("source Facts only", str(formset.errors) + str(formset.non_form_errors()))
        with self.assertRaises(ValidationError):
            GoalQuestionResolvedFact.objects.create(question=question, fact=derived, position=1)
        self.assertFalse(question.resolved_fact_links.exists())

    def test_ordinary_orm_paths_run_catalog_validation(self) -> None:
        procedure = Procedure.objects.create(
            semantic_id="procedure.orm-validation",
            text_ar="إجراء",
            text_en="Procedure",
            primary_goal=self.goal,
        )
        with self.assertRaises(ValidationError):
            GoalProcedureCandidate.objects.create(
                goal=self.other_goal,
                procedure=procedure,
                selection_predicate={"op": "exists", "fact": "is_student"},
            )
        with self.assertRaises(ValidationError):
            GoalProcedureCandidate.objects.create(
                goal=self.goal,
                procedure=procedure,
                selection_predicate={"op": "unsupported"},
            )

        derived = FactDefinition.objects.get(key="card_expired_before_evaluation_date")
        with self.assertRaises(ValidationError):
            GoalQuestion.objects.create(
                semantic_id="question.derived",
                goal=self.goal,
                fact=derived,
                text_ar="سؤال؟",
                text_en="Question?",
                priority=1,
            )

        with self.assertRaises(ValidationError):
            GoalContradiction.objects.create(
                semantic_id="contradiction.malformed",
                goal=self.goal,
                condition={"op": "unsupported"},
            )

        self.assertFalse(GoalProcedureCandidate.objects.filter(procedure=procedure).exists())
        self.assertFalse(GoalQuestion.objects.filter(semantic_id="question.derived").exists())
        self.assertFalse(
            GoalContradiction.objects.filter(semantic_id="contradiction.malformed").exists()
        )

    def test_contradiction_exact_source_fact_set(self) -> None:
        first = FactDefinition.objects.get(key="is_student")
        second = FactDefinition.objects.get(key="has_current_enrollment_certificate")
        contradiction = GoalContradiction.objects.create(
            semantic_id="contradiction.student",
            goal=self.goal,
            condition={
                "op": "all",
                "children": [
                    {"op": "eq", "fact": first.key, "value": True},
                    {"op": "eq", "fact": second.key, "value": False},
                ],
            },
        )
        set_contradiction_facts(contradiction, [second, first])
        self.assertEqual(contradiction.fact_keys, (second.key, first.key))
        with self.assertRaises(ValidationError):
            set_contradiction_facts(contradiction, [first])
        self.assertEqual(contradiction.fact_keys, (second.key, first.key))


class PublishedFactTriggerTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self) -> None:
        FactDefinition.objects.get_or_create(
            key="is_student",
            defaults={"kind": "boolean", "enum_values": [], "is_published": True},
        )

    def test_model_and_database_paths_cannot_mutate_or_delete_published_fact(self) -> None:
        fact = FactDefinition.objects.get(key="is_student")
        fact.derived = True
        with self.assertRaises(ValidationError):
            fact.save()
        with self.assertRaises(DatabaseError), transaction.atomic():
            FactDefinition.objects.filter(pk=fact.pk).update(derived=True)
        with self.assertRaises(DatabaseError), transaction.atomic():
            FactDefinition.objects.filter(pk=fact.pk).delete()
        self.assertFalse(FactDefinition.objects.get(pk=fact.pk).derived)

    def test_nonsemantic_noop_update_is_allowed(self) -> None:
        fact = FactDefinition.objects.get(key="is_student")
        self.assertEqual(FactDefinition.objects.filter(pk=fact.pk).update(key=fact.key), 1)
