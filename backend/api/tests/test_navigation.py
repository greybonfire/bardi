from __future__ import annotations

from unittest.mock import patch

from django.db import DatabaseError, connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from knowledge.domain import KnowledgeSnapshotLoadError
from knowledge.models import Service


class NavigationHttpContractTests(SimpleTestCase):
    @patch("api.api.list_active_services")
    def test_navigation_shape_contains_no_authoring_metadata(self, listing) -> None:  # type: ignore[no-untyped-def]
        listing.return_value = {
            "services": [{"id": "a.service", "title": {"ar": "خدمة", "en": "Service"}}]
        }
        response = self.client.get("/v1/services")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), listing.return_value)
        rendered = response.content.decode()
        for forbidden in ("candidate", "question", "predicate", "version", "publisher"):
            self.assertNotIn(forbidden, rendered.lower())

    @patch("api.api.list_active_services", side_effect=DatabaseError("database unavailable"))
    def test_database_error_keeps_existing_inconclusive_response(self, _listing) -> None:  # type: ignore[no-untyped-def]
        response = self.client.get("/v1/services")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "type": "inconclusive",
                "reason": "knowledge_unavailable",
                "message": "Knowledge is unavailable.",
            },
        )

    @patch("api.api.list_active_services", side_effect=KnowledgeSnapshotLoadError(()))
    def test_snapshot_configuration_error_keeps_existing_invalid_response(self, _listing) -> None:  # type: ignore[no-untyped-def]
        response = self.client.get("/v1/services")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {
                "type": "invalid",
                "diagnostics": [{"code": "knowledge_snapshot_invalid", "path": []}],
            },
        )


class NavigationHttpDatabaseTests(TestCase):
    def test_real_default_navigation_returns_exact_empty_shape(self) -> None:
        response = self.client.get("/v1/services")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"services": []})

    def test_real_default_navigation_wiring_is_one_query_and_active_only(self) -> None:
        Service.objects.create(semantic_id="http.z", text_ar="ز", text_en="Z", is_active=True)
        Service.objects.create(semantic_id="http.a", text_ar="أ", text_en="A", is_active=False)
        Service.objects.create(semantic_id="http.A", text_ar="ألف", text_en="Alpha", is_active=True)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/v1/services")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "services": [
                    {"id": "http.A", "title": {"ar": "ألف", "en": "Alpha"}},
                    {"id": "http.z", "title": {"ar": "ز", "en": "Z"}},
                ]
            },
        )
        self.assertEqual(len(queries), 1)
