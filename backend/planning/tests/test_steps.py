from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date

from planning import (
    AuthoritySnapshot,
    EligibilityBasisSnapshot,
    EvidenceLinkSnapshot,
    LocalizedText,
    Predicate,
    PreparedFacts,
    ProcedureVersionSnapshot,
    SourceSnapshot,
    StepSnapshot,
)
from planning.steps import select_steps


class StepSelectionTests(unittest.TestCase):
    def test_order_scope_uncertainty_and_compact_provenance_are_deterministic(self) -> None:
        source = SourceSnapshot(
            "source",
            AuthoritySnapshot("authority", LocalizedText("جهة", "Authority")),
            "Title",
            "https://example.test",
            "official",
            date(2026, 1, 1),
        )
        evidence = EvidenceLinkSnapshot(
            "private",
            "section",
            "context",
            "supports",
            "current",
            (source,),
            verified_on=date(2026, 1, 1),
        )

        def step(identifier: str, order: int, scope: str = "procedure") -> StepSnapshot:
            return StepSnapshot(
                identifier,
                LocalizedText(identifier, identifier),
                "prepare",
                order,
                0,
                None,
                scope,
                "basis" if scope == "eligibility_basis" else None,
                None,
                None,
                "current",
                date(2026, 1, 1),
                None,
                (evidence,),
            )

        version = ProcedureVersionSnapshot(
            "v",
            "p",
            LocalizedText("خ", "V"),
            Predicate("eq", "ok", True),
            "v1",
            "published",
            None,
            None,
            eligibility_bases=(EligibilityBasisSnapshot("basis"),),
            steps=(step("b", 2), step("a", 1), step("c", 0, "eligibility_basis")),
        )
        facts = PreparedFacts({"ok": True}, frozenset({"ok"}), {})
        unresolved = select_steps(version, facts, date(2026, 2, 1))
        self.assertEqual([item.id for item in unresolved.items], ["a", "b"])
        self.assertTrue(unresolved.basis_resolution_required)

        resolved = select_steps(version, facts, date(2026, 2, 1), matched_basis_ids={"basis"})
        self.assertEqual([item.id for item in resolved.items], ["c", "a", "b"])
        self.assertFalse(resolved.basis_resolution_required)
        self.assertEqual(resolved.items[0].sources[0].id, "source")

        trustworthy = step("trustworthy", 1)
        mixed = replace(
            version,
            steps=(
                trustworthy,
                replace(step("untrusted", 2), verification_state="needs_reverification"),
                replace(step("unknown", 3), applicability=Predicate("eq", "missing", True)),
            ),
        )
        selected = select_steps(mixed, facts, date(2026, 2, 1))
        self.assertEqual(tuple(item.id for item in selected.items), ("trustworthy",))
        self.assertEqual(selected.missing_facts, frozenset({"missing"}))
        self.assertTrue(selected.trust_inconclusive)


if __name__ == "__main__":
    unittest.main()
