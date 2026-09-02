from __future__ import annotations

import inspect
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from planning import (
    CandidateEvaluation,
    FactDefinition,
    KnowledgeSnapshot,
    LocalizedText,
    Predicate,
    PreparedFacts,
    ProcedureCandidateSnapshot,
    ProcedureSelected,
    QuestionSnapshot,
    SelectionConfigurationDefect,
    SelectionInconclusive,
    SelectionQuestion,
    SelectionUnsupported,
    ServiceSnapshot,
    TruthValue,
    select_procedure,
)


def candidate(semantic_id: str, predicate: Predicate) -> ProcedureCandidateSnapshot:
    return ProcedureCandidateSnapshot(semantic_id, LocalizedText("ع", "en"), predicate)


def catalog(
    candidates: tuple[ProcedureCandidateSnapshot, ...],
    questions: tuple[QuestionSnapshot, ...] = (),
) -> KnowledgeSnapshot:
    definitions = {
        "a": FactDefinition("a", "boolean"),
        "b": FactDefinition("b", "boolean"),
        "derived": FactDefinition("derived", "boolean", derived=True),
    }
    service = ServiceSnapshot("service", LocalizedText("ع", "Service"), candidates, questions, ())
    return KnowledgeSnapshot(definitions, (service,))


def prepared(
    values: dict[str, bool] | None = None,
    dependencies: dict[str, frozenset[str]] | None = None,
) -> PreparedFacts:
    values = {} if values is None else values
    return PreparedFacts(values, frozenset(values), {} if dependencies is None else dependencies)


