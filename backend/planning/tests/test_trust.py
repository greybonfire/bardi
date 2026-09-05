from __future__ import annotations

import unittest
from datetime import date

from planning.trust import assess_trust


class SharedTrustTests(unittest.TestCase):
    evaluation_date = date(2026, 9, 1)

    def test_every_authored_state_has_an_explicit_decision(self) -> None:
        for state in (
            "current",
            "needs_reverification",
            "stale",
            "disputed",
            "unknown",
        ):
            with self.subTest(state=state):
                assessment = assess_trust(state, evaluation_date=self.evaluation_date)
                self.assertEqual(assessment.freshness.state, state)
                self.assertEqual(
                    assessment.disposition,
                    "assert_current" if state == "current" else "inconclusive",
                )

    def test_temporal_boundaries_are_inclusive(self) -> None:
        assessment = assess_trust(
            "current",
            evaluation_date=self.evaluation_date,
            effective_from=self.evaluation_date,
            effective_to=self.evaluation_date,
            retrieved_on=self.evaluation_date,
            verified_on=self.evaluation_date,
            reverify_on=self.evaluation_date,
        )
        self.assertEqual(assessment.disposition, "assert_current")
        self.assertEqual(assessment.freshness.state, "current")

    def test_future_or_due_current_material_is_locally_inconclusive(self) -> None:
        for dates, expected_state in (
            ({"effective_from": date(2026, 9, 2)}, "needs_reverification"),
            ({"reverify_on": date(2026, 8, 31)}, "needs_reverification"),
            ({"verified_on": date(2026, 9, 2)}, "unknown"),
            ({"retrieved_on": date(2026, 9, 2)}, "unknown"),
        ):
            with self.subTest(dates=dates):
                assessment = assess_trust("current", evaluation_date=self.evaluation_date, **dates)
                self.assertEqual(assessment.disposition, "inconclusive")
                self.assertEqual(assessment.freshness.state, expected_state)

    def test_explicit_stale_material_requires_prior_verification_for_context(self) -> None:
        established = assess_trust(
            "stale",
            evaluation_date=self.evaluation_date,
            verified_on=date(2026, 8, 1),
        )
        unestablished = assess_trust("stale", evaluation_date=self.evaluation_date)
        self.assertEqual(established.disposition, "context_only")
        self.assertEqual(established.freshness.state, "stale")
        self.assertEqual(unestablished.disposition, "inconclusive")

    def test_established_expired_material_is_dated_context_only(self) -> None:
        assessment = assess_trust(
            "current",
            evaluation_date=self.evaluation_date,
            effective_from=date(2025, 1, 1),
            effective_to=date(2026, 8, 31),
            retrieved_on=date(2026, 8, 30),
            verified_on=date(2026, 8, 31),
        )
        self.assertEqual(assessment.disposition, "context_only")
        self.assertEqual(assessment.freshness.state, "current")

    def test_later_evidence_cannot_be_back_projected_as_historical_context(self) -> None:
        for dates in (
            {"verified_on": date(2026, 9, 1), "retrieved_on": date(2026, 8, 30)},
            {"verified_on": date(2026, 8, 31), "retrieved_on": date(2026, 9, 1)},
            {"verified_on": None, "retrieved_on": date(2026, 8, 30)},
        ):
            with self.subTest(dates=dates):
                assessment = assess_trust(
                    "current",
                    evaluation_date=self.evaluation_date,
                    effective_to=date(2026, 8, 31),
                    **dates,
                )
                self.assertEqual(assessment.disposition, "inconclusive")
                self.assertEqual(assessment.freshness.state, "needs_reverification")

    def test_stale_material_cannot_use_later_evidence_as_historical_context(self) -> None:
        for dates in (
            {"verified_on": date(2025, 1, 1), "retrieved_on": date(2020, 1, 1)},
            {"verified_on": date(2020, 1, 1), "retrieved_on": date(2025, 1, 1)},
        ):
            with self.subTest(dates=dates):
                assessment = assess_trust(
                    "stale",
                    evaluation_date=self.evaluation_date,
                    effective_to=date(2020, 12, 31),
                    **dates,
                )
                self.assertEqual(assessment.disposition, "inconclusive")
                self.assertEqual(assessment.freshness.state, "stale")

    def test_old_noncurrent_material_is_not_reclassified_as_historical(self) -> None:
        for state in ("needs_reverification", "disputed", "unknown"):
            with self.subTest(state=state):
                assessment = assess_trust(
                    state,
                    evaluation_date=self.evaluation_date,
                    effective_to=date(2020, 1, 1),
                    verified_on=date(2020, 1, 1),
                    reverify_on=date(2020, 2, 1),
                )
                self.assertEqual(assessment.freshness.state, state)
                self.assertEqual(assessment.disposition, "inconclusive")
