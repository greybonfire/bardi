"""Feature policy interfaces: plain rows, explicit Facts, no Django settings/database."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from functools import partial
from typing import Any
from unittest import TestCase

from planning.facts import FACT_DEFINITIONS
from planning.rules import Predicate

from knowledge.snapshot_policy import (
    AssociationRow,
    BasisRow,
    DecodedBasisRules,
    DecodedDependencyRules,
    DecodedRoutingRules,
    DependencyRow,
    EvidenceInfo,
    EvidenceRow,
    KnowledgeSnapshotLoadError,
    MaterialRow,
    core_evidence_owner,
    routing_evidence_owner,
    summarize_evidence_rows,
    validate_bases,
    validate_dependencies,
    validate_routing,
)

RULE = {"op": "eq", "fact": "is_student", "value": True}
FALSE_RULE = {**RULE, "value": False}
BROKEN = {"op": "broken"}
TRUE = Predicate("eq", "is_student", True)
FALSE = Predicate("eq", "is_student", False)
SUPPORT = EvidenceInfo(
    "passage", "section", "context", "supports", "current", (("official", None, ""),)
)


def basis() -> BasisRow:
    return {
        "id": 1,
        "procedure_version__semantic_id": "v1",
        "semantic_id": "basis",
        "text_ar": "أساس",
        "text_en": "Basis",
        "reachability": RULE,
        "qualification": FALSE_RULE,
    }


def dependency() -> DependencyRow:
    return {
        "id": 1,
        "procedure_version__semantic_id": "v1",
        "procedure_version__procedure_id": 10,
        "target_procedure_id": 20,
        "semantic_id": "dependency",
        "text_ar": "متطلب",
        "text_en": "Dependency",
        "relation": "blocking_prerequisite",
        "applicability": RULE,
        "satisfied_when": FALSE_RULE,
    }


def association() -> AssociationRow:
    return {
        "id": 1,
        "procedure_version__semantic_id": "v1",
        "semantic_id": "association",
        "service_point_version_id": 2,
        "applicability": RULE,
        "verification_state": "current",
    }


def material() -> MaterialRow:
    return {
        "id": 2,
        "semantic_id": "material",
        "address_ar": "عنوان",
        "address_en": "Address",
        "availability": "available",
        "verification_state": "current",
    }


class FeaturePolicyTests(TestCase):
    def assert_failure(
        self,
        operation: Callable[[], object],
        expected: tuple[tuple[str, tuple[tuple[str, tuple[str | int, ...]], ...]], ...],
    ) -> None:
        with self.assertRaises(KnowledgeSnapshotLoadError) as caught:
            operation()
        error = caught.exception
        self.assertEqual(
            tuple(
                (row.owner_id, tuple((item.code, item.path) for item in row.diagnostics))
                for row in error.rule_diagnostics
            ),
            expected,
        )
        self.assertEqual(error.owner_ids, tuple(row[0] for row in expected))
        self.assertEqual(str(error), ", ".join(error.owner_ids))

    def test_positive_handoff_distinguishes_both_stages_and_optional_omission(self) -> None:
        bases = validate_bases((basis(),), FACT_DEFINITIONS, {("eligibility_basis", 1): (SUPPORT,)})
        self.assertEqual(bases, {1: DecodedBasisRules(TRUE, FALSE)})
        dependencies = validate_dependencies(
            (dependency(),), FACT_DEFINITIONS, {("procedure_dependency", 1): (SUPPORT,)}
        )
        self.assertEqual(dependencies, {1: DecodedDependencyRules(TRUE, FALSE)})
        self.assertEqual(
            validate_bases(
                ({**basis(), "reachability": {}},),
                FACT_DEFINITIONS,
                {("eligibility_basis", 1): (SUPPORT,)},
            ),
            {1: DecodedBasisRules(None, FALSE)},
        )
        self.assertEqual(
            validate_dependencies(
                ({**dependency(), "applicability": {}},),
                FACT_DEFINITIONS,
                {("procedure_dependency", 1): (SUPPORT,)},
            ),
            {1: DecodedDependencyRules(None, FALSE)},
        )
        self.assertEqual(
            validate_routing(
                (association(),),
                (material(),),
                FACT_DEFINITIONS,
                {
                    ("procedure_service_point_association", 1): (SUPPORT,),
                    ("service_point_version", 2): (SUPPORT,),
                },
            ),
            DecodedRoutingRules({1: TRUE}),
        )
        self.assertEqual(validate_bases((), {}, {}), {})
        self.assertEqual(validate_dependencies((), {}, {}), {})
        self.assertEqual(validate_routing((), (), {}, {}), DecodedRoutingRules({}))
        with self.assertRaises(TypeError):
            bases[2] = bases[1]  # type: ignore[index]

    def test_basis_failure_suppression(self) -> None:
        row: Any = basis()
        row.update({"reachability": BROKEN, "qualification": {}, "text_ar": ""})
        for code, path, repair in (
            ("unsupported_rule_operator:broken", ("rule", "op"), {"reachability": {}}),
            ("missing_qualification", ("qualification",), {"qualification": BROKEN}),
            ("unsupported_rule_operator:broken", ("rule", "op"), {"qualification": RULE}),
            ("invalid_basis_evidence", ("evidence",), {}),
        ):
            with self.subTest(code=code, repair=repair):
                self.assert_failure(
                    lambda: validate_bases((row,), FACT_DEFINITIONS, {}),
                    (("eligibility_basis:v1:basis", ((code, path),)),),
                )
                row.update(repair)

    def test_dependency_failure_suppression(self) -> None:
        row: Any = dependency()
        row.update(
            {
                "relation": "unsupported",
                "target_procedure_id": 10,
                "applicability": BROKEN,
                "satisfied_when": {},
                "text_en": "",
            }
        )
        for code, path, repair in (
            (
                "unsupported_dependency_relation",
                ("relation",),
                {"relation": "blocking_prerequisite"},
            ),
            ("self_dependency", ("target_procedure",), {"target_procedure_id": 20}),
            ("unsupported_rule_operator:broken", ("rule", "op"), {"applicability": {}}),
            ("missing_satisfied_when", ("satisfied_when",), {"satisfied_when": BROKEN}),
            ("unsupported_rule_operator:broken", ("rule", "op"), {"satisfied_when": RULE}),
            ("invalid_dependency_evidence", ("evidence",), {}),
        ):
            with self.subTest(code=code, repair=repair):
                self.assert_failure(
                    lambda: validate_dependencies((row,), FACT_DEFINITIONS, {}),
                    (("procedure_dependency:v1:dependency", ((code, path),)),),
                )
                row.update(repair)

    def test_basis_and_dependency_require_both_texts_links_and_every_source(self) -> None:
        for factory, validate, field, code in (
            (basis, validate_bases, "eligibility_basis", "invalid_basis_evidence"),
            (
                dependency,
                validate_dependencies,
                "procedure_dependency",
                "invalid_dependency_evidence",
            ),
        ):
            for changes, links in (
                ({"text_ar": " "}, (SUPPORT,)),
                ({"text_en": " "}, (SUPPORT,)),
                ({}, ()),
                ({}, (SUPPORT, replace(SUPPORT, sources=()))),
            ):
                with self.subTest(field=field, changes=changes, links=links):
                    row: Any = {**factory(), **changes}
                    self.assert_failure(
                        partial(validate, (row,), FACT_DEFINITIONS, {(field, 1): links}),
                        ((f"{field}:v1:{row['semantic_id']}", ((code, ("evidence",)),)),),
                    )
            # These stages intentionally do not impose routing/publication adequacy.
            valid_row: Any = factory()
            validate(
                (valid_row,),
                FACT_DEFINITIONS,
                {
                    (field, 1): (
                        replace(
                            SUPPORT,
                            passage="",
                            location="",
                            applicability_context="",
                            support_status="contradicts",
                            sources=(("field_report", None, ""),),
                        ),
                    )
                },
            )

    def test_explicit_empty_facts_do_not_fall_back_to_defaults(self) -> None:
        for operation, owner in (
            (partial(validate_bases, (basis(),), {}, {}), "eligibility_basis:v1:basis"),
            (
                partial(validate_dependencies, (dependency(),), {}, {}),
                "procedure_dependency:v1:dependency",
            ),
        ):
            self.assert_failure(
                operation,
                ((owner, (("unsupported_rule_fact:is_student", ("rule", "fact")),)),),
            )
        self.assert_failure(
            lambda: validate_routing((association(),), (), {}, {}),
            (
                (
                    "service_point_association:v1:association",
                    (("unsupported_rule_fact:is_student", ("rule", "fact")),),
                ),
            ),
        )

    def test_routing_mandatory_rule_failure_wins_over_evidence_but_material_is_checked(
        self,
    ) -> None:
        self.assert_failure(
            lambda: validate_routing(
                ({**association(), "applicability": {}},), (material(),), FACT_DEFINITIONS, {}
            ),
            (
                (
                    "service_point_association:v1:association",
                    (("malformed_rule:<unknown>", ("rule", "op")),),
                ),
                ("service_point_version:material", (("invalid_service_point_material", ()),)),
            ),
        )

    def test_routing_current_adequacy_checks_every_detail_but_unknown_only_requires_sources(
        self,
    ) -> None:
        bad_links = (
            replace(SUPPORT, passage=" "),
            replace(SUPPORT, location=" "),
            replace(SUPPORT, applicability_context=" "),
            replace(SUPPORT, sources=(("field_report", None, "place"),)),
            replace(SUPPORT, sources=(("field_report", date(2026, 1, 1), " "),)),
            replace(SUPPORT, support_status="contradicts"),
        )
        for bad in bad_links:
            for state in ("current", "unknown"):
                with self.subTest(bad=bad, state=state):

                    def run(state: str = state, bad: EvidenceInfo = bad) -> DecodedRoutingRules:
                        return validate_routing(
                            ({**association(), "verification_state": state},),
                            ({**material(), "verification_state": state},),
                            FACT_DEFINITIONS,
                            {
                                ("procedure_service_point_association", 1): (SUPPORT, bad),
                                ("service_point_version", 2): (SUPPORT, bad),
                            },
                        )

                    if state == "current":
                        self.assert_failure(
                            run,
                            (
                                (
                                    "service_point_association:v1:association",
                                    (("invalid_routing_evidence", ("evidence",)),),
                                ),
                                (
                                    "service_point_version:material",
                                    (("invalid_service_point_material", ()),),
                                ),
                            ),
                        )
                    else:
                        self.assertEqual(run(), DecodedRoutingRules({1: TRUE}))
        for links in (
            (),
            (SUPPORT, replace(SUPPORT, sources=())),
            (replace(SUPPORT, verification_state="unknown"),),
        ):
            for state in ("current", "unknown"):
                with self.subTest(links=links, state=state):

                    def run_presence(
                        state: str = state, links: tuple[EvidenceInfo, ...] = links
                    ) -> DecodedRoutingRules:
                        return validate_routing(
                            ({**association(), "verification_state": state},),
                            ({**material(), "verification_state": state},),
                            FACT_DEFINITIONS,
                            {
                                ("procedure_service_point_association", 1): links,
                                ("service_point_version", 2): links,
                            },
                        )

                    if state == "unknown" and links and all(link.sources for link in links):
                        run_presence()
                    else:
                        self.assert_failure(
                            run_presence,
                            (
                                (
                                    "service_point_association:v1:association",
                                    (("invalid_routing_evidence", ("evidence",)),),
                                ),
                                (
                                    "service_point_version:material",
                                    (("invalid_service_point_material", ()),),
                                ),
                            ),
                        )

    def test_routing_material_text_and_exact_availability_support(self) -> None:
        for availability in ("available", "unknown", "unavailable"):
            for changes in ({}, {"address_ar": " "}, {"address_en": " "}):
                with self.subTest(availability=availability, changes=changes):
                    changed_material: Any = {**material(), "availability": availability, **changes}
                    run = partial(
                        validate_routing,
                        (),
                        (changed_material,),
                        {},
                        {("service_point_version", 2): (SUPPORT,)},
                    )

                    if availability == "unavailable" or changes:
                        self.assert_failure(
                            run,
                            (
                                (
                                    "service_point_version:material",
                                    (("invalid_service_point_material", ()),),
                                ),
                            ),
                        )
                    else:
                        run()
        valid_field_report = replace(
            SUPPORT, sources=(("field_report", date(2026, 1, 1), "place"),)
        )
        validate_routing(
            (), (material(),), {}, {("service_point_version", 2): (valid_field_report,)}
        )

    def test_pk_handoff_never_uses_colliding_formatted_owner_strings(self) -> None:
        for factory, validate, field, first_rule, second_rule in (
            (basis, validate_bases, "eligibility_basis", "reachability", "qualification"),
            (
                dependency,
                validate_dependencies,
                "procedure_dependency",
                "applicability",
                "satisfied_when",
            ),
        ):
            first: Any = {**factory(), "procedure_version__semantic_id": "v:x", "semantic_id": "y"}
            second: Any = {
                **factory(),
                "id": 2,
                "procedure_version__semantic_id": "v",
                "semantic_id": "x:y",
                first_rule: FALSE_RULE,
                second_rule: RULE,
            }
            evidence = {(field, 1): (SUPPORT,), (field, 2): (SUPPORT,)}
            decoded = validate((first, second), FACT_DEFINITIONS, evidence)
            self.assertEqual(getattr(decoded[1], first_rule), TRUE)
            self.assertEqual(getattr(decoded[2], first_rule), FALSE)
            self.assertEqual(getattr(decoded[1], second_rule), FALSE)
            self.assertEqual(getattr(decoded[2], second_rule), TRUE)
            # Equal-owner errors remain separate and stable in input/check order.
            first[first_rule] = BROKEN
            second[second_rule] = {}
            code = (
                "missing_qualification"
                if field == "eligibility_basis"
                else "missing_satisfied_when"
            )
            self.assert_failure(
                partial(validate, (first, second), FACT_DEFINITIONS, evidence),
                (
                    (f"{field}:v:x:y", (("unsupported_rule_operator:broken", ("rule", "op")),)),
                    (f"{field}:v:x:y", ((code, (second_rule,)),)),
                ),
            )
        first_association: AssociationRow = {
            **association(),
            "procedure_version__semantic_id": "v:x",
            "semantic_id": "y",
        }
        second_association: AssociationRow = {
            **association(),
            "id": 2,
            "procedure_version__semantic_id": "v",
            "semantic_id": "x:y",
            "applicability": FALSE_RULE,
        }
        self.assertEqual(
            validate_routing(
                (first_association, second_association),
                (),
                FACT_DEFINITIONS,
                {("procedure_service_point_association", key): (SUPPORT,) for key in (1, 2)},
            ),
            DecodedRoutingRules({1: TRUE, 2: FALSE}),
        )

    def test_scalar_evidence_summary_preserves_details_order_and_owner_independence(self) -> None:
        rows: list[EvidenceRow] = [
            {
                "id": 1,
                "passage": "passage",
                "location": "section",
                "applicability_context": "context",
                "support_status": "supports",
                "verification_state": "current",
            },
            {
                "id": 2,
                "passage": "",
                "location": "",
                "applicability_context": "",
                "support_status": "contradicts",
                "verification_state": "unknown",
            },
        ]
        summaries = summarize_evidence_rows(
            rows,
            [
                {
                    "evidence_link_id": 1,
                    "source__classification": "official",
                    "source__observation_date": None,
                    "source__observation_context": "",
                },
                {
                    "evidence_link_id": 1,
                    "source__classification": "field_report",
                    "source__observation_date": date(2026, 1, 1),
                    "source__observation_context": "place",
                },
            ],
        )
        self.assertEqual(
            summaries[1],
            replace(
                SUPPORT, sources=(SUPPORT.sources[0], ("field_report", date(2026, 1, 1), "place"))
            ),
        )
        self.assertEqual(summaries[2], EvidenceInfo("", "", "", "contradicts", "unknown", ()))
        owners: dict[str, object] = {
            "checklist_item_id": 1,
            "step_id": 2,
            "fee_id": 3,
            "warning_id": 4,
            "eligibility_basis_id": 5,
            "procedure_dependency_id": 6,
            "procedure_service_point_association_id": 7,
            "service_point_version_id": 8,
        }
        self.assertEqual(core_evidence_owner(owners), ("checklist_item", 1))
        self.assertEqual(routing_evidence_owner(owners), ("procedure_service_point_association", 7))
        owners["procedure_service_point_association_id"] = 0
        self.assertEqual(routing_evidence_owner(owners), ("procedure_service_point_association", 0))
        owners["procedure_service_point_association_id"] = None
        self.assertEqual(routing_evidence_owner(owners), ("service_point_version", 8))
        owners["service_point_version_id"] = None
        self.assertIsNone(routing_evidence_owner(owners))
