from __future__ import annotations

from unittest.mock import patch

from django.test import SimpleTestCase


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
