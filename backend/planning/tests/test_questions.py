"""Characterize both existing picker policies before consolidating their implementation.

Malformed catalog/preparation handoffs below intentionally bypass publication validation;
these are compatibility observations, not claims that such knowledge can be published.
"""

from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from planning import (
    CandidateEvaluation,
    FactDefinition,
    KnowledgeSnapshot,
    LocalizedText,
    Predicate,
    PreparedFacts,
    ProcedureCandidateSnapshot,
    QuestionSnapshot,
    SelectionConfigurationDefect,
    SelectionQuestion,
    ServiceSnapshot,
    TruthValue,
    select_procedure,
)
from planning.evaluator import Evaluation, EvaluationTrace, evaluate
from planning.questions import ConsequentialQuestion, pick_consequential_question


def question(
    semantic_id: str = "q", *, priority: int = 1, answers: tuple[str, ...] = ("a",)
) -> QuestionSnapshot:
    return QuestionSnapshot(semantic_id, LocalizedText("سؤال", semantic_id), priority, "a", answers)


def knowledge(
    missing: frozenset[str], questions: tuple[QuestionSnapshot, ...] = ()
) -> KnowledgeSnapshot:
    return KnowledgeSnapshot(
        {
            "a": FactDefinition("a", "boolean"),
            "b": FactDefinition("b", "boolean"),
            "z": FactDefinition("z", "boolean"),
            "derived_a": FactDefinition("derived_a", "boolean", derived=True),
            "derived_z": FactDefinition("derived_z", "boolean", derived=True),
        },
        (
            ServiceSnapshot(
                "service",
                LocalizedText("خدمة", "Service"),
                tuple(
                    ProcedureCandidateSnapshot(
                        key, LocalizedText("إجراء", key), Predicate("eq", key, True)
                    )
                    for key in sorted(missing, reverse=True)
                ),
                questions,
                (),
                True,
            ),
        ),
    )


