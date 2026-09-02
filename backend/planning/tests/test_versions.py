from __future__ import annotations

import inspect
import unittest
from dataclasses import FrozenInstanceError
from datetime import date

from planning import (
    FactDefinition,
    KnowledgeSnapshot,
    LocalizedText,
    Predicate,
    ProcedureVersionConfigurationDefect,
    ProcedureVersionResolved,
    ProcedureVersionSnapshot,
    ProcedureVersionUnavailable,
    resolve_procedure_version,
)


def version(
    semantic_id: str,
    start: date | None,
    end: date | None,
    *,
    state: str = "published",
    procedure: str = "procedure",
    contract: str = "v1",
) -> ProcedureVersionSnapshot:
    return ProcedureVersionSnapshot(
        semantic_id,
        procedure,
        LocalizedText("ع", "English"),
        Predicate("eq", "a", True),
        contract,
        state,
        start,
        end,
    )


def snapshot(*versions: ProcedureVersionSnapshot) -> KnowledgeSnapshot:
    return KnowledgeSnapshot({"a": FactDefinition("a", "boolean")}, (), versions)


class ProcedureVersionResolutionTests(unittest.TestCase):
    def test_inclusive_boundaries_and_unbounded_intervals(self) -> None:
        bounded = version("bounded", date(2025, 1, 1), date(2025, 1, 31))
        for value in (date(2025, 1, 1), date(2025, 1, 31)):
            outcome = resolve_procedure_version(snapshot(bounded), "procedure", value)
            self.assertIsInstance(outcome, ProcedureVersionResolved)
            assert isinstance(outcome, ProcedureVersionResolved)
            self.assertEqual(outcome.version.semantic_id, "bounded")
        self.assertIsInstance(
            resolve_procedure_version(
                snapshot(version("forever", None, None)), "procedure", date(1900, 1, 1)
            ),
            ProcedureVersionResolved,
        )

    def test_touching_and_unbounded_published_ranges_are_deterministic_defects(self) -> None:
        versions = (
            version("z", date(2025, 1, 1), date(2025, 2, 1)),
            version("a", date(2025, 2, 1), None),
        )
        for ordered in (versions, tuple(reversed(versions))):
            outcome = resolve_procedure_version(snapshot(*ordered), "procedure", date(2025, 1, 1))
            self.assertEqual(
                outcome,
                ProcedureVersionConfigurationDefect(
                    ("overlapping_published_intervals",),
                    ("a", "z"),
                    (next(item for item in ordered if item.semantic_id == "a"),),
                ),
            )

    def test_drafts_and_withdrawn_are_never_implicitly_visible(self) -> None:
        catalog = snapshot(
            version("draft", date(2026, 1, 1), None, state="draft"),
            version("withdrawn", None, date(2024, 1, 1), state="withdrawn"),
        )
        self.assertEqual(
            resolve_procedure_version(catalog, "procedure", date(2025, 1, 1)),
            ProcedureVersionUnavailable("no_published_version", ()),
        )

    def test_future_versions_are_upcoming_but_never_selected_early(self) -> None:
        future = version("future", date(2026, 1, 1), None)
        draft = version("future-draft", date(2025, 2, 1), None, state="draft")
        outcome = resolve_procedure_version(snapshot(future, draft), "procedure", date(2025, 1, 1))
        self.assertEqual(outcome, ProcedureVersionUnavailable("not_yet_effective", (future,)))

    def test_gap_and_empty_or_unknown_catalog_have_stable_reasons(self) -> None:
        expired = version("expired", None, date(2024, 1, 1))
        self.assertEqual(
            resolve_procedure_version(snapshot(expired), "procedure", date(2025, 1, 1)),
            ProcedureVersionUnavailable("no_applicable_version", ()),
        )
        self.assertEqual(
            resolve_procedure_version(snapshot(), "absent", date(2025, 1, 1)),
            ProcedureVersionUnavailable("unknown_procedure", ()),
        )

    def test_explicit_history_rejects_unknown_draft_and_future_but_allows_expired(self) -> None:
        expired = version("expired", None, date(2024, 1, 1), state="withdrawn")
        draft = version("draft", None, None, state="draft")
        future = version("future", date(2026, 1, 1), None)
        catalog = snapshot(expired, draft, future)
        resolved = resolve_procedure_version(
            catalog, "procedure", date(2025, 1, 1), historical_version_id="expired"
        )
        self.assertEqual(resolved, ProcedureVersionResolved(expired, (future,), True))
        self.assertEqual(
            resolve_procedure_version(
                catalog, "procedure", date(2025, 1, 1), historical_version_id="draft"
            ),
            ProcedureVersionUnavailable("draft_historical_version", (future,)),
        )
        self.assertEqual(
            resolve_procedure_version(
                catalog, "procedure", date(2025, 1, 1), historical_version_id="future"
            ),
            ProcedureVersionUnavailable("historical_version_not_yet_effective", (future,)),
        )

    def test_malformed_metadata_is_reported_without_incidental_exceptions(self) -> None:
        malformed = version("bad", date(2025, 2, 1), date(2025, 1, 1), contract="v2")
        outcome = resolve_procedure_version(snapshot(malformed), "procedure", date(2025, 1, 1))
        self.assertEqual(
            outcome,
            ProcedureVersionConfigurationDefect(
                ("invalid_effective_interval", "unsupported_rules_contract"),
                ("bad",),
                (malformed,),
            ),
        )

    def test_snapshots_results_and_input_sequences_are_immutable_copies(self) -> None:
        items = [version("one", None, None)]
        catalog = KnowledgeSnapshot({}, (), items)  # type: ignore[arg-type]
        items.clear()
        self.assertEqual(len(catalog.procedure_versions), 1)
        outcome = resolve_procedure_version(catalog, "procedure", date(2025, 1, 1))
        with self.assertRaises(FrozenInstanceError):
            outcome.historical = True  # type: ignore[union-attr,misc]

    def test_resolver_has_no_django_boundary_and_does_not_evaluate_applicability(self) -> None:
        import planning.versions as module

        self.assertNotIn("django", inspect.getsource(module))
        self.assertNotIn("evaluate(", inspect.getsource(module.resolve_procedure_version))


if __name__ == "__main__":
    unittest.main()
