from __future__ import annotations

import unittest
from datetime import date

from planning import (
    AuthoritySnapshot,
    EvidenceLinkSnapshot,
    KnowledgeSnapshot,
    LocalizedText,
    Predicate,
    PreparedFacts,
    ProcedureDependencySnapshot,
    ProcedureVersionSnapshot,
    SourceSnapshot,
)
from planning.dependencies import select_procedure_dependencies

EVALUATION_DATE = date(2026, 9, 1)


def evidence() -> tuple[EvidenceLinkSnapshot, ...]:
    source = SourceSnapshot(
        "source",
        AuthoritySnapshot("authority", LocalizedText("جهة", "Authority")),
        "Official source",
        "https://example.test/source",
        "official",
        date(2026, 8, 1),
    )
    return (
        EvidenceLinkSnapshot(
            "Passage",
            "Section",
            "Prerequisite assertion",
            "supports",
            "current",
            (source,),
            verified_on=date(2026, 8, 1),
        ),
    )


def dependency(
    semantic_id: str,
    *,
    order: int = 0,
    target: str = "target",
    applicability: Predicate | None = None,
    satisfied_when: Predicate | None = None,
    state: str = "current",
    relation: str = "blocking_prerequisite",
) -> ProcedureDependencySnapshot:
    return ProcedureDependencySnapshot(
        semantic_id,
        LocalizedText(f"{semantic_id}-ar", semantic_id),
        target,
        LocalizedText("إجراء مستهدف", "Target procedure"),
        relation,
        applicability,
        satisfied_when or Predicate("eq", "satisfied", True),
        order,
        None,
        None,
        state,  # type: ignore[arg-type]
        date(2026, 8, 1),
        None,
        evidence(),
    )


def version(
    semantic_id: str,
    procedure_id: str,
    *,
    dependencies: tuple[ProcedureDependencySnapshot, ...] = (),
    effective_from: date | None = None,
    effective_to: date | None = None,
) -> ProcedureVersionSnapshot:
    return ProcedureVersionSnapshot(
        semantic_id,
        procedure_id,
        LocalizedText("نسخة", "Version"),
        Predicate("eq", "entry", True),
        "v1",
        "published",
        effective_from,
        effective_to,
        dependencies=dependencies,
    )


def facts(**values: object) -> PreparedFacts:
    return PreparedFacts(values, frozenset(values), {})  # type: ignore[arg-type]


class ProcedureDependencySelectionTests(unittest.TestCase):
    def test_false_applicability_does_not_expose_satisfaction_facts(self) -> None:
        root = version(
            "root-v1",
            "root",
            dependencies=(
                dependency(
                    "dep",
                    applicability=Predicate("eq", "applies", True),
                    satisfied_when=Predicate("eq", "satisfied", True),
                ),
            ),
        )
        snapshot = KnowledgeSnapshot({}, (), (root,))
        selection = select_procedure_dependencies(
            snapshot,
            root,
            facts(applies=False),
            EVALUATION_DATE,
        )
        self.assertEqual(selection.dependencies, ())
        self.assertEqual(selection.missing_facts, frozenset())

    def test_unknown_rules_become_consequential_in_stage_order(self) -> None:
        root = version(
            "root-v1",
            "root",
            dependencies=(
                dependency(
                    "dep",
                    applicability=Predicate("eq", "applies", True),
                    satisfied_when=Predicate("eq", "satisfied", True),
                ),
            ),
        )
        snapshot = KnowledgeSnapshot({}, (), (root,))

        applicability = select_procedure_dependencies(snapshot, root, facts(), EVALUATION_DATE)
        self.assertEqual(applicability.missing_facts, frozenset({"applies"}))
        self.assertNotIn("satisfied", applicability.missing_facts)

        satisfaction = select_procedure_dependencies(
            snapshot,
            root,
            facts(applies=True),
            EVALUATION_DATE,
        )
        self.assertEqual(satisfaction.missing_facts, frozenset({"satisfied"}))

    def test_resolved_target_produces_satisfied_or_blocking_without_recursing(self) -> None:
        nested_malformed = dependency("nested", relation="unsupported")
        target = version(
            "target-v1",
            "target",
            dependencies=(nested_malformed,),
        )
        root = version(
            "root-v1",
            "root",
            dependencies=(
                dependency("blocking", order=20),
                dependency("satisfied", order=10),
            ),
        )
        snapshot = KnowledgeSnapshot({}, (), (root, target))
        selection = select_procedure_dependencies(
            snapshot,
            root,
            facts(satisfied=False),
            EVALUATION_DATE,
        )
        self.assertEqual(
            tuple(item.id for item in selection.dependencies),
            ("satisfied", "blocking"),
        )
        self.assertTrue(all(item.status == "blocking" for item in selection.dependencies))
        self.assertTrue(
            all(item.target_procedure_version_id == "target-v1" for item in selection.dependencies)
        )
        self.assertFalse(selection.configuration_invalid)

        satisfied = select_procedure_dependencies(
            snapshot,
            root,
            facts(satisfied=True),
            EVALUATION_DATE,
        )
        self.assertTrue(all(item.status == "satisfied" for item in satisfied.dependencies))

    def test_unsupported_target_is_local_metadata(self) -> None:
        root = version("root-v1", "root", dependencies=(dependency("dep", target="missing"),))
        snapshot = KnowledgeSnapshot({}, (), (root,))
        selection = select_procedure_dependencies(
            snapshot,
            root,
            facts(satisfied=False),
            EVALUATION_DATE,
        )
        self.assertEqual(selection.dependencies[0].status, "unsupported_target")
        self.assertIsNone(selection.dependencies[0].target_procedure_version_id)
        self.assertFalse(selection.configuration_invalid)

    def test_untrusted_dependency_stays_visible_without_asking_or_blocking(self) -> None:
        for state in ("needs_reverification", "stale", "disputed", "unknown"):
            with self.subTest(state=state):
                root = version(
                    "root-v1",
                    "root",
                    dependencies=(
                        dependency(
                            "dep",
                            applicability=Predicate("eq", "applies", True),
                            state=state,
                        ),
                    ),
                )
                snapshot = KnowledgeSnapshot({}, (), (root,))
                selection = select_procedure_dependencies(
                    snapshot,
                    root,
                    facts(),
                    EVALUATION_DATE,
                )
                self.assertEqual(selection.missing_facts, frozenset())
                self.assertEqual(selection.dependencies[0].status, "inconclusive")
                self.assertTrue(selection.dependencies[0].sources)

    def test_target_version_configuration_defect_is_local_to_dependency(self) -> None:
        first = version(
            "target-v1",
            "target",
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
        )
        second = version(
            "target-v2",
            "target",
            effective_from=date(2026, 6, 1),
            effective_to=date(2026, 12, 31),
        )
        root = version("root-v1", "root", dependencies=(dependency("dep"),))
        snapshot = KnowledgeSnapshot({}, (), (root, first, second))
        selection = select_procedure_dependencies(
            snapshot,
            root,
            facts(satisfied=False),
            EVALUATION_DATE,
        )
        self.assertEqual(selection.dependencies[0].status, "inconclusive")
        self.assertFalse(selection.configuration_invalid)


if __name__ == "__main__":
    unittest.main()
