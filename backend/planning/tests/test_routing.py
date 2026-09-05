from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, timedelta

from planning.catalog import (
    AuthoritySnapshot,
    EvidenceLinkSnapshot,
    KnowledgeSnapshot,
    LocalizedText,
    ProcedureServicePointAssociationSnapshot,
    ProcedureVersionSnapshot,
    ServicePointSnapshot,
    ServicePointVersionSnapshot,
    SourceSnapshot,
)
from planning.facts import PreparedFacts
from planning.routing import select_service_points
from planning.rules import Predicate

TODAY = date(2026, 9, 5)
TRUE = Predicate("eq", fact="route", value=True)


def evidence(source_id: str) -> tuple[EvidenceLinkSnapshot, ...]:
    source = SourceSnapshot(
        source_id,
        AuthoritySnapshot("authority", LocalizedText("جهة", "Authority")),
        "Official routing",
        "https://example.test/routing",
        "official",
        TODAY,
    )
    return (
        EvidenceLinkSnapshot(
            "Passage",
            "Section",
            "Jurisdiction",
            "supports",
            "current",
            (source,),
            verified_on=TODAY,
        ),
    )


class RoutingSelectionTests(unittest.TestCase):
    def snapshot(
        self,
        associations: tuple[ProcedureServicePointAssociationSnapshot, ...],
        *,
        materials: tuple[ServicePointVersionSnapshot, ...] | None = None,
    ) -> tuple[KnowledgeSnapshot, ProcedureVersionSnapshot]:
        version = ProcedureVersionSnapshot(
            "procedure.v1",
            "procedure",
            LocalizedText("إجراء", "Procedure"),
            TRUE,
            "v1",
            "published",
            None,
            None,
            service_point_associations=associations,
        )
        default_materials = (
            ServicePointVersionSnapshot(
                "point-b.v1",
                "point-b",
                LocalizedText("عنوان ب", "B address"),
                "unknown",
                TODAY,
                TODAY,
                "current",
                TODAY,
                None,
                evidence("material-b"),
            ),
            ServicePointVersionSnapshot(
                "point-a.v1",
                "point-a",
                LocalizedText("عنوان أ", "A address"),
                "available",
                None,
                None,
                "current",
                TODAY,
                None,
                evidence("material-a"),
            ),
        )
        return (
            KnowledgeSnapshot(
                {},
                (),
                (version,),
                (
                    ServicePointSnapshot("point-b", LocalizedText("ب", "B")),
                    ServicePointSnapshot("point-a", LocalizedText("أ", "A")),
                ),
                default_materials if materials is None else materials,
            ),
            version,
        )

    def association(
        self,
        semantic_id: str,
        material_id: str,
        *,
        predicate: Predicate = TRUE,
        state: str = "current",
    ) -> ProcedureServicePointAssociationSnapshot:
        return ProcedureServicePointAssociationSnapshot(
            semantic_id,
            material_id,
            predicate,
            TODAY,
            TODAY,
            state,  # type: ignore[arg-type]
            TODAY,
            None,
            evidence(f"association-{semantic_id}"),
        )

    def test_multiple_destinations_are_association_distinct_and_sorted_without_ranking(
        self,
    ) -> None:
        associations = (
            self.association("route-z", "point-b.v1"),
            self.association("route-b", "point-a.v1"),
            self.association("route-a", "point-a.v1"),
        )
        snapshot, version = self.snapshot(associations)
        result = select_service_points(
            snapshot,
            version,
            PreparedFacts({"route": True}, frozenset({"route"}), {}),
            TODAY,
        )
        self.assertEqual(result.status, "resolved")
        self.assertEqual(
            [item.association_id for item in result.destinations],
            ["route-a", "route-b", "route-z"],
        )
        self.assertEqual(result.destinations[-1].availability, "unknown")
        self.assertFalse(hasattr(result.destinations[0], "rank"))

    def test_unknown_and_untrusted_routes_are_local(self) -> None:
        associations = (
            self.association("selected", "point-a.v1"),
            self.association(
                "unknown", "point-b.v1", predicate=Predicate("eq", fact="missing", value=True)
            ),
            self.association("untrusted", "point-b.v1", state="disputed"),
        )
        snapshot, version = self.snapshot(associations)
        result = select_service_points(
            snapshot,
            version,
            PreparedFacts({"route": True}, frozenset({"route"}), {}),
            TODAY,
        )
        self.assertEqual(result.status, "partially_resolved")
        self.assertEqual([item.association_id for item in result.destinations], ["selected"])
        self.assertEqual(
            [source.id for source in result.verification_sources],
            ["association-unknown", "association-untrusted"],
        )

    def test_future_provenance_is_not_back_projected_as_a_verification_path(self) -> None:
        association = self.association(
            "unknown", "point-a.v1", predicate=Predicate("eq", fact="missing", value=True)
        )
        link = association.evidence_links[0]
        future_source = replace(link.sources[0], retrieved_on=TODAY + timedelta(days=1))
        association = replace(
            association,
            evidence_links=(replace(link, sources=(future_source,)),),
        )
        snapshot, version = self.snapshot((association,))

        result = select_service_points(
            snapshot,
            version,
            PreparedFacts({"route": True}, frozenset({"route"}), {}),
            TODAY,
        )

        self.assertEqual(result.status, "unresolved")
        self.assertEqual(result.verification_sources, ())

    def test_missing_catalog_and_no_associations_are_unresolved(self) -> None:
        association = self.association("missing", "absent")
        snapshot, version = self.snapshot((association,), materials=())
        self.assertEqual(
            select_service_points(
                snapshot,
                version,
                PreparedFacts({"route": True}, frozenset({"route"}), {}),
                TODAY,
            ).status,
            "unresolved",
        )
        snapshot, version = self.snapshot(())
        self.assertEqual(
            select_service_points(
                snapshot,
                version,
                PreparedFacts({"route": True}, frozenset({"route"}), {}),
                TODAY,
            ).status,
            "unresolved",
        )


if __name__ == "__main__":
    unittest.main()
