from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date
from typing import cast

from planning.catalog import (
    AuthoritySnapshot,
    ChecklistItemSnapshot,
    EvidenceLinkSnapshot,
    LocalizedText,
    ProcedureVersionSnapshot,
    SourceSnapshot,
)
from planning.checklists import select_checklist_items
from planning.facts import PreparedFacts
from planning.rules import Predicate
from planning.trust import VerificationState


class ChecklistSelectionTests(unittest.TestCase):
    def version(self, *items: ChecklistItemSnapshot) -> ProcedureVersionSnapshot:
        return ProcedureVersionSnapshot(
            "v1",
            "procedure",
            LocalizedText("نسخة", "Version"),
            Predicate("eq", "eligible", True),
            "v1",
            "published",
            None,
            None,
            checklist_items=items,
        )

    def item(
        self, *, state: str = "current", applicability: Predicate | None = None
    ) -> ChecklistItemSnapshot:
        authority = AuthoritySnapshot("authority", LocalizedText("جهة", "Authority"))
        source = SourceSnapshot(
            "source",
            authority,
            "Official page",
            "https://example.test",
            "official",
            date(2026, 1, 1),
        )
        evidence = EvidenceLinkSnapshot(
            "editorial secret passage",
            "section 1",
            "applies generally",
            "supports",
            "current",
            (source,),
            verified_on=date(2026, 1, 1),
        )
        return ChecklistItemSnapshot(
            "claim",
            LocalizedText("أحضر المستند", "Bring the document"),
            "official_requirement",
            None,
            1,
            1,
            0,
            2,
            applicability,
            "procedure",
            "",
            None,
            None,
            cast(VerificationState, state),
            date(2026, 1, 1),
            None,
            (evidence,),
        )

    def test_true_current_claim_is_selected_without_editorial_evidence(self) -> None:
        facts = PreparedFacts({"eligible": True}, frozenset({"eligible"}), {})
        result = select_checklist_items(
            self.version(self.item(applicability=Predicate("eq", "eligible", True))),
            facts,
            date(2026, 2, 1),
        )
        self.assertEqual(tuple(item.id for item in result.items), ("claim",))
        self.assertNotIn("editorial secret passage", repr(result.items))

    def test_false_unknown_and_untrusted_claims_are_not_asserted(self) -> None:
        false = select_checklist_items(
            self.version(self.item(applicability=Predicate("eq", "eligible", True))),
            PreparedFacts({"eligible": False}, frozenset({"eligible"}), {}),
            date(2026, 2, 1),
        )
        self.assertEqual(false.items, ())
        unknown = select_checklist_items(
            self.version(self.item(applicability=Predicate("eq", "eligible", True))),
            PreparedFacts({}, frozenset(), {}),
            date(2026, 2, 1),
        )
        self.assertEqual(unknown.missing_facts, frozenset({"eligible"}))
        stale = select_checklist_items(
            self.version(self.item(state="stale")),
            PreparedFacts({}, frozenset(), {}),
            date(2026, 2, 1),
        )
        self.assertEqual(stale.items, ())
        self.assertFalse(stale.trust_inconclusive)

        needs_review = select_checklist_items(
            self.version(self.item(state="needs_reverification")),
            PreparedFacts({}, frozenset(), {}),
            date(2026, 2, 1),
        )
        self.assertEqual(needs_review.items, ())
        self.assertTrue(needs_review.trust_inconclusive)

        practical = replace(
            self.item(state="needs_reverification"), classification="practical_preparation"
        )
        practical_stale = select_checklist_items(
            self.version(practical), PreparedFacts({}, frozenset(), {}), date(2026, 2, 1)
        )
        self.assertEqual(practical_stale.items, ())
        self.assertFalse(practical_stale.trust_inconclusive)

    def test_current_contradictory_evidence_blocks_assertion(self) -> None:
        facts = PreparedFacts({}, frozenset(), {})
        base = self.item()
        support = base.evidence_links[0]
        field_source = replace(
            support.sources[0],
            semantic_id="field-report",
            classification="field_report",
        )
        contradiction = replace(
            support,
            support_status="contradicts",
            sources=(field_source,),
        )

        result = select_checklist_items(
            self.version(replace(base, evidence_links=(support, contradiction))),
            facts,
            date(2026, 2, 1),
        )

        self.assertEqual(result.items, ())
        self.assertTrue(result.trust_inconclusive)

    def test_future_or_expired_evidence_is_not_back_projected(self) -> None:
        facts = PreparedFacts({}, frozenset(), {})
        base = self.item()
        evidence = base.evidence_links[0]
        future_link = replace(evidence, retrieved_on=date(2026, 3, 1))
        future_source = replace(evidence.sources[0], retrieved_on=date(2026, 3, 1))
        expired_source = replace(evidence.sources[0], reverify_on=date(2026, 1, 31))

        for item in (
            replace(base, evidence_links=(future_link,)),
            replace(base, evidence_links=(replace(evidence, sources=(future_source,)),)),
            replace(base, evidence_links=(replace(evidence, sources=(expired_source,)),)),
        ):
            with self.subTest(item=item):
                result = select_checklist_items(self.version(item), facts, date(2026, 2, 1))
                self.assertEqual(result.items, ())
                self.assertTrue(result.trust_inconclusive)
