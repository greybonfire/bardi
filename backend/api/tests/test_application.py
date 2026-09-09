from __future__ import annotations

from datetime import date

from django.test import SimpleTestCase
from knowledge.navigation import ServiceNavigationEntry
from planning import (
    FactDefinition,
    InconclusiveResult,
    KnowledgeSnapshot,
    LocalizedText,
    PlanningInput,
    PlanResult,
    ServiceSnapshot,
)

from api.application import execute_planning, list_active_services, project_result


class ApplicationBoundaryTests(SimpleTestCase):
    def setUp(self) -> None:
        self.snapshot = KnowledgeSnapshot(
            {"when": FactDefinition("when", "date")},
            (
                ServiceSnapshot("z", LocalizedText("ز", "Z"), (), (), (), True),
                ServiceSnapshot("a", LocalizedText("أ", "A"), (), (), (), False),
                ServiceSnapshot("A", LocalizedText("ألف", "Alpha"), (), (), (), True),
                ServiceSnapshot("a-10", LocalizedText("عشرة", "Ten"), (), (), (), True),
            ),
        )

    def test_snapshot_navigation_is_active_sorted_and_whitelisted(self) -> None:
        self.assertEqual(
            list_active_services(snapshot_loader=lambda: self.snapshot),
            {
                "services": [
                    {"id": "A", "title": {"ar": "ألف", "en": "Alpha"}},
                    {"id": "a-10", "title": {"ar": "عشرة", "en": "Ten"}},
                    {"id": "z", "title": {"ar": "ز", "en": "Z"}},
                ]
            },
        )

    def test_navigation_injection_is_detached_sorted_and_whitelisted(self) -> None:
        entries = (
            ServiceNavigationEntry("item-10", "عشرة", "Ten"),
            ServiceNavigationEntry("item-2", "اثنان", "Two"),
            ServiceNavigationEntry("Item!", "عنصر", "Item"),
            ServiceNavigationEntry("item.1", "واحد", "One"),
            ServiceNavigationEntry("خدمة", "خدمة", "Service"),
        )
        calls: list[str] = []

        def loader() -> tuple[ServiceNavigationEntry, ...]:
            calls.append("loaded")
            return entries

        self.assertEqual(
            list_active_services(navigation_loader=loader),
            {
                "services": [
                    {"id": entry.semantic_id, "title": {"ar": entry.text_ar, "en": entry.text_en}}
                    for entry in sorted(entries, key=lambda item: item.semantic_id)
                ]
            },
        )
        self.assertEqual(calls, ["loaded"])

    def test_snapshot_loader_takes_precedence_over_navigation_loader(self) -> None:
        calls: list[str] = []

        def navigation_loader() -> tuple[ServiceNavigationEntry, ...]:
            calls.append("navigation")
            return (ServiceNavigationEntry("wrong", "خطأ", "Wrong"),)

        self.assertEqual(
            list_active_services(
                navigation_loader=navigation_loader,
                snapshot_loader=lambda: self.snapshot,
            )["services"],
            [
                {"id": "A", "title": {"ar": "ألف", "en": "Alpha"}},
                {"id": "a-10", "title": {"ar": "عشرة", "en": "Ten"}},
                {"id": "z", "title": {"ar": "ز", "en": "Z"}},
            ],
        )
        self.assertEqual(calls, [])

    def test_snapshot_is_fully_loaded_before_detached_input_reaches_planner(self) -> None:
        events: list[str] = []
        submitted = {"when": "2026-09-01"}

        def loader() -> KnowledgeSnapshot:
            events.append("loaded")
            return self.snapshot

        def planner(snapshot: KnowledgeSnapshot, value: PlanningInput):  # type: ignore[no-untyped-def]
            events.append("planned")
            self.assertIs(snapshot, self.snapshot)
            self.assertEqual(value.facts["when"], date(2026, 9, 1))
            self.assertIsNot(value.facts, submitted)
            return InconclusiveResult("no_matching_researched_procedure")

        output = execute_planning(
            PlanningInput("z", submitted, "en", date(2026, 9, 1)),
            snapshot_loader=loader,
            planner=planner,
        )
        self.assertEqual(events, ["loaded", "planned"])
        self.assertEqual(output["type"], "inconclusive")

    def test_reserved_plan_projection_has_only_the_public_contract_fields(self) -> None:
        result = PlanResult("z", "procedure", "version", LocalizedText("خطة", "Plan"))
        self.assertEqual(
            project_result(result, "ar"),
            {
                "type": "plan",
                "service_id": "z",
                "procedure_id": "procedure",
                "procedure_version_id": "version",
                "title": "خطة",
                "eligibility_bases": [],
                "inconclusive_basis_ids": [],
                "inconclusive_sections": [],
                "dependencies": [],
                "checklist_items": [],
                "steps": [],
                "fees": [],
                "warnings": [],
                "routing": {
                    "status": "unresolved",
                    "destinations": [],
                    "verification_sources": [],
                },
            },
        )

    def test_projection_does_not_echo_facts(self) -> None:
        secret = "DISTINCTIVE-SECRET"
        output = execute_planning(
            PlanningInput("missing", {"unknown": secret}, "en", date(2026, 9, 1)),
            snapshot_loader=lambda: self.snapshot,
        )
        self.assertNotIn(secret, str(output))
        self.assertNotIn("facts", str(output))
