from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, timedelta

from planning import (
    AuthoritySnapshot,
    ChecklistItemSnapshot,
    EvidenceLinkSnapshot,
    FactDefinition,
    InconclusiveResult,
    InvalidResult,
    KnowledgeSnapshot,
    LocalizedText,
    NextQuestionResult,
    PlanningInput,
    PlanResult,
    Predicate,
    ProcedureCandidateSnapshot,
    ProcedureServicePointAssociationSnapshot,
    ProcedureVersionSnapshot,
    QuestionSnapshot,
    ServicePointSnapshot,
    ServicePointVersionSnapshot,
    ServiceSnapshot,
    SourceSnapshot,
    StepSnapshot,
    plan_stateless,
)
from planning.facts import PreparedFacts
from planning.routing import select_service_points

TODAY = date(2026, 9, 5)


def _evidence(source_id: str = "source") -> tuple[EvidenceLinkSnapshot, ...]:
    source = SourceSnapshot(
        source_id,
        AuthoritySnapshot("authority", LocalizedText("جهة", "Authority")),
        "Official source",
        "https://example.test/source",
        "official",
        TODAY,
    )
    return (
        EvidenceLinkSnapshot(
            "Passage",
            "Section 1",
            "Applies to the procedure",
            "supports",
            "current",
            (source,),
            verified_on=TODAY,
        ),
    )


def _question(question_id: str, fact_key: str, priority: int = 10) -> QuestionSnapshot:
    return QuestionSnapshot(
        question_id,
        LocalizedText("سؤال", "Question"),
        priority,
        fact_key,
        (fact_key,),
    )


def _planning_snapshot(
    *,
    version_applicability: Predicate | None = None,
    checklist_items: tuple[ChecklistItemSnapshot, ...] = (),
    steps: tuple[StepSnapshot, ...] = (),
    questions: tuple[QuestionSnapshot, ...] = (),
) -> KnowledgeSnapshot:
    definitions = {
        "selected": FactDefinition("selected", "boolean"),
        "version_applies": FactDefinition("version_applies", "boolean"),
        "checklist_applies": FactDefinition("checklist_applies", "boolean"),
        "step_applies": FactDefinition("step_applies", "boolean"),
        "shared_applies": FactDefinition("shared_applies", "boolean"),
    }
    candidate = ProcedureCandidateSnapshot(
        "procedure",
        LocalizedText("إجراء", "Procedure"),
        Predicate("eq", "selected", True),
    )
    service = ServiceSnapshot(
        "service",
        LocalizedText("خدمة", "Service"),
        (candidate,),
        questions,
        (),
        True,
    )
    version = ProcedureVersionSnapshot(
        "procedure.v1",
        "procedure",
        LocalizedText("نسخة", "Version"),
        version_applicability or Predicate("eq", "selected", True),
        "v1",
        "published",
        None,
        None,
        checklist_items=checklist_items,
        steps=steps,
    )
    return KnowledgeSnapshot(definitions, (service,), (version,))


def _request(**facts: object) -> PlanningInput:
    return PlanningInput("service", facts, "en", TODAY)


def _checklist(
    *,
    fact_key: str = "checklist_applies",
    classification: str = "official_requirement",
    verification_state: str = "current",
    evidence: tuple[EvidenceLinkSnapshot, ...] | None = None,
) -> ChecklistItemSnapshot:
    return ChecklistItemSnapshot(
        "requirement",
        LocalizedText("متطلب", "Requirement"),
        classification,
        None,
        1,
        0,
        0,
        1,
        Predicate("eq", fact_key, True),
        "procedure",
        "",
        None,
        None,
        verification_state,  # type: ignore[arg-type]
        TODAY,
        None,
        _evidence("checklist-source") if evidence is None else evidence,
    )


