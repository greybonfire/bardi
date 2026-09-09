from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date
from unittest.mock import patch

from planning import (
    AuthoritySnapshot,
    ChecklistItemSnapshot,
    ContradictionSnapshot,
    EligibilityBasisSnapshot,
    EvidenceLinkSnapshot,
    FactDefinition,
    FeeSnapshot,
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
    SourceSnapshot,
    StepSnapshot,
    plan_stateless,
)
from planning.fees import FeeSelection


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


def fee_operation_snapshot(
    *,
    value_state: str = "known",
    amount: int | None = 100,
    minimum_amount: int | None = None,
    maximum_amount: int | None = None,
    evidence: tuple[EvidenceLinkSnapshot, ...] | None = None,
    questions: tuple[QuestionSnapshot, ...] | None = None,
    fee_fact: str = "fee_applies",
    fee_predicate: Predicate | None = None,
) -> KnowledgeSnapshot:
    base = snapshot(version=True)
    source = SourceSnapshot(
        "fee-source",
        AuthoritySnapshot("authority", LocalizedText("جهة", "Authority")),
        "Fee source",
        "https://example.test/fee",
        "official",
        date(2026, 8, 1),
    )
    support = EvidenceLinkSnapshot(
        "Fee passage",
        "Fee table",
        "Fee support",
        "supports",
        "current",
        (source,),
        verified_on=date(2026, 8, 1),
    )
    fee = FeeSnapshot(
        "fee",
        LocalizedText("رسم", "Fee"),
        value_state,
        amount,
        minimum_amount,
        maximum_amount,
        "EGP",
        "service_fee",
        1,
        fee_predicate or Predicate("eq", fee_fact, True),
        "procedure",
        None,
        None,
        None,
        "current",
        date(2026, 8, 1),
        None,
        (support,) if evidence is None else evidence,
    )
    definitions = {
        **base.fact_definitions,
        "fee_applies": FactDefinition("fee_applies", "boolean"),
    }
    authored_questions = (
        (
            QuestionSnapshot(
                "fee-question",
                LocalizedText("هل ينطبق الرسم؟", "Does the fee apply?"),
                5,
                "fee_applies",
                ("fee_applies",),
            ),
        )
        if questions is None
        else questions
    )
    service = replace(base.services[0], questions=base.services[0].questions + authored_questions)
    version = replace(base.procedure_versions[0], fees=(fee,))
    return KnowledgeSnapshot(definitions, (service,), (version,))


