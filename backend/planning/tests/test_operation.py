from __future__ import annotations

import unittest
from datetime import date

from planning import (
    FactDefinition,
    InconclusiveResult,
    InvalidResult,
    KnowledgeSnapshot,
    LocalizedText,
    NextQuestionResult,
    PlanningInput,
    Predicate,
    ProcedureCandidateSnapshot,
    ProcedureVersionSnapshot,
    QuestionSnapshot,
    ServiceSnapshot,
    plan_stateless,
)


def snapshot(
    *, active: bool = True, derived: bool = False, version: bool = False
) -> KnowledgeSnapshot:
    definitions = {
        "answer": FactDefinition("answer", "boolean"),
        "derived": FactDefinition("derived", "boolean", derived=True),
    }
    fact = "derived" if derived else "answer"
    candidate = ProcedureCandidateSnapshot(
        "procedure", LocalizedText("إجراء", "Procedure"), Predicate("eq", fact, True)
    )
    question = QuestionSnapshot(
        "question", LocalizedText("سؤال", "Question"), 1, "answer", ("answer",)
    )
    service = ServiceSnapshot(
        "service", LocalizedText("خدمة", "Service"), (candidate,), (question,), (), active
    )
    versions: tuple[ProcedureVersionSnapshot, ...] = ()
    if version:
        versions = (
            ProcedureVersionSnapshot(
                "version",
                "procedure",
                LocalizedText("نسخة", "Version"),
                Predicate("eq", "answer", True),
                "v1",
                "published",
                None,
                None,
            ),
        )
    return KnowledgeSnapshot(definitions, (service,), versions)


def request(facts: dict[str, object] | None = None) -> PlanningInput:
    return PlanningInput("service", facts or {}, "en", date(2026, 9, 1))


class PublicPlanningOperationTests(unittest.TestCase):
    def test_question_is_safe_explicit_metadata(self) -> None:
        result = plan_stateless(snapshot(), request())
        self.assertIsInstance(result, NextQuestionResult)
        assert isinstance(result, NextQuestionResult)
        self.assertEqual(result.type, "next_question")
        self.assertEqual(result.question.answers[0].key, "answer")

    def test_invalid_facts_are_redacted_to_code_and_path(self) -> None:
        result = plan_stateless(snapshot(), request({"answer": None}))
        self.assertEqual(
            result,
            InvalidResult(result.diagnostics),  # type: ignore[union-attr]
        )
        assert isinstance(result, InvalidResult)
        self.assertEqual(result.diagnostics[0].code, "invalid_fact_value")
        self.assertEqual(result.diagnostics[0].path, ("facts", "answer"))

    def test_semantic_and_staged_inconclusive_boundaries(self) -> None:
        unknown = PlanningInput("missing", {}, "en", date(2026, 9, 1))
        self.assertEqual(plan_stateless(snapshot(), unknown), InconclusiveResult("unknown_service"))
        self.assertEqual(
            plan_stateless(snapshot(active=False), request()),
            InconclusiveResult("inactive_service"),
        )
        self.assertEqual(
            plan_stateless(snapshot(derived=True), request()),
            InconclusiveResult("case_preparation_unavailable"),
        )
        self.assertEqual(
            plan_stateless(snapshot(), request({"answer": True})),
            InconclusiveResult("no_published_version"),
        )
        self.assertEqual(
            plan_stateless(snapshot(version=True), request({"answer": True})),
            InconclusiveResult("plan_assembly_unavailable"),
        )

    def test_repeated_calls_are_deterministic_and_input_is_copied(self) -> None:
        facts: dict[str, object] = {}
        planning_input = PlanningInput("service", facts, "en", date(2026, 9, 1))
        facts["answer"] = True
        self.assertEqual(
            plan_stateless(snapshot(), planning_input),
            plan_stateless(snapshot(), planning_input),
        )


if __name__ == "__main__":
    unittest.main()