def _step(
    *,
    fact_key: str = "step_applies",
    verification_state: str = "current",
    evidence: tuple[EvidenceLinkSnapshot, ...] | None = None,
) -> StepSnapshot:
    return StepSnapshot(
        "step",
        LocalizedText("خطوة", "Step"),
        "submit",
        1,
        1,
        Predicate("eq", fact_key, True),
        "procedure",
        None,
        None,
        None,
        verification_state,  # type: ignore[arg-type]
        TODAY,
        None,
        _evidence("step-source") if evidence is None else evidence,
    )


class ConsequentialQuestionRegressionTests(unittest.TestCase):
    """Durable coverage for the question phases added by issues #115 and #116."""

    def test_version_applicability_question_progresses_and_fails_closed(self) -> None:
        knowledge = _planning_snapshot(
            version_applicability=Predicate("eq", "version_applies", True),
            questions=(_question("version-question", "version_applies"),),
        )

        unanswered = plan_stateless(knowledge, _request(selected=True))
        self.assertIsInstance(unanswered, NextQuestionResult)
        assert isinstance(unanswered, NextQuestionResult)
        self.assertEqual(unanswered.question.id, "version-question")

        included = plan_stateless(knowledge, _request(selected=True, version_applies=True))
        self.assertIsInstance(included, PlanResult)

        excluded = plan_stateless(knowledge, _request(selected=True, version_applies=False))
        self.assertEqual(excluded, InconclusiveResult("procedure_version_not_applicable"))

        uncovered = replace(knowledge, services=(replace(knowledge.services[0], questions=()),))
        invalid = plan_stateless(uncovered, _request(selected=True))
        self.assertIsInstance(invalid, InvalidResult)
        assert isinstance(invalid, InvalidResult)
        self.assertEqual(invalid.diagnostics[0].code, "knowledge_configuration_invalid")

    def test_checklist_question_is_asked_only_for_usable_official_material(self) -> None:
        knowledge = _planning_snapshot(
            checklist_items=(_checklist(),),
            questions=(_question("checklist-question", "checklist_applies"),),
        )

        unanswered = plan_stateless(knowledge, _request(selected=True))
        self.assertIsInstance(unanswered, NextQuestionResult)
        assert isinstance(unanswered, NextQuestionResult)
        self.assertEqual(unanswered.question.id, "checklist-question")

        included = plan_stateless(knowledge, _request(selected=True, checklist_applies=True))
        self.assertIsInstance(included, PlanResult)
        assert isinstance(included, PlanResult)
        self.assertEqual([item.id for item in included.checklist_items], ["requirement"])

        excluded = plan_stateless(knowledge, _request(selected=True, checklist_applies=False))
        self.assertIsInstance(excluded, PlanResult)
        assert isinstance(excluded, PlanResult)
        self.assertEqual(excluded.checklist_items, ())

        unusable = _planning_snapshot(
            checklist_items=(_checklist(evidence=()),),
            questions=(_question("checklist-question", "checklist_applies"),),
        )
        self.assertEqual(
            plan_stateless(unusable, _request(selected=True)),
            InconclusiveResult("checklist_applicability_unknown"),
        )

    def test_optional_practical_preparation_unknown_does_not_block_or_ask(self) -> None:
        knowledge = _planning_snapshot(
            checklist_items=(_checklist(classification="practical_preparation"),),
            questions=(_question("checklist-question", "checklist_applies"),),
        )

        result = plan_stateless(knowledge, _request(selected=True))
        self.assertIsInstance(result, PlanResult)
        assert isinstance(result, PlanResult)
        self.assertEqual(result.checklist_items, ())

    def test_step_question_and_shared_fact_progress_without_duplicate_questioning(self) -> None:
        shared = "shared_applies"
        knowledge = _planning_snapshot(
            checklist_items=(_checklist(fact_key=shared),),
            steps=(_step(fact_key=shared),),
            questions=(_question("shared-question", shared),),
        )

        unanswered = plan_stateless(knowledge, _request(selected=True))
        self.assertIsInstance(unanswered, NextQuestionResult)
        assert isinstance(unanswered, NextQuestionResult)
        self.assertEqual(unanswered.question.id, "shared-question")

        answered = plan_stateless(knowledge, _request(selected=True, shared_applies=True))
        self.assertIsInstance(answered, PlanResult)
        assert isinstance(answered, PlanResult)
        self.assertEqual([item.id for item in answered.checklist_items], ["requirement"])
        self.assertEqual([item.id for item in answered.steps], ["step"])

        false_answer = plan_stateless(knowledge, _request(selected=True, shared_applies=False))
        self.assertIsInstance(false_answer, PlanResult)
        assert isinstance(false_answer, PlanResult)
        self.assertEqual(false_answer.checklist_items, ())
        self.assertEqual(false_answer.steps, ())

    def test_unusable_unknown_step_retains_inconclusive_fallback_instead_of_asking(self) -> None:
        knowledge = _planning_snapshot(
            steps=(_step(evidence=()),),
            questions=(_question("step-question", "step_applies"),),
        )
        self.assertEqual(
            plan_stateless(knowledge, _request(selected=True)),
            InconclusiveResult("step_applicability_unknown"),
        )


