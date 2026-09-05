from __future__ import annotations

import unittest
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
)
from planning.eligibility_bases import select_eligibility_bases

EVALUATION_DATE = date(2026, 9, 1)


def evidence() -> tuple[EvidenceLinkSnapshot, ...]:
    source = SourceSnapshot(
        "source",
        AuthoritySnapshot("authority", LocalizedText("جهة", "Authority")),
        "Source",
        "https://example.test/source",
        "official",
        date(2026, 8, 1),
    )
    return (
        EvidenceLinkSnapshot(
            "Passage",
            "Section",
            "Basis assertion",
            "supports",
            "current",
            (source,),
            verified_on=date(2026, 8, 1),
        ),
    )


def basis(
    semantic_id: str,
    *,
    order: int = 0,
    reachability: Predicate | None = None,
    qualification: Predicate | None = None,
    state: str = "current",
) -> EligibilityBasisSnapshot:
    return EligibilityBasisSnapshot(
        semantic_id,
        LocalizedText(f"{semantic_id}-ar", semantic_id),
        reachability,
        qualification or Predicate("eq", "qualification", True),
        order,
        None,
        None,
        state,  # type: ignore[arg-type]
        date(2026, 8, 1),
        None,
        evidence(),
    )


def version(*bases: EligibilityBasisSnapshot) -> ProcedureVersionSnapshot:
    return ProcedureVersionSnapshot(
        "version",
        "procedure",
        LocalizedText("نسخة", "Version"),
        Predicate("eq", "procedure", True),
        "v1",
        "published",
        None,
        None,
        eligibility_bases=bases,
    )


def facts(**values: object) -> PreparedFacts:
    return PreparedFacts(values, frozenset(values), {})  # type: ignore[arg-type]


class EligibilityBasisSelectionTests(unittest.TestCase):
    def test_false_reachability_never_inspects_qualification_missing_facts(self) -> None:
        selection = select_eligibility_bases(
            version(
                basis(
                    "father-route",
                    reachability=Predicate("eq", "father_alive", True),
                    qualification=Predicate("eq", "qualification", True),
                )
            ),
            facts(father_alive=False),
            EVALUATION_DATE,
        )

        self.assertEqual(selection.missing_facts, frozenset())
        self.assertEqual(selection.bases, ())
        self.assertTrue(selection.no_applicable_basis)

    def test_unknown_reachability_exposes_only_reachability_facts(self) -> None:
        selection = select_eligibility_bases(
            version(
                basis(
                    "father-route",
                    reachability=Predicate("eq", "father_alive", True),
                    qualification=Predicate("eq", "qualification", True),
                )
            ),
            facts(),
            EVALUATION_DATE,
        )

        self.assertEqual(selection.missing_facts, frozenset({"father_alive"}))
        self.assertNotIn("qualification", selection.missing_facts)

    def test_true_reachability_allows_qualification_facts_to_become_consequential(self) -> None:
        selection = select_eligibility_bases(
            version(
                basis(
                    "father-route",
                    reachability=Predicate("eq", "father_alive", True),
                    qualification=Predicate("eq", "qualification", True),
                )
            ),
            facts(father_alive=True),
            EVALUATION_DATE,
        )

        self.assertEqual(selection.missing_facts, frozenset({"qualification"}))

    def test_all_matches_remain_ordered_non_ranked_alternatives(self) -> None:
        selection = select_eligibility_bases(
            version(
                basis("second-authored", order=20),
                basis("first-authored", order=10),
                basis("untrusted-match", order=30, state="needs_reverification"),
            ),
            facts(qualification=True),
            EVALUATION_DATE,
        )

        self.assertEqual(
            tuple(item.id for item in selection.bases),
            ("first-authored", "second-authored", "untrusted-match"),
        )
        self.assertEqual(
            selection.trusted_matched_basis_ids,
            frozenset({"first-authored", "second-authored"}),
        )
        self.assertEqual(selection.inconclusive_basis_ids, ("untrusted-match",))

    def test_untrusted_unknown_basis_is_local_and_does_not_ask_questions(self) -> None:
        for state in ("stale", "disputed", "unknown"):
            with self.subTest(state=state):
                selection = select_eligibility_bases(
                    version(
                        basis(
                            "uncertain",
                            reachability=Predicate("eq", "reachability", True),
                            state=state,
                        )
                    ),
                    facts(),
                    EVALUATION_DATE,
                )
                self.assertEqual(selection.missing_facts, frozenset())
                self.assertEqual(selection.inconclusive_basis_ids, ("uncertain",))
                self.assertFalse(selection.no_applicable_basis)

    def test_needs_reverification_unknown_basis_remains_factually_resolvable(self) -> None:
        selection = select_eligibility_bases(
            version(
                basis(
                    "candidate",
                    reachability=Predicate("eq", "reachability", True),
                    state="needs_reverification",
                )
            ),
            facts(),
            EVALUATION_DATE,
        )

        self.assertEqual(selection.missing_facts, frozenset({"reachability"}))
        self.assertEqual(selection.inconclusive_basis_ids, ())

    def test_missing_qualification_is_configuration_invalid(self) -> None:
        malformed = EligibilityBasisSnapshot(
            "malformed",
            LocalizedText("أساس", "Basis"),
            qualification=None,
            verification_state="current",
            verified_on=date(2026, 8, 1),
            evidence_links=evidence(),
        )
        selection = select_eligibility_bases(version(malformed), facts(), EVALUATION_DATE)
        self.assertTrue(selection.configuration_invalid)


if __name__ == "__main__":
    unittest.main()
