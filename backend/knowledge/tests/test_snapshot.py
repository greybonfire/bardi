from __future__ import annotations

from datetime import date
from unittest.mock import PropertyMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from planning import (
    PreparedFacts,
    ProcedureVersionUnavailable,
    SelectionQuestion,
    resolve_procedure_version,
    select_procedure,
)

from knowledge.domain import (
    KnowledgeSnapshotLoadError,
    decode_stored_rule,
    load_consistent_knowledge_snapshot,
    load_knowledge_snapshot,
)
from knowledge.models import (
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceContradiction,
    ServiceProcedureCandidate,
    ServiceQuestion,
)
from knowledge.publication import publish_procedure_version, withdraw_procedure_version
from knowledge.services import set_contradiction_facts, set_question_resolved_facts


class KnowledgeSnapshotTests(TestCase):
    def setUp(self) -> None:
        self.actor = get_user_model().objects.create_user(username="snapshot-publisher")
        self.service = Service.objects.create(
            semantic_id="snapshot.service", text_ar="خدمة", text_en="Service", is_active=True
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

        procedure = Procedure.objects.get(semantic_id="snapshot.procedure.a")
        self.version = ProcedureVersion.objects.create(
            semantic_id="snapshot.version.a",
            procedure=procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability={"op": "eq", "fact": source_a.key, "value": True},
        )

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
        publish_procedure_version(self.version.pk, actor=self.actor)
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
        self.assertTrue(service.is_active)
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
        self.assertEqual(
            tuple(item.semantic_id for item in snapshot.procedure_versions),
            ("snapshot.version.a",),
        )
        self.assertEqual(snapshot.procedure_versions[0].applicability.fact, "is_student")

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

    def test_version_resolution_and_traversal_issue_no_queries(self) -> None:
        snapshot = load_knowledge_snapshot()
        with self.assertNumQueries(0):
            outcome = resolve_procedure_version(snapshot, "snapshot.procedure.a", date(2025, 1, 1))
            self.assertEqual(outcome, ProcedureVersionUnavailable("no_published_version", ()))
            _ = outcome.upcoming

    def test_loaded_snapshot_is_detached_from_later_database_changes(self) -> None:
        publish_procedure_version(self.version.pk, actor=self.actor)
        snapshot = load_knowledge_snapshot()
        original = next(
            item for item in snapshot.services if item.semantic_id == self.service.semantic_id
        )
        Service.objects.filter(pk=self.service.pk).update(text_en="Changed")
        set_question_resolved_facts(self.explicit_question, ())
        ServiceProcedureCandidate.objects.filter(service=self.service).delete()
        withdraw_procedure_version(self.version.pk, actor=self.actor)

        self.assertEqual(original.text.en, "Service")
        self.assertEqual(len(original.candidates), 2)
        self.assertEqual(
            original.questions[0].resolved_fact_keys,
            ("has_current_enrollment_certificate", "is_student"),
        )
        self.assertEqual(snapshot.procedure_versions[0].text.en, "Version")
        self.assertEqual(snapshot.procedure_versions[0].state, "published")

    def test_consistent_loader_rejects_an_already_active_transaction(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "outermost transaction"):
            load_consistent_knowledge_snapshot()

    def test_incomplete_drafts_are_excluded_from_the_planning_snapshot(self) -> None:
        ProcedureVersion.objects.filter(pk=self.version.pk).update(applicability={"op": "broken"})
        snapshot = load_knowledge_snapshot()
        self.assertEqual(snapshot.procedure_versions, ())

    def test_active_question_with_unpublished_fact_fails_until_fact_is_published(self) -> None:
        hidden = FactDefinition.objects.create(
            key="snapshot.hidden.question", kind=FactDefinition.Kind.BOOLEAN
        )
        ServiceQuestion.objects.create(
            semantic_id="snapshot.question.hidden",
            service=self.service,
            fact=hidden,
            text_ar="سؤال مخفي",
            text_en="Hidden question",
            priority=4,
        )

        with self.assertRaises(KnowledgeSnapshotLoadError) as caught:
            load_knowledge_snapshot()
        self.assertEqual(caught.exception.owner_ids, ("question:snapshot.question.hidden",))

        hidden.is_published = True
        hidden.save()
        snapshot = load_knowledge_snapshot()
        self.assertIn(hidden.key, snapshot.fact_definitions)

    def test_active_contradiction_with_unpublished_fact_fails_until_fact_is_published(
        self,
    ) -> None:
        hidden = FactDefinition.objects.create(
            key="snapshot.hidden.contradiction", kind=FactDefinition.Kind.BOOLEAN
        )
        published = FactDefinition.objects.get(key="is_student")
        contradiction = ServiceContradiction.objects.create(
            semantic_id="snapshot.contradiction.hidden",
            service=self.service,
            condition={
                "op": "all",
                "children": [
                    {"op": "eq", "fact": published.key, "value": True},
                    {"op": "eq", "fact": hidden.key, "value": False},
                ],
            },
        )
        set_contradiction_facts(contradiction, (published, hidden))

        with self.assertRaises(KnowledgeSnapshotLoadError) as caught:
            load_knowledge_snapshot()
        self.assertEqual(
            caught.exception.owner_ids, ("contradiction:snapshot.contradiction.hidden",)
        )

        hidden.is_published = True
        hidden.save()
        snapshot = load_knowledge_snapshot()
        self.assertIn(hidden.key, snapshot.fact_definitions)

    def test_public_snapshot_excludes_unpublished_fact_without_active_dependencies(self) -> None:
        hidden = FactDefinition.objects.create(
            key="snapshot.hidden.unused", kind=FactDefinition.Kind.BOOLEAN
        )
        snapshot = load_knowledge_snapshot()
        self.assertNotIn(hidden.key, snapshot.fact_definitions)

        # Draft authoring still decodes against the complete internal Fact registry.
        authored = decode_stored_rule({"op": "eq", "fact": hidden.key, "value": True})
        self.assertIsNotNone(authored.predicate)
        self.assertEqual(authored.diagnostics, ())

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
