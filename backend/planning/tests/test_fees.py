from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date

from planning import (
    AuthoritySnapshot,
    EligibilityBasisSnapshot,
    EvidenceLinkSnapshot,
    FeeSnapshot,
    LocalizedText,
    Predicate,
    PreparedFacts,
    ProcedureVersionSnapshot,
    SourceSnapshot,
)
from planning.fees import select_fees


class FeeSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = SourceSnapshot(
            "source",
            AuthoritySnapshot("authority", LocalizedText("جهة", "Authority")),
            "Official fee page",
            "https://example.test/fees",
            "official",
            date(2026, 1, 1),
        )
        self.evidence = EvidenceLinkSnapshot(
            "fee passage",
            "fee table",
            "ordinary service",
            "supports",
            "current",
            (self.source,),
            verified_on=date(2026, 1, 1),
        )
        self.facts = PreparedFacts({"ok": True}, frozenset({"ok"}), {})

    def fee(
        self,
        identifier: str,
        order: int,
        *,
        value_state: str = "known",
        amount: int | None = 100,
        minimum_amount: int | None = None,
        maximum_amount: int | None = None,
        verification_state: str = "current",
        applicability: Predicate | None = None,
        scope: str = "procedure",
        evidence: tuple[EvidenceLinkSnapshot, ...] | None = None,
    ) -> FeeSnapshot:
        return FeeSnapshot(
            identifier,
            LocalizedText(identifier, identifier),
            value_state,
            amount,
            minimum_amount,
            maximum_amount,
            "EGP",
            "service_fee",
            order,
            applicability,
            scope,
            "basis" if scope == "eligibility_basis" else None,
            None,
            None,
            verification_state,  # type: ignore[arg-type]
            date(2026, 1, 1),
            None,
            (self.evidence,) if evidence is None and value_state != "unknown" else (evidence or ()),
        )

    def version(self, *fees: FeeSnapshot) -> ProcedureVersionSnapshot:
        return ProcedureVersionSnapshot(
            "v",
            "p",
            LocalizedText("خ", "V"),
            Predicate("eq", "ok", True),
            "v1",
            "published",
            None,
            None,
            eligibility_bases=(EligibilityBasisSnapshot("basis"),),
            fees=fees,
        )

    def test_all_value_states_are_explicit_and_deterministic(self) -> None:
        known = self.fee("known", 20, amount=705)
        range_fee = self.fee(
            "range",
            10,
            value_state="range",
            amount=None,
            minimum_amount=100,
            maximum_amount=150,
        )
        unknown = self.fee("unknown", 30, value_state="unknown", amount=None)
        unverified = self.fee(
            "unverified",
            40,
            value_state="unverified",
            amount=900,
            verification_state="disputed",
        )

        selected = select_fees(
            self.version(known, range_fee, unknown, unverified),
            self.facts,
            date(2026, 2, 1),
        )

        self.assertEqual(
            [item.id for item in selected.items],
            ["range", "known", "unknown", "unverified"],
        )
        by_id = {item.id: item for item in selected.items}
        self.assertEqual(by_id["known"].amount, 705)
        self.assertFalse(by_id["known"].current_value_unknown)
        self.assertEqual((by_id["range"].minimum_amount, by_id["range"].maximum_amount), (100, 150))
        self.assertEqual(by_id["unknown"].value_state, "unknown")
        self.assertIsNone(by_id["unknown"].amount)
        self.assertTrue(by_id["unknown"].current_value_unknown)
        self.assertEqual(by_id["unverified"].value_state, "unverified")
        self.assertIsNone(by_id["unverified"].amount)
        self.assertTrue(by_id["unverified"].current_value_unknown)
        self.assertEqual(by_id["unverified"].sources[0].id, "source")

    def test_unreliable_fee_is_local_and_never_exposes_its_amount(self) -> None:
        reliable = self.fee("reliable", 1, amount=100)
        disputed = self.fee(
            "disputed",
            2,
            amount=999,
            verification_state="disputed",
        )
        stale = replace(
            self.fee("stale", 3, amount=888),
            verification_state="stale",
            effective_to=date(2026, 1, 31),
        )

        selected = select_fees(
            self.version(reliable, disputed, stale), self.facts, date(2026, 2, 1)
        )

        self.assertEqual([item.id for item in selected.items], ["reliable", "disputed"])
        self.assertEqual(selected.items[0].amount, 100)
        self.assertIsNone(selected.items[1].amount)
        self.assertEqual(selected.items[1].value_state, "unverified")

    def test_only_trusted_unknown_applicability_requests_more_facts(self) -> None:
        rule = Predicate("eq", "missing", True)
        current = self.fee("current", 1, applicability=rule)
        untrusted = self.fee(
            "untrusted",
            2,
            applicability=rule,
            verification_state="needs_reverification",
        )

        current_selection = select_fees(self.version(current), self.facts, date(2026, 2, 1))
        self.assertEqual(current_selection.missing_facts, frozenset({"missing"}))

        untrusted_selection = select_fees(self.version(untrusted), self.facts, date(2026, 2, 1))
        self.assertFalse(untrusted_selection.missing_facts)
        self.assertFalse(untrusted_selection.items)

    def test_current_basis_scoped_fee_fails_closed_until_basis_resolution(self) -> None:
        fee = self.fee("basis-fee", 1, scope="eligibility_basis")
        version = self.version(fee)

        unresolved = select_fees(version, self.facts, date(2026, 2, 1))
        self.assertTrue(unresolved.basis_resolution_required)
        self.assertFalse(unresolved.items)

        excluded = select_fees(version, self.facts, date(2026, 2, 1), matched_basis_ids=set())
        self.assertFalse(excluded.basis_resolution_required)
        self.assertFalse(excluded.items)

        included = select_fees(version, self.facts, date(2026, 2, 1), matched_basis_ids={"basis"})
        self.assertEqual([item.id for item in included.items], ["basis-fee"])


if __name__ == "__main__":
    unittest.main()
