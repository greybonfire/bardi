from __future__ import annotations

from datetime import date
from typing import Any, cast

from django.test import SimpleTestCase
from planning.catalog import LocalizedText
from planning.public import PlanResult, PublicRouting, PublicServicePoint, PublicSource

from api.application import project_result


class ServicePointRoutingContractTests(SimpleTestCase):
    def result(self, status: str = "resolved") -> PlanResult:
        source = PublicSource(
            "source",
            "authority",
            "Official office page",
            "https://example.test/office",
            "official",
            date(2026, 9, 1),
        )
        destination = PublicServicePoint(
            "point",
            "point.v1",
            "association",
            LocalizedText("المكتب", "Office"),
            LocalizedText("العنوان", "Address"),
            "unknown",
            date(2026, 1, 1),
            None,
            (source,),
        )
        return PlanResult(
            "service",
            "procedure",
            "procedure.v1",
            LocalizedText("خطة", "Plan"),
            routing=PublicRouting(
                status,  # type: ignore[arg-type]
                (destination,) if status != "unresolved" else (),
                (source,) if status != "resolved" else (),
            ),
        )

    def test_exact_localized_association_distinct_whitelist(self) -> None:
        projected = project_result(self.result(), "ar")["routing"]
        self.assertEqual(
            projected,
            {
                "status": "resolved",
                "destinations": [
                    {
                        "service_point_id": "point",
                        "service_point_version_id": "point.v1",
                        "association_id": "association",
                        "name": "المكتب",
                        "address": "العنوان",
                        "availability": "unknown",
                        "effective_from": date(2026, 1, 1),
                        "effective_to": None,
                        "sources": [
                            {
                                "id": "source",
                                "authority_id": "authority",
                                "title": "Official office page",
                                "locator": "https://example.test/office",
                                "classification": "official",
                                "retrieved_on": date(2026, 9, 1),
                            }
                        ],
                    }
                ],
                "verification_sources": [],
            },
        )
        serialized = repr(projected)
        for private in ("predicate", "missing_fact", "evidence_link", "passage", "trace"):
            self.assertNotIn(private, serialized)

    def test_all_statuses_have_an_explicit_routing_object(self) -> None:
        for status in ("resolved", "partially_resolved", "unresolved"):
            routing = cast(dict[str, Any], project_result(self.result(status), "en")["routing"])
            self.assertEqual(routing["status"], status)
            self.assertEqual(len(routing["verification_sources"]), int(status != "resolved"))
