"""Core stage contract: runnable with unittest and no Django settings or database."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest import TestCase

from planning.facts import FACT_DEFINITIONS, FactDefinition
from planning.rules import Predicate

from knowledge.snapshot_policy import (
    ClaimRow,
    CoreInputs,
    DecodedCoreRules,
    EvidenceInfo,
    FeeRow,
    KnowledgeSnapshotLoadError,
    StepRow,
    WarningRow,
    validate_core,
)

RULE = {"op": "eq", "fact": "is_student", "value": True}
BROKEN = {"op": "broken"}
SUPPORT = EvidenceInfo(
    "passage", "section", "context", "supports", "current", (("official", None, ""),)
)


def item() -> ClaimRow:
    return {
        "id": 1,
        "procedure_version__semantic_id": "v1",
        "semantic_id": "claim",
        "applicability": {},
        "verification_state": "unknown",
    }


def step() -> StepRow:
    return {
        **item(),
        "scope": "procedure",
        "eligibility_basis_id": None,
        "eligibility_basis__procedure_version_id": None,
        "procedure_version_id": 10,
    }


def fee() -> FeeRow:
    return {
        **step(),
        "currency": "EGP",
        "fee_type": "administrative",
        "value_state": "unknown",
        "amount": None,
        "minimum_amount": None,
        "maximum_amount": None,
    }


def warning() -> WarningRow:
    return {**item(), "kind": "product"}


class CorePolicyTests(TestCase):
    def setUp(self) -> None:
        self.inputs = CoreInputs(FACT_DEFINITIONS, FACT_DEFINITIONS, {})

    def diagnostics(
        self, inputs: CoreInputs
    ) -> tuple[tuple[str, tuple[tuple[str, tuple[str | int, ...]], ...]], ...]:
        with self.assertRaises(KnowledgeSnapshotLoadError) as caught:
            validate_core(inputs)
        error = caught.exception
        self.assertEqual(error.owner_ids, tuple(row.owner_id for row in error.rule_diagnostics))
        self.assertEqual(str(error), ", ".join(error.owner_ids))
        return tuple(
            (
                row.owner_id,
                tuple((diagnostic.code, diagnostic.path) for diagnostic in row.diagnostics),
            )
            for row in error.rule_diagnostics
        )

    def test_decoded_handoff_for_every_rule_owner_and_optional_omission(self) -> None:
        checklist = item()
        checklist["applicability"] = RULE
        current_step = step()
        current_step.update({"applicability": RULE, "verification_state": "current"})
        known_fee = fee()
        known_fee.update(
            {
                "applicability": RULE,
                "value_state": "known",
                "amount": 0,
                "verification_state": "current",
            }
        )
        administrative_warning = warning()
        administrative_warning.update(
            {"applicability": RULE, "kind": "administrative", "verification_state": "current"}
        )
        result = validate_core(
            replace(
                self.inputs,
                services=({"semantic_id": "s", "is_active": True},),
                checklist_items=(checklist,),
                steps=(current_step,),
                fees=(known_fee,),
                warnings=(administrative_warning,),
                evidence={key: (SUPPORT,) for key in (("step", 1), ("fee", 1), ("warning", 1))},
                candidates=(
                    {
                        "service__semantic_id": "s",
                        "procedure__semantic_id": "p",
                        "selection_predicate": RULE,
                    },
                ),
                versions=({"semantic_id": "v1", "applicability": RULE},),
                contradictions=(
                    {"service__semantic_id": "s", "semantic_id": "c", "condition": RULE},
                ),
            )
        )
        self.assertEqual(
            result,
            DecodedCoreRules(
                {1: Predicate("eq", "is_student", True)},
                {1: Predicate("eq", "is_student", True)},
                {1: Predicate("eq", "is_student", True)},
                {1: Predicate("eq", "is_student", True)},
                {("s", "p"): Predicate("eq", "is_student", True)},
                {"v1": Predicate("eq", "is_student", True)},
                {"c": Predicate("eq", "is_student", True)},
            ),
        )
        omitted = validate_core(
            replace(
                self.inputs,
                checklist_items=(item(),),
                steps=(step(),),
                fees=(fee(),),
                warnings=(warning(),),
            )
        )
        self.assertEqual(
            omitted,
            DecodedCoreRules({1: None}, {1: None}, {1: None}, {1: None}, {}, {}, {}),
        )

    def test_colliding_diagnostic_strings_preserve_distinct_rules(self) -> None:
        first = {"procedure_version__semantic_id": "v1:x", "semantic_id": "y"}
        second = {"procedure_version__semantic_id": "v1", "semantic_id": "x:y"}
        false_rule = {**RULE, "value": False}
        for field, factory in (
            ("checklist_items", item),
            ("steps", step),
            ("fees", fee),
            ("warnings", warning),
        ):
            with self.subTest(field=field):
                rows = (
                    {**factory(), **first, "id": 1, "applicability": RULE},
                    {**factory(), **second, "id": 2, "applicability": false_rule},
                )
                changes: dict[str, Any] = {field: rows}
                result = validate_core(replace(self.inputs, **changes))
                self.assertEqual(
                    getattr(result, field),
                    {
                        1: Predicate("eq", "is_student", True),
                        2: Predicate("eq", "is_student", False),
                    },
                )
                broken = tuple({**row, "applicability": BROKEN} for row in rows)
                changes = {field: broken}
                diagnostics = self.diagnostics(replace(self.inputs, **changes))
                self.assertEqual(len(diagnostics), 2)
                self.assertEqual(diagnostics[0][0], diagnostics[1][0])
        result = validate_core(
            replace(
                self.inputs,
                candidates=(
                    {
                        "service__semantic_id": "s:x",
                        "procedure__semantic_id": "y",
                        "selection_predicate": RULE,
                    },
                    {
                        "service__semantic_id": "s",
                        "procedure__semantic_id": "x:y",
                        "selection_predicate": false_rule,
                    },
                ),
            )
        )
        self.assertEqual(
            result.candidates,
            {
                ("s:x", "y"): Predicate("eq", "is_student", True),
                ("s", "x:y"): Predicate("eq", "is_student", False),
            },
        )

    def test_rule_precedence_keeps_step_and_warning_duplicates_but_suppresses_fee(self) -> None:
        broken_step = step()
        broken_step.update(
            {"applicability": BROKEN, "scope": "eligibility_basis", "verification_state": "current"}
        )
        broken_fee = fee()
        broken_fee.update(
            {"applicability": BROKEN, "scope": "eligibility_basis", "currency": "", "fee_type": ""}
        )
        broken_warning = warning()
        broken_warning.update(
            {"applicability": BROKEN, "kind": "administrative", "verification_state": "current"}
        )
        broken_item = item()
        broken_item.update({"applicability": BROKEN, "verification_state": "current"})
        rule_error = (("unsupported_rule_operator:broken", ("rule", "op")),)
        self.assertEqual(
            self.diagnostics(
                replace(
                    self.inputs,
                    steps=(broken_step,),
                    fees=(broken_fee,),
                    warnings=(broken_warning,),
                    checklist_items=(broken_item,),
                )
            ),
            (
                ("checklist_item:v1:claim", rule_error),
                ("fee:v1:claim", rule_error),
                ("step:v1:claim", rule_error),
                ("step:v1:claim", (("invalid_basis_owner", ("scope",)),)),
                ("warning:v1:claim", rule_error),
                ("warning:v1:claim", (("invalid_warning_evidence", ("evidence",)),)),
            ),
        )
        broken_step["scope"] = "procedure"
        self.assertEqual(
            self.diagnostics(replace(self.inputs, steps=(broken_step,))),
            (("step:v1:claim", rule_error),),
        )

    def test_checklist_evidence_presence_is_not_step_adequacy(self) -> None:
        current = item()
        current["verification_state"] = "current"
        self.assertEqual(
            self.diagnostics(replace(self.inputs, checklist_items=(current,))),
            (("checklist_item:v1:claim", (("missing_evidence_link", ("evidence",)),)),),
        )
        for state in ("current", "unknown"):
            current["verification_state"] = state
            self.assertEqual(
                self.diagnostics(
                    replace(
                        self.inputs,
                        checklist_items=(current,),
                        evidence={("checklist_item", 1): (replace(SUPPORT, sources=()),)},
                    )
                ),
                (("checklist_item:v1:claim", (("missing_evidence_source", ("evidence",)),)),),
            )
        validate_core(
            replace(
                self.inputs,
                checklist_items=(current,),
                evidence={
                    ("checklist_item", 1): (
                        replace(SUPPORT, passage="", support_status="contradicts"),
                    )
                },
            )
        )

    def test_step_basis_failure_precedes_evidence(self) -> None:
        scoped = step()
        scoped.update(
            {
                "scope": "eligibility_basis",
                "eligibility_basis_id": 20,
                "eligibility_basis__procedure_version_id": 11,
                "verification_state": "current",
            }
        )
        self.assertEqual(
            self.diagnostics(replace(self.inputs, steps=(scoped,))),
            (("step:v1:claim", (("invalid_basis_owner", ("scope",)),)),),
        )
        scoped["eligibility_basis__procedure_version_id"] = 10
        self.assertEqual(
            self.diagnostics(replace(self.inputs, steps=(scoped,))),
            (("step:v1:claim", (("inadequate_evidence", ("evidence",)),)),),
        )

    def test_current_support_requires_one_complete_link_and_no_current_contradiction(self) -> None:
        current = step()
        current["verification_state"] = "current"
        for bad in (
            replace(SUPPORT, passage=" "),
            replace(SUPPORT, location=" "),
            replace(SUPPORT, applicability_context=" "),
            replace(SUPPORT, sources=()),
            replace(SUPPORT, verification_state="stale"),
            replace(SUPPORT, support_status="contradicts"),
        ):
            with self.subTest(link=bad):
                self.assertEqual(
                    self.diagnostics(
                        replace(self.inputs, steps=(current,), evidence={("step", 1): (bad,)})
                    ),
                    (("step:v1:claim", (("inadequate_evidence", ("evidence",)),)),),
                )
        contradictory = replace(SUPPORT, support_status="contradicts")
        self.diagnostics(
            replace(self.inputs, steps=(current,), evidence={("step", 1): (SUPPORT, contradictory)})
        )
        # Unlike routing, incomplete extra links/field-report context do not veto core support.
        validate_core(
            replace(
                self.inputs,
                steps=(current,),
                evidence={
                    ("step", 1): (
                        SUPPORT,
                        replace(SUPPORT, passage="", sources=(("field_report", None, ""),)),
                        replace(contradictory, verification_state="stale"),
                    )
                },
            )
        )

    def test_fee_failure_order(self) -> None:
        invalid = fee()
        invalid.update(
            {
                "scope": "eligibility_basis",
                "currency": "",
                "fee_type": "",
                "value_state": "known",
                "amount": -1,
                "verification_state": "current",
            }
        )
        for code, path in (
            ("invalid_basis_owner", "scope"),
            ("missing_currency", "currency"),
            ("missing_fee_type", "fee_type"),
            ("invalid_fee_value", "value_state"),
            ("missing_evidence_link", "evidence"),
        ):
            with self.subTest(code=code):
                self.assertEqual(
                    self.diagnostics(replace(self.inputs, fees=(invalid,))),
                    (("fee:v1:claim", ((code, (path,)),)),),
                )
                if code == "invalid_basis_owner":
                    invalid["scope"] = "procedure"
                elif code == "missing_currency":
                    invalid["currency"] = "EGP"
                elif code == "missing_fee_type":
                    invalid["fee_type"] = "administrative"
                elif code == "invalid_fee_value":
                    invalid["amount"] = 0
        for links, code in (
            ((replace(SUPPORT, sources=()),), "missing_evidence_source"),
            ((replace(SUPPORT, passage=""),), "inadequate_evidence"),
        ):
            self.assertEqual(
                self.diagnostics(
                    replace(self.inputs, fees=(invalid,), evidence={("fee", 1): links})
                ),
                (("fee:v1:claim", ((code, ("evidence",)),)),),
            )

    def test_fee_shapes_and_unverified_support_boundary(self) -> None:
        for state, amount, minimum, maximum, verification, valid in (
            ("known", 0, None, None, "unknown", True),
            ("known", True, None, None, "unknown", False),
            ("range", None, 0, 1, "unknown", True),
            ("range", None, 2, 1, "unknown", False),
            ("range", 1, 0, 2, "unknown", False),
            ("unknown", None, None, None, "current", True),
            ("unknown", 0, None, None, "unknown", False),
            ("unverified", 1, None, None, "stale", True),
            ("unverified", None, 0, 2, "disputed", True),
            ("unverified", 0, None, None, "needs_reverification", True),
            ("unverified", 0, None, None, "current", False),
            ("unverified", None, None, None, "unknown", False),
            ("other", None, None, None, "unknown", False),
        ):
            with self.subTest(state=state, amount=amount, verification=verification):
                row = fee()
                row.update(
                    {
                        "value_state": state,
                        "amount": amount,
                        "minimum_amount": minimum,
                        "maximum_amount": maximum,
                        "verification_state": verification,
                    }
                )
                inputs = replace(
                    self.inputs, fees=(row,), evidence={("fee", 1): (replace(SUPPORT, passage=""),)}
                )
                if valid:
                    validate_core(inputs)
                else:
                    self.assertEqual(
                        self.diagnostics(inputs),
                        (("fee:v1:claim", (("invalid_fee_value", ("value_state",)),)),),
                    )
        unverified = fee()
        unverified.update({"value_state": "unverified", "amount": 0, "verification_state": "stale"})
        self.assertEqual(
            self.diagnostics(replace(self.inputs, fees=(unverified,))),
            (("fee:v1:claim", (("missing_evidence_link", ("evidence",)),)),),
        )

    def test_product_warning_rejects_any_evidence(self) -> None:
        self.assertEqual(
            self.diagnostics(
                replace(
                    self.inputs,
                    warnings=(warning(),),
                    evidence={("warning", 1): (replace(SUPPORT, verification_state="unknown"),)},
                )
            ),
            (("warning:v1:claim", (("invalid_warning_evidence", ("evidence",)),)),),
        )

    def test_domain_reexports_the_same_error_types(self) -> None:
        from knowledge.domain import KnowledgeSnapshotLoadError as AdapterError
        from knowledge.domain import StoredRuleLoadDiagnostic as AdapterDiagnostic
        from knowledge.snapshot_policy import StoredRuleLoadDiagnostic

        self.assertIs(AdapterError, KnowledgeSnapshotLoadError)
        self.assertIs(AdapterDiagnostic, StoredRuleLoadDiagnostic)

    def test_mandatory_rules_do_not_accept_optional_guidance_omission(self) -> None:
        self.assertEqual(
            self.diagnostics(
                replace(
                    self.inputs,
                    candidates=(
                        {
                            "service__semantic_id": "s",
                            "procedure__semantic_id": "p",
                            "selection_predicate": {},
                        },
                    ),
                    versions=({"semantic_id": "v", "applicability": {}},),
                    contradictions=(
                        {"service__semantic_id": "s", "semantic_id": "c", "condition": {}},
                    ),
                )
            ),
            tuple(
                (owner, (("malformed_rule:<unknown>", ("rule", "op")),))
                for owner in (
                    "candidate:s:p",
                    "contradiction:c",
                    "procedure_version:v",
                )
            ),
        )

    def test_explicit_empty_definitions_never_use_default_registry(self) -> None:
        self.assertEqual(
            self.diagnostics(
                CoreInputs({}, {}, {}, versions=({"semantic_id": "v", "applicability": RULE},))
            ),
            (("procedure_version:v", (("unsupported_rule_fact:is_student", ("rule", "fact")),)),),
        )

    def test_active_rules_use_published_facts_inactive_rules_use_all_facts(self) -> None:
        hidden = FactDefinition("hidden", "boolean")
        definitions = {**FACT_DEFINITIONS, hidden.key: hidden}
        hidden_rule = {"op": "eq", "fact": "hidden", "value": True}
        inputs = replace(
            self.inputs,
            definitions=definitions,
            services=({"semantic_id": "s", "is_active": False},),
            candidates=(
                {
                    "service__semantic_id": "s",
                    "procedure__semantic_id": "p",
                    "selection_predicate": hidden_rule,
                },
            ),
            contradictions=(
                {"service__semantic_id": "s", "semantic_id": "c", "condition": hidden_rule},
            ),
            questions=({"service__semantic_id": "s", "semantic_id": "q", "fact__key": "hidden"},),
        )
        decoded = validate_core(inputs)
        self.assertEqual(decoded.candidates, {("s", "p"): Predicate("eq", "hidden", True)})
        self.assertEqual(decoded.contradictions, {"c": Predicate("eq", "hidden", True)})
        active = replace(inputs, services=({"semantic_id": "s", "is_active": True},))
        unsupported = (("unsupported_rule_fact:hidden", ("rule", "fact")),)
        self.assertEqual(
            self.diagnostics(active),
            (
                ("candidate:s:p", unsupported),
                ("contradiction:c", unsupported),
                ("question:q", (("unpublished_fact", ("facts", "hidden")),)),
            ),
        )
        validate_core(replace(active, published_definitions=definitions))

    def test_contradiction_decode_precedes_declared_facts_and_questions_check_primary_and_resolved(
        self,
    ) -> None:
        inputs = replace(
            self.inputs,
            services=({"semantic_id": "s", "is_active": True},),
            contradictions=(
                {"service__semantic_id": "s", "semantic_id": "c", "condition": BROKEN},
            ),
            contradiction_facts=(
                {"contradiction__semantic_id": "c", "fact__key": "z"},
                {"contradiction__semantic_id": "c", "fact__key": "a"},
            ),
            questions=({"service__semantic_id": "s", "semantic_id": "q", "fact__key": "z"},),
            question_facts=(
                {"question__semantic_id": "q", "fact__key": "a"},
                {"question__semantic_id": "q", "fact__key": "a"},
            ),
        )
        unpublished = (("unpublished_fact", ("facts", "a")), ("unpublished_fact", ("facts", "z")))
        self.assertEqual(
            self.diagnostics(inputs),
            (
                ("contradiction:c", (("unsupported_rule_operator:broken", ("rule", "op")),)),
                ("question:q", unpublished),
            ),
        )
        self.assertEqual(
            self.diagnostics(
                replace(
                    inputs,
                    contradictions=(
                        {"service__semantic_id": "s", "semantic_id": "c", "condition": RULE},
                    ),
                )
            ),
            (
                ("contradiction:c", unpublished),
                ("question:q", unpublished),
            ),
        )
        self.assertEqual(
            self.diagnostics(replace(inputs, contradictions=(), question_facts=())),
            (("question:q", (("unpublished_fact", ("facts", "z")),)),),
        )

    def test_only_published_derived_definitions_require_exact_pinned_meaning(self) -> None:
        extra = FactDefinition("extra", "boolean", derived=True)
        validate_core(replace(self.inputs, definitions={**FACT_DEFINITIONS, extra.key: extra}))
        for invalid in (
            extra,
            replace(FACT_DEFINITIONS["is_student"], derived=True),
            replace(FACT_DEFINITIONS["age_years_on_evaluation_date"], minimum=1),
            replace(FACT_DEFINITIONS["only_son_candidate"], kind="integer"),
            replace(FACT_DEFINITIONS["only_son_candidate"], enum_values=("changed",)),
        ):
            with self.subTest(fact=invalid):
                definitions = {**FACT_DEFINITIONS, invalid.key: invalid}
                self.assertEqual(
                    self.diagnostics(
                        replace(
                            self.inputs, definitions=definitions, published_definitions=definitions
                        )
                    ),
                    (
                        (
                            f"fact:{invalid.key}",
                            (("unsupported_derived_fact", ("facts", invalid.key)),),
                        ),
                    ),
                )
        # Request-time validation does not add an immutable-source/publication gate.
        source = FactDefinition("custom", "string")
        validate_core(CoreInputs({source.key: source}, {source.key: source}, {}))
        validate_core(self.inputs)