class SelectionTests(unittest.TestCase):
    def test_selects_only_true_after_exhaustive_stably_ordered_evaluation(self) -> None:
        snapshot = catalog(
            (
                candidate("z", Predicate("eq", "a", False)),
                candidate("a", Predicate("eq", "a", True)),
                candidate("m", Predicate("eq", "a", False)),
            )
        )
        calls: list[str] = []

        from planning.selection import evaluate as real_evaluate

        def recording(predicate: Predicate, *args: object, **kwargs: object) -> object:
            assert predicate.value is not None
            calls.append(str(predicate.value))
            return real_evaluate(predicate, *args, **kwargs)  # type: ignore[arg-type]

        with patch("planning.selection.evaluate", side_effect=recording):
            outcome = select_procedure(snapshot, "service", prepared({"a": True}))
        self.assertIsInstance(outcome, ProcedureSelected)
        assert isinstance(outcome, ProcedureSelected)
        self.assertEqual(outcome.procedure_semantic_id, "a")
        self.assertEqual(
            tuple(item.candidate_semantic_id for item in outcome.evaluations),
            ("a", "m", "z"),
        )
        self.assertEqual(len(calls), 3)

    def test_zero_and_empty_candidates_are_explicitly_unsupported(self) -> None:
        for candidates in ((), (candidate("false", Predicate("eq", "a", True)),)):
            with self.subTest(candidates=candidates):
                outcome = select_procedure(catalog(candidates), "service", prepared({"a": False}))
                self.assertEqual(
                    outcome,
                    SelectionUnsupported("no_matching_researched_procedure", outcome.evaluations),
                )
        self.assertEqual(
            select_procedure(catalog(()), "absent", prepared()),
            SelectionUnsupported("unknown_service", ()),
        )

    def test_multiple_true_is_inconclusive_even_with_unknown(self) -> None:
        outcome = select_procedure(
            catalog(
                (
                    candidate("z", Predicate("eq", "a", True)),
                    candidate("a", Predicate("eq", "a", True)),
                    candidate("unknown", Predicate("eq", "b", True)),
                ),
                (QuestionSnapshot("q", LocalizedText("ع", "?"), 1, "b", ("b",)),),
            ),
            "service",
            prepared({"a": True}),
        )
        self.assertIsInstance(outcome, SelectionInconclusive)
        assert isinstance(outcome, SelectionInconclusive)
        self.assertEqual(outcome.candidate_semantic_ids, ("a", "z"))

    def test_true_plus_unknown_asks_deterministic_question(self) -> None:
        questions = (
            QuestionSnapshot("z", LocalizedText("ع", "?"), 1, "a", ("b",)),
            QuestionSnapshot("b", LocalizedText("ع", "?"), 0, "a", ("b",)),
            QuestionSnapshot("a", LocalizedText("ع", "?"), 0, "a", ("b",)),
        )
        outcome = select_procedure(
            catalog(
                (
                    candidate("true", Predicate("eq", "a", True)),
                    candidate("unknown", Predicate("eq", "b", True)),
                ),
                tuple(reversed(questions)),
            ),
            "service",
            prepared({"a": True}),
        )
        self.assertIsInstance(outcome, SelectionQuestion)
        assert isinstance(outcome, SelectionQuestion)
        self.assertEqual(outcome.question.semantic_id, "a")

    def test_unknowns_aggregate_and_require_coverage_for_every_source(self) -> None:
        outcome = select_procedure(
            catalog(
                (
                    candidate("a", Predicate("eq", "a", True)),
                    candidate("b", Predicate("eq", "b", True)),
                ),
                (QuestionSnapshot("qa", LocalizedText("ع", "?"), 1, "a", ("a",)),),
            ),
            "service",
            prepared(),
        )
        self.assertIsInstance(outcome, SelectionConfigurationDefect)
        assert isinstance(outcome, SelectionConfigurationDefect)
        self.assertEqual(outcome.diagnostic_codes, ("missing_procedure_selection_question:b",))

    def test_dominated_unknown_does_not_create_a_question(self) -> None:
        predicate = Predicate(
            "all",
            children=(Predicate("eq", "a", False), Predicate("eq", "b", True)),
        )
        outcome = select_procedure(
            catalog((candidate("false", predicate),)),
            "service",
            prepared({"a": True}),
        )
        self.assertIsInstance(outcome, SelectionUnsupported)

    def test_derived_missing_fact_uses_only_prepared_source_dependencies(self) -> None:
        question = QuestionSnapshot("source", LocalizedText("ع", "?"), 1, "a", ("a",))
        snapshot = catalog((candidate("p", Predicate("eq", "derived", True)),), (question,))
        outcome = select_procedure(
            snapshot, "service", prepared(dependencies={"derived": frozenset({"a"})})
        )
        self.assertIsInstance(outcome, SelectionQuestion)
        self.assertEqual(outcome.question.semantic_id, "source")  # type: ignore[union-attr]

        defect = select_procedure(snapshot, "service", prepared())
        self.assertIsInstance(defect, SelectionConfigurationDefect)
        self.assertEqual(
            defect.diagnostic_codes,  # type: ignore[union-attr]
            ("missing_source_dependencies:derived",),
        )

    def test_inputs_and_public_collections_are_defensively_immutable(self) -> None:
        values = {"a": True}
        dependencies = {"derived": frozenset({"a"})}
        facts = PreparedFacts(values, frozenset({"a"}), dependencies)
        values["a"] = False
        dependencies["derived"] = frozenset({"b"})
        self.assertIs(facts.values["a"], True)
        self.assertEqual(facts.missing_source_dependencies["derived"], frozenset({"a"}))
        with self.assertRaises(TypeError):
            facts.values["a"] = False  # type: ignore[index]

        definitions = {"a": FactDefinition("a", "boolean")}
        snapshot = KnowledgeSnapshot(definitions, ())
        definitions.clear()
        self.assertIn("a", snapshot.fact_definitions)
        with self.assertRaises(FrozenInstanceError):
            snapshot.services = ()  # type: ignore[misc]

        evaluations: list[CandidateEvaluation] = []
        result = SelectionUnsupported("x", evaluations)  # type: ignore[arg-type]
        evaluations.append(object())  # type: ignore[arg-type]
        self.assertEqual(result.evaluations, ())

    def test_selector_has_no_date_or_procedure_version_input(self) -> None:
        self.assertEqual(
            tuple(inspect.signature(select_procedure).parameters),
            ("snapshot", "service_semantic_id", "prepared_facts"),
        )
        outcome = select_procedure(
            catalog((candidate("p", Predicate("eq", "a", True)),)),
            "service",
            prepared({"a": True}),
        )
        assert isinstance(outcome, ProcedureSelected)
        self.assertIs(outcome.evaluations[0].evaluation.value, TruthValue.TRUE)


if __name__ == "__main__":
    unittest.main()
