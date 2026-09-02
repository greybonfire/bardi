from __future__ import annotations

from unittest.mock import PropertyMock, patch

from django.test import TestCase
from planning import PreparedFacts, SelectionQuestion, select_procedure

from knowledge.domain import KnowledgeSnapshotLoadError, load_knowledge_snapshot
from knowledge.models import (
    FactDefinition,
    Procedure,
    Service,
    ServiceContradiction,
    ServiceProcedureCandidate,
    ServiceQuestion,
)
from knowledge.services import set_contradiction_facts, set_question_resolved_facts


class KnowledgeSnapshotTests(TestCase):
    def setUp(self) -> None:
        self.service = Service.objects.create(
            semantic_id="snapshot.service", text_ar="خدمة", text_en="Service"
        )
        source_a = FactDefinition.objects.get(key="is_student")
        source_b = FactDefinition.objects.get(key="has_current_enrollment_certificate")
        derived = FactDefinition.objects.get(key="age_years_on_evaluation_date")

        for semantic_id, rule in (
            ("snapshot.procedure.z", {"op": "eq", "fact": source_a.key, "value": True}),
            ("snapshot.procedure.a", {"op": "gte", "fact": derived.key, "value": 18}),
        ):
            procedure = Procedure.objects.create(
                semantic_id=semantic_id,
                text_ar=f"إجراء {semantic_id}",
                text_en=f"Procedure {semantic_id}",
                primary_service=self.service,
            )
            ServiceProcedureCandidate.objects.create(
                service=self.service, procedure=procedure, selection_predicate=rule
            )

        self.fallback_question = ServiceQuestion.objects.create(
            semantic_id="snapshot.question.z",
            service=self.service,
            fact=source_b,
            text_ar="سؤال ب",
            text_en="Question B",
            priority=3,
        )
        self.explicit_question = ServiceQuestion.objects.create(
            semantic_id="snapshot.question.a",
            service=self.service,
            fact=source_a,
            text_ar="سؤال أ",
            text_en="Question A",
            priority=2,
        )
        set_question_resolved_facts(self.explicit_question, (source_b, source_a))

        self.contradiction = ServiceContradiction.objects.create(
            semantic_id="snapshot.contradiction",
            service=self.service,
            condition={
                "op": "all",
                "children": [
                    {"op": "eq", "fact": source_a.key, "value": True},
                    {"op": "eq", "fact": source_b.key, "value": False},
                ],
            },
        )
        set_contradiction_facts(self.contradiction, (source_b, source_a))

    def test_loader_materializes_decodes_and_preserves_declared_order(self) -> None:
        with (
            patch.object(
                ServiceQuestion,
                "resolved_fact_keys",
                new_callable=PropertyMock,
                side_effect=AssertionError("lazy question property used"),
            ),
            patch.object(
                ServiceContradiction,
                "fact_keys",
                new_callable=PropertyMock,
                side_effect=AssertionError("lazy contradiction property used"),
            ),
        ):
            snapshot = load_knowledge_snapshot()

        service = next(
            item for item in snapshot.services if item.semantic_id == self.service.semantic_id
        )
        self.assertEqual(
            tuple(item.procedure_semantic_id for item in service.candidates),
            ("snapshot.procedure.a", "snapshot.procedure.z"),
        )
        self.assertEqual(
            tuple(item.semantic_id for item in service.questions),
            ("snapshot.question.a", "snapshot.question.z"),
        )
        self.assertEqual(
            service.questions[0].resolved_fact_keys,
            ("has_current_enrollment_certificate", "is_student"),
        )
        self.assertEqual(
            service.questions[1].resolved_fact_keys,
            ("has_current_enrollment_certificate",),
        )
        self.assertEqual(
            service.contradictions[0].fact_keys,
            ("has_current_enrollment_certificate", "is_student"),
        )
        self.assertEqual(
            service.candidates[0].selection_predicate.fact, "age_years_on_evaluation_date"
        )

    def test_selection_and_complete_result_traversal_issue_no_queries(self) -> None:
        snapshot = load_knowledge_snapshot()
        prepared = PreparedFacts(
            {},
            frozenset(),
            {"age_years_on_evaluation_date": frozenset({"is_student"})},
        )
        with self.assertNumQueries(0):
            outcome = select_procedure(snapshot, self.service.semantic_id, prepared)
            self.assertIsInstance(outcome, SelectionQuestion)
            assert isinstance(outcome, SelectionQuestion)
            self.assertEqual(outcome.question.semantic_id, "snapshot.question.a")
            for candidate_evaluation in outcome.evaluations:
                evaluation = candidate_evaluation.evaluation
                _ = evaluation.value
                _ = evaluation.missing_facts
                stack = [evaluation.trace]
                while stack:
                    trace = stack.pop()
                    _ = trace.fact_key
                    _ = trace.actual_value
                    stack.extend(trace.children)

    def test_loaded_snapshot_is_detached_from_later_database_changes(self) -> None:
        snapshot = load_knowledge_snapshot()
        original = next(
            item for item in snapshot.services if item.semantic_id == self.service.semantic_id
        )
        Service.objects.filter(pk=self.service.pk).update(text_en="Changed")
        set_question_resolved_facts(self.explicit_question, ())
        ServiceProcedureCandidate.objects.filter(service=self.service).delete()

        self.assertEqual(original.text.en, "Service")
        self.assertEqual(len(original.candidates), 2)
        self.assertEqual(
            original.questions[0].resolved_fact_keys,
            ("has_current_enrollment_certificate", "is_student"),
        )

    def test_malformed_stored_rule_fails_with_stable_owner_and_diagnostics(self) -> None:
        ServiceProcedureCandidate.objects.filter(
            procedure__semantic_id="snapshot.procedure.a"
        ).update(selection_predicate={"op": "broken"})
        with self.assertRaises(KnowledgeSnapshotLoadError) as caught:
            load_knowledge_snapshot()
        self.assertEqual(
            caught.exception.owner_ids,
            ("candidate:snapshot.service:snapshot.procedure.a",),
        )
        self.assertEqual(
            tuple(
                diagnostic.code for diagnostic in caught.exception.rule_diagnostics[0].diagnostics
            ),
            ("unsupported_rule_operator:broken",),
        )