class MissingFactPolicyCharacterizationTests(unittest.TestCase):
    def assert_policies(
        self,
        snapshot: KnowledgeSnapshot,
        missing: frozenset[str],
        prepared: PreparedFacts,
        selection_expected: QuestionSnapshot | tuple[str, ...],
        later_expected: QuestionSnapshot | tuple[str, ...],
    ) -> None:
        selection = select_procedure(snapshot, "service", prepared)
        expected_evaluations = tuple(
            CandidateEvaluation(
                item.procedure_semantic_id,
                evaluate(
                    item.selection_predicate,
                    prepared.values,
                    submitted_keys=prepared.submitted_keys,
                ),
            )
            for item in sorted(
                snapshot.services[0].candidates, key=lambda item: item.procedure_semantic_id
            )
        )
        if isinstance(selection_expected, QuestionSnapshot):
            self.assertEqual(selection, SelectionQuestion(selection_expected, expected_evaluations))
            assert isinstance(selection, SelectionQuestion)
            self.assertIs(selection.question, selection_expected)
        else:
            self.assertEqual(
                selection, SelectionConfigurationDefect(selection_expected, expected_evaluations)
            )
        later = pick_consequential_question(
            snapshot,
            snapshot.services[0],
            prepared,
            missing,
            diagnostic_prefix="missing_phase_question",
        )
        if isinstance(later_expected, QuestionSnapshot):
            self.assertEqual(later, ConsequentialQuestion(later_expected))
            self.assertIs(later.question, later_expected)
        else:
            self.assertEqual(later, ConsequentialQuestion(None, later_expected))

    def test_unknown_definition_is_legacy_source_but_later_unknown_fact(self) -> None:
        missing = frozenset({"unknown"})
        authored = question(answers=("unknown",))
        for questions, expected in (
            ((authored,), authored),
            ((), ("missing_procedure_selection_question:unknown",)),
        ):
            with self.subTest(covered=bool(questions)):
                self.assert_policies(
                    knowledge(missing, questions),
                    missing,
                    PreparedFacts({}, frozenset(), {}),
                    expected,
                    ("unknown_fact:unknown",),
                )

    def test_undefined_source_dependency_is_accepted_only_by_selection(self) -> None:
        missing = frozenset({"derived_a"})
        authored = question(answers=("unknown",))
        self.assert_policies(
            knowledge(missing, (authored,)),
            missing,
            PreparedFacts({}, frozenset(), {"derived_a": frozenset({"unknown"})}),
            authored,
            ("missing_source_dependencies:derived_a",),
        )

    def test_absent_empty_and_derived_dependencies_precede_source_coverage(self) -> None:
        missing = frozenset({"derived_z", "derived_a", "z"})
        cases: tuple[dict[str, frozenset[str]], ...] = (
            {},
            {"derived_a": frozenset(), "derived_z": frozenset()},
            {"derived_a": frozenset({"derived_z"}), "derived_z": frozenset({"a", "derived_a"})},
        )
        for dependencies in cases:
            with self.subTest(dependencies=dependencies):
                expected = (
                    "missing_source_dependencies:derived_a",
                    "missing_source_dependencies:derived_z",
                )
                self.assert_policies(
                    knowledge(missing),
                    missing,
                    PreparedFacts({}, frozenset(), dependencies),
                    expected,
                    expected,
                )

    def test_later_expansion_defects_are_sorted_together_before_coverage(self) -> None:
        missing = frozenset({"unknown_z", "derived_a", "unknown_a", "z"})
        snapshot = knowledge(missing)
        self.assertEqual(
            pick_consequential_question(
                snapshot,
                snapshot.services[0],
                PreparedFacts({}, frozenset(), {}),
                missing,
                diagnostic_prefix="missing_phase_question",
            ),
            ConsequentialQuestion(
                None,
                (
                    "missing_source_dependencies:derived_a",
                    "unknown_fact:unknown_a",
                    "unknown_fact:unknown_z",
                ),
            ),
        )

    def test_all_source_coverage_is_required_before_returning_a_winner(self) -> None:
        missing = frozenset({"z", "b", "a"})
        self.assert_policies(
            knowledge(missing, (question(priority=-10),)),
            missing,
            PreparedFacts({}, frozenset(), {}),
            ("missing_procedure_selection_question:b", "missing_procedure_selection_question:z"),
            ("missing_phase_question:b", "missing_phase_question:z"),
        )

    def test_later_derived_expansion_uses_only_missing_prepared_sources(self) -> None:
        missing = frozenset({"derived_a", "b"})
        authored = question(answers=("b",))
        self.assert_policies(
            knowledge(missing, (authored,)),
            missing,
            PreparedFacts({"a": True}, frozenset({"a"}), {"derived_a": frozenset({"b"})}),
            authored,
            authored,
        )

    def test_priority_then_id_and_exact_tie_preserve_first_object(self) -> None:
        first = question("a", priority=0)
        tie = replace(first, text=LocalizedText("آخر", "Different wording"))
        missing = frozenset({"a"})
        for tied in ((first, tie), (tie, first)):
            with self.subTest(first=tied[0].text.en):
                self.assert_policies(
                    knowledge(
                        missing, (question("0", priority=1), question("z", priority=0), *tied)
                    ),
                    missing,
                    PreparedFacts({}, frozenset(), {}),
                    tied[0],
                    tied[0],
                )

    def test_pickers_do_not_validate_winning_question_extra_answers(self) -> None:
        missing = frozenset({"a"})
        for extra in ("undefined", "derived_a"):
            with self.subTest(extra=extra):
                winner = question("winner", priority=0, answers=("a", extra))
                self.assert_policies(
                    knowledge(missing, (question("runner"), winner)),
                    missing,
                    PreparedFacts({}, frozenset(), {}),
                    winner,
                    winner,
                )

    def test_empty_later_input_returns_no_source_fact(self) -> None:
        snapshot = knowledge(frozenset(), (question(),))
        self.assertEqual(
            pick_consequential_question(
                snapshot,
                snapshot.services[0],
                PreparedFacts({}, frozenset(), {}),
                frozenset(),
                diagnostic_prefix="missing_phase_question",
            ),
            ConsequentialQuestion(None, ("missing_phase_question:no_source_fact",)),
        )

    def test_malformed_trusted_unknown_without_missing_facts_retains_legacy_value_error(
        self,
    ) -> None:
        # The real evaluator cannot produce UNKNOWN with an empty missing set for valid rules.
        malformed = Evaluation(
            TruthValue.UNKNOWN, frozenset(), EvaluationTrace("eq", TruthValue.UNKNOWN)
        )
        with patch("planning.selection.evaluate", return_value=malformed):
            with self.assertRaisesRegex(ValueError, "min\\(\\) (arg|iterable argument) is empty"):
                select_procedure(
                    knowledge(frozenset({"a"}), (question(),)),
                    "service",
                    PreparedFacts({}, frozenset(), {}),
                )