def step(
    *,
    applicability: Predicate | None = None,
    scope: str = "procedure",
    verification_state: str = "current",
) -> StepSnapshot:
    return StepSnapshot(
        "step",
        LocalizedText("خطوة", "Step"),
        "prepare",
        0,
        0,
        applicability,
        scope,
        "basis" if scope == "eligibility_basis" else None,
        None,
        None,
        verification_state,  # type: ignore[arg-type]
        date(2026, 8, 1),
        None,
        (),
    )


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
        result = plan_stateless(with_claim, request({"answer": True}))
        self.assertIsInstance(result, PlanResult)
        assert isinstance(result, PlanResult)
        self.assertEqual(result.checklist_items, ())
        self.assertEqual(result.inconclusive_sections, ("checklist_items",))

    def test_step_uncertainty_is_not_silently_omitted(self) -> None:
        base = snapshot(version=True)

        unknown = step(applicability=Predicate("eq", "missing", True))
        unknown_version = replace(base.procedure_versions[0], steps=(unknown,))
        unknown_knowledge = KnowledgeSnapshot(
            base.fact_definitions, base.services, (unknown_version,)
        )
        self.assertEqual(
            plan_stateless(unknown_knowledge, request({"answer": True})),
            InconclusiveResult("step_applicability_unknown"),
        )

        untrusted = step(verification_state="needs_reverification")
        untrusted_version = replace(base.procedure_versions[0], steps=(untrusted,))
        untrusted_knowledge = KnowledgeSnapshot(
            base.fact_definitions, base.services, (untrusted_version,)
        )
        result = plan_stateless(untrusted_knowledge, request({"answer": True}))
        self.assertIsInstance(result, PlanResult)
        assert isinstance(result, PlanResult)
        self.assertEqual(result.steps, ())
        self.assertEqual(result.inconclusive_sections, ("steps",))

    def test_fee_question_true_and_false_preserve_all_authored_value_states(self) -> None:
        cases = (
            ("known", 100, None, None),
            ("range", None, 100, 150),
            ("unknown", None, None, None),
            ("unverified", 900, None, None),
        )
        for value_state, amount, minimum, maximum in cases:
            with self.subTest(value_state=value_state):
                knowledge = fee_operation_snapshot(
                    value_state=value_state,
                    amount=amount,
                    minimum_amount=minimum,
                    maximum_amount=maximum,
                )
                unanswered = plan_stateless(knowledge, request({"answer": True}))
                self.assertIsInstance(unanswered, NextQuestionResult)
                assert isinstance(unanswered, NextQuestionResult)
                self.assertEqual(unanswered.question.id, "fee-question")

                included = plan_stateless(knowledge, request({"answer": True, "fee_applies": True}))
                self.assertIsInstance(included, PlanResult)
                assert isinstance(included, PlanResult)
                self.assertEqual([item.id for item in included.fees], ["fee"])
                projected = included.fees[0]
                if value_state == "known":
                    self.assertEqual(projected.amount, 100)
                    self.assertFalse(projected.current_value_unknown)
                elif value_state == "range":
                    self.assertEqual(
                        (projected.minimum_amount, projected.maximum_amount), (100, 150)
                    )
                    self.assertFalse(projected.current_value_unknown)
                else:
                    self.assertIsNone(projected.amount)
                    self.assertIsNone(projected.minimum_amount)
                    self.assertIsNone(projected.maximum_amount)
                    self.assertTrue(projected.current_value_unknown)

                excluded = plan_stateless(
                    knowledge, request({"answer": True, "fee_applies": False})
                )
                self.assertIsInstance(excluded, PlanResult)
                assert isinstance(excluded, PlanResult)
                self.assertFalse(excluded.fees)

    def test_fee_question_does_not_promote_unavailable_stale_or_disputed_support(self) -> None:
        base = fee_operation_snapshot()
        original = base.procedure_versions[0].fees[0].evidence_links[0]
        for label, evidence in (
            ("unavailable", ()),
            ("stale", (replace(original, verification_state="stale"),)),
            ("disputed", (replace(original, verification_state="disputed"),)),
        ):
            with self.subTest(support=label):
                knowledge = fee_operation_snapshot(evidence=evidence)
                self.assertIsInstance(
                    plan_stateless(knowledge, request({"answer": True})),
                    NextQuestionResult,
                )
                result = plan_stateless(knowledge, request({"answer": True, "fee_applies": True}))
                self.assertIsInstance(result, PlanResult)
                assert isinstance(result, PlanResult)
                projected = result.fees[0]
                self.assertEqual(projected.value_state, "unverified")
                self.assertIsNone(projected.amount)
                self.assertTrue(projected.current_value_unknown)

    def test_fee_question_expands_derived_facts_and_uses_deterministic_multi_fact_order(
        self,
    ) -> None:
        questions = (
            QuestionSnapshot(
                "later-question",
                LocalizedText("لاحق", "Later"),
                20,
                "birth_date",
                ("birth_date",),
            ),
            QuestionSnapshot(
                "multi-question",
                LocalizedText("متعدد", "Multi"),
                10,
                "birth_date",
                ("birth_date", "fee_applies"),
            ),
        )
        knowledge = fee_operation_snapshot(
            questions=questions,
            fee_predicate=Predicate("gte", "age_years_on_evaluation_date", 18),
        )
        knowledge = KnowledgeSnapshot(
            {
                **knowledge.fact_definitions,
                "birth_date": FactDefinition("birth_date", "date"),
                "age_years_on_evaluation_date": FactDefinition(
                    "age_years_on_evaluation_date", "integer", minimum=0, derived=True
                ),
            },
            knowledge.services,
            knowledge.procedure_versions,
        )

        first = plan_stateless(knowledge, request({"answer": True}))
        self.assertIsInstance(first, NextQuestionResult)
        assert isinstance(first, NextQuestionResult)
        self.assertEqual(first.question.id, "multi-question")
        self.assertEqual(
            tuple(answer.key for answer in first.question.answers), ("birth_date", "fee_applies")
        )

        partial = plan_stateless(knowledge, request({"answer": True, "fee_applies": False}))
        self.assertIsInstance(partial, NextQuestionResult)
        assert isinstance(partial, NextQuestionResult)
        self.assertEqual(partial.question.id, "multi-question")

        adult = plan_stateless(
            knowledge,
            request({"answer": True, "fee_applies": False, "birth_date": date(2000, 1, 1)}),
        )
        self.assertIsInstance(adult, PlanResult)
        assert isinstance(adult, PlanResult)
        self.assertEqual([item.id for item in adult.fees], ["fee"])

    def test_fee_question_configuration_defects_and_no_actionable_fallback_fail_closed(
        self,
    ) -> None:
        missing_coverage = fee_operation_snapshot(questions=())
        result = plan_stateless(missing_coverage, request({"answer": True}))
        self.assertIsInstance(result, InvalidResult)
        assert isinstance(result, InvalidResult)
        self.assertEqual(result.diagnostics[0].code, "knowledge_configuration_invalid")

        invalid_question = fee_operation_snapshot(
            questions=(
                QuestionSnapshot(
                    "invalid-question",
                    LocalizedText("غير صالح", "Invalid"),
                    1,
                    "fee_applies",
                    ("fee_applies", "not_defined"),
                ),
            )
        )
        invalid = plan_stateless(invalid_question, request({"answer": True}))
        self.assertIsInstance(invalid, InvalidResult)

        with patch(
            "planning.operation.select_fees",
            return_value=FeeSelection((), applicability_inconclusive=True),
        ):
            fallback = plan_stateless(snapshot(version=True), request({"answer": True}))
        self.assertEqual(fallback, InconclusiveResult("fee_applicability_unknown"))

    def test_unknown_basis_scope_is_configuration_invalid_after_basis_resolution(self) -> None:
        base = snapshot(version=True)
        version = replace(
            base.procedure_versions[0],
            steps=(step(scope="eligibility_basis"),),
        )
        knowledge = KnowledgeSnapshot(base.fact_definitions, base.services, (version,))
        result = plan_stateless(knowledge, request({"answer": True}))
        self.assertIsInstance(result, InvalidResult)
        assert isinstance(result, InvalidResult)
        self.assertEqual(result.diagnostics[0].code, "knowledge_configuration_invalid")

    def test_basis_reachability_precedes_qualification_questions(self) -> None:
        source = SourceSnapshot(
            "basis-source",
            AuthoritySnapshot("authority", LocalizedText("جهة", "Authority")),
            "Basis source",
            "https://example.test/basis",
            "official",
            date(2026, 8, 1),
        )
        evidence = EvidenceLinkSnapshot(
            "Basis passage",
            "Section",
            "Basis assertion",
            "supports",
            "current",
            (source,),
            verified_on=date(2026, 8, 1),
        )
        candidate = ProcedureCandidateSnapshot(
            "procedure",
            LocalizedText("إجراء", "Procedure"),
            Predicate("eq", "answer", True),
        )
        questions = (
            QuestionSnapshot(
                "answer-question",
                LocalizedText("جواب", "Answer"),
                1,
                "answer",
                ("answer",),
            ),
            QuestionSnapshot(
                "gate-question",
                LocalizedText("بوابة", "Gate"),
                2,
                "gate",
                ("gate",),
            ),
            QuestionSnapshot(
                "qualification-question",
                LocalizedText("تأهيل", "Qualification"),
                3,
                "qualification",
                ("qualification",),
            ),
        )
        service = ServiceSnapshot(
            "service",
            LocalizedText("خدمة", "Service"),
            (candidate,),
            questions,
            (),
            True,
        )
        basis = EligibilityBasisSnapshot(
            "basis",
            LocalizedText("أساس", "Basis"),
            Predicate("eq", "gate", True),
            Predicate("eq", "qualification", True),
            verification_state="current",
            verified_on=date(2026, 8, 1),
            evidence_links=(evidence,),
        )
        version = ProcedureVersionSnapshot(
            "version",
            "procedure",
            LocalizedText("نسخة", "Version"),
            Predicate("eq", "answer", True),
            "v1",
            "published",
            None,
            None,
            eligibility_bases=(basis,),
        )
        knowledge = KnowledgeSnapshot(
            {
                "answer": FactDefinition("answer", "boolean"),
                "gate": FactDefinition("gate", "boolean"),
                "qualification": FactDefinition("qualification", "boolean"),
            },
            (service,),
            (version,),
        )

        gate = plan_stateless(knowledge, request({"answer": True}))
        self.assertIsInstance(gate, NextQuestionResult)
        assert isinstance(gate, NextQuestionResult)
        self.assertEqual(gate.question.id, "gate-question")

        no_basis = plan_stateless(knowledge, request({"answer": True, "gate": False}))
        self.assertEqual(no_basis, InconclusiveResult("no_applicable_eligibility_basis"))

        qualification = plan_stateless(knowledge, request({"answer": True, "gate": True}))
        self.assertIsInstance(qualification, NextQuestionResult)
        assert isinstance(qualification, NextQuestionResult)
        self.assertEqual(qualification.question.id, "qualification-question")

        matched = plan_stateless(
            knowledge,
            request({"answer": True, "gate": True, "qualification": True}),
        )
        self.assertIsInstance(matched, PlanResult)
        assert isinstance(matched, PlanResult)
        self.assertEqual(tuple(item.id for item in matched.eligibility_bases), ("basis",))
        self.assertEqual(matched.inconclusive_basis_ids, ())
        self.assertEqual(matched.routing.status, "unresolved")
        self.assertEqual(matched.routing.destinations, ())

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
