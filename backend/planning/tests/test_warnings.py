from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date

from planning import (
    AuthoritySnapshot,
    EvidenceLinkSnapshot,
    LocalizedText,
    Predicate,
    PreparedFacts,
    ProcedureVersionSnapshot,
    SourceSnapshot,
    WarningSnapshot,
)
from planning.warnings import select_warnings


class WarningSelectionTests(unittest.TestCase):
    def test_product_warning_needs_no_evidence_and_is_ordered(self) -> None:
        def warning(identifier: str, order: int) -> WarningSnapshot:
            return WarningSnapshot(
                identifier,
                LocalizedText(identifier, identifier),
                "important",
                "product",
                "regeneration" if identifier == "regenerate" else "limitation",
                order,
                None,
                None,
                None,
                "current",
                date(2026, 1, 1),
                None,
                (),
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
            warnings=(warning("later", 2), warning("regenerate", 1)),
        )
        selected = select_warnings(
            version, PreparedFacts({"ok": True}, frozenset({"ok"}), {}), date(2026, 2, 1)
        )
        self.assertEqual([item.id for item in selected], ["regenerate", "later"])
        self.assertEqual(selected[0].sources, ())

        source = SourceSnapshot(
            "source",
            AuthoritySnapshot("authority", LocalizedText("جهة", "Authority")),
            "Title",
            "https://example.test",
            "official",
            date(2026, 1, 1),
        )
        evidence = EvidenceLinkSnapshot(
            "passage",
            "section",
            "context",
            "supports",
            "current",
            (source,),
            verified_on=date(2026, 1, 1),
        )
        administrative = replace(
            warning("administrative", 0), kind="administrative", role="general"
        )
        administrative = replace(administrative, evidence_links=(evidence,))
        mixed = replace(
            version,
            warnings=(
                replace(warning("untrusted", 0), verification_state="disputed"),
                administrative,
                warning("regenerate", 1),
            ),
        )
        selected = select_warnings(
            mixed, PreparedFacts({"ok": True}, frozenset({"ok"}), {}), date(2026, 2, 1)
        )
        self.assertEqual(tuple(item.id for item in selected), ("administrative", "regenerate"))
        self.assertEqual(selected[0].sources[0].id, "source")


if __name__ == "__main__":
    unittest.main()