class RoutingStatusRegressionTests(unittest.TestCase):
    """Cover the empty-destination paths corrected by issue #111 / PR #114."""

    def association(
        self,
        semantic_id: str,
        *,
        predicate: Predicate | None = None,
        effective_from: date | None = TODAY,
        effective_to: date | None = TODAY,
    ) -> ProcedureServicePointAssociationSnapshot:
        return ProcedureServicePointAssociationSnapshot(
            semantic_id,
            "point.v1",
            predicate or Predicate("eq", "route", True),
            effective_from,
            effective_to,
            "current",
            TODAY,
            None,
            _evidence(f"association-{semantic_id}"),
        )

    def snapshot(
        self, associations: tuple[ProcedureServicePointAssociationSnapshot, ...]
    ) -> tuple[KnowledgeSnapshot, ProcedureVersionSnapshot]:
        version = ProcedureVersionSnapshot(
            "procedure.v1",
            "procedure",
            LocalizedText("إجراء", "Procedure"),
            Predicate("eq", "route", True),
            "v1",
            "published",
            None,
            None,
            service_point_associations=associations,
        )
        material = ServicePointVersionSnapshot(
            "point.v1",
            "point",
            LocalizedText("عنوان", "Address"),
            "available",
            TODAY,
            None,
            "current",
            TODAY,
            None,
            _evidence("material-source"),
        )
        snapshot = KnowledgeSnapshot(
            {},
            (),
            (version,),
            (ServicePointSnapshot("point", LocalizedText("نقطة", "Point")),),
            (material,),
        )
        return snapshot, version

    def select(
        self, associations: tuple[ProcedureServicePointAssociationSnapshot, ...]
    ):
        snapshot, version = self.snapshot(associations)
        return select_service_points(
            snapshot,
            version,
            PreparedFacts({"route": True}, frozenset({"route"}), {}),
            TODAY,
        )

    def test_empty_routing_after_expired_future_or_false_is_unresolved(self) -> None:
        cases = (
            self.association("expired", effective_to=TODAY - timedelta(days=1)),
            self.association("future", effective_from=TODAY + timedelta(days=1)),
            self.association("false", predicate=Predicate("eq", "route", False)),
        )
        for association in cases:
            with self.subTest(association=association.semantic_id):
                result = self.select((association,))
                self.assertEqual(result.status, "unresolved")
                self.assertEqual(result.destinations, ())

    def test_usable_route_plus_benign_skips_stays_resolved(self) -> None:
        selected = self.association("selected")
        skipped = (
            self.association("expired", effective_to=TODAY - timedelta(days=1)),
            self.association("future", effective_from=TODAY + timedelta(days=1)),
            self.association("false", predicate=Predicate("eq", "route", False)),
        )
        for association in skipped:
            with self.subTest(association=association.semantic_id):
                result = self.select((selected, association))
                self.assertEqual(result.status, "resolved")
                self.assertEqual(
                    [item.association_id for item in result.destinations],
                    ["selected"],
                )


if __name__ == "__main__":
    unittest.main()
