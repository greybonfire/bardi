from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date
from unittest.mock import patch

from planning import (
    ChecklistItemSnapshot,
    ContradictionSnapshot,
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
    ProcedureVersionSnapshot,
    QuestionSnapshot,
    SelectionUnsupported,
    ServiceSnapshot,
    plan_stateless,
)


def snapshot(
    *, active: bool = True, derived: bool = False, version: bool = False
) -> KnowledgeSnapshot:
    definitions = {"answer": FactDefinition("answer", "boolean")}
    if derived:
        definitions.update(
            {
                "birth_date": FactDefinition("birth_date", "date"),
                "age_years_on_evaluation_date": FactDefinition(
                    "age_years_on_evaluation_date", "integer", minimum=0, derived=True
                ),
            }
        )
    fact = "age_years_on_evaluation_date" if derived else "answer"
    candidate = ProcedureCandidateSnapshot(
        "procedure",
        LocalizedText("إجراء", "Procedure"),
        Predicate("gte", fact, 18) if derived else Predicate("eq", fact, True),
    )
    question_key = "birth_date" if derived else "answer"
    question = QuestionSnapshot(
        "question", LocalizedText("سؤال", "Question"), 1, question_key, (question_key,)
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
        self.assertIsInstance(plan_stateless(snapshot(derived=True), request()), NextQuestionResult)
        self.assertEqual(
            plan_stateless(snapshot(derived=True), request({"birth_date": date(2000, 9, 1)})),
            InconclusiveResult("no_published_version"),
        )
        self.assertEqual(
            plan_stateless(snapshot(), request({"answer": True})),
            InconclusiveResult("no_published_version"),
        )
        self.assertEqual(
            plan_stateless(snapshot(version=True), request({"answer": True})),
            PlanResult("service", "procedure", "version", LocalizedText("نسخة", "Version")),
        )

    def test_untrusted_official_claim_is_locally_inconclusive(self) -> None:
        base = snapshot(version=True)
        claim = ChecklistItemSnapshot(
            "claim",
            LocalizedText("متطلب", "Requirement"),
            "official_requirement",
            None,
            1,
            0,
            0,
            0,
            None,
            "procedure",
            "",
            None,
            None,
            "needs_reverification",
            None,
            None,
            (),
        )
        version = replace(base.procedure_versions[0], checklist_items=(claim,))
        with_claim = KnowledgeSnapshot(base.fact_definitions, base.services, (version,))
        self.assertEqual(
            plan_stateless(with_claim, request({"answer": True})),
            InconclusiveResult("checklist_trust_inconclusive"),
        )

    def test_preparation_completes_before_candidate_selection(self) -> None:
        with patch(
            "planning.operation.select_procedure",
            return_value=SelectionUnsupported("done", ()),
        ) as selector:
            result = plan_stateless(
                snapshot(derived=True), request({"birth_date": date(2000, 9, 1)})
            )
        self.assertEqual(result, InconclusiveResult("done"))
        prepared = selector.call_args.args[2]
        self.assertEqual(prepared.values["age_years_on_evaluation_date"], 26)
        self.assertEqual(prepared.submitted_keys, frozenset({"birth_date"}))

    def test_invalid_derivation_and_true_contradiction_prevent_selection(self) -> None:
        derived_snapshot = snapshot(derived=True)
        with patch("planning.operation.select_procedure") as selector:
            result = plan_stateless(derived_snapshot, request({"birth_date": date(2027, 1, 1)}))
        self.assertIsInstance(result, InvalidResult)
        selector.assert_not_called()

        ordinary = snapshot()
        contradiction = ContradictionSnapshot(
            "internal",
            Predicate(
                "all",
                children=(
                    Predicate("eq", "answer", True),
                    Predicate("eq", "other", False),
                ),
            ),
            ("answer", "other"),
        )
        service = ordinary.services[0]
        contradictory = KnowledgeSnapshot(
            {**ordinary.fact_definitions, "other": FactDefinition("other", "boolean")},
            (
                ServiceSnapshot(
                    service.semantic_id,
                    service.text,
                    service.candidates,
                    service.questions,
                    (contradiction,),
                    True,
                ),
            ),
        )
        with patch("planning.operation.select_procedure") as selector:
            result = plan_stateless(contradictory, request({"answer": True, "other": False}))
        self.assertIsInstance(result, InvalidResult)
        selector.assert_not_called()

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
