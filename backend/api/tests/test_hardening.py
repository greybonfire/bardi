from __future__ import annotations

import json
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from api import rate_limit
from api.rate_limit import evaluate_rate_limit, reset_rate_limit_state


class PublicApiHardeningTests(SimpleTestCase):
    def setUp(self) -> None:
        reset_rate_limit_state()

    def tearDown(self) -> None:
        reset_rate_limit_state()

    @override_settings(
        PUBLIC_API_RATE_LIMIT_ENABLED=True,
        PUBLIC_API_RATE_LIMIT_REQUESTS=2,
        PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS=60,
        PUBLIC_API_CLIENT_IP_HEADER="",
    )
    @patch("api.api.list_active_services")
    def test_public_api_rate_limit_is_stable_per_client_and_route(self, listing) -> None:  # type: ignore[no-untyped-def]
        listing.return_value = {"services": []}

        first = self.client.get("/v1/services", REMOTE_ADDR="203.0.113.10")
        second = self.client.get("/v1/services", REMOTE_ADDR="203.0.113.10")
        limited = self.client.get("/v1/services", REMOTE_ADDR="203.0.113.10")
        other_client = self.client.get("/v1/services", REMOTE_ADDR="203.0.113.11")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(
            limited.json(),
            {"type": "invalid", "diagnostics": [{"code": "rate_limited", "path": []}]},
        )
        self.assertGreaterEqual(int(limited["Retry-After"]), 1)
        self.assertEqual(limited["Cache-Control"], "no-store")
        self.assertEqual(other_client.status_code, 200)
        self.assertEqual(listing.call_count, 3)

    @override_settings(
        PUBLIC_API_RATE_LIMIT_ENABLED=True,
        PUBLIC_API_RATE_LIMIT_REQUESTS=5,
        PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS=60,
        PUBLIC_API_CLIENT_IP_HEADER="",
    )
    def test_rate_limit_state_never_contains_raw_client_or_request_facts(self) -> None:
        client = "203.0.113.44"
        secret = "DISTINCTIVE-RATE-LIMIT-FACT"
        request = RequestFactory().post(
            "/v1/planning",
            data=json.dumps({"facts": {"answer": secret}}),
            content_type="application/json",
            REMOTE_ADDR=client,
        )

        decision = evaluate_rate_limit(request, now=120.0)

        self.assertFalse(decision.limited)
        state = repr(rate_limit._buckets)
        self.assertNotIn(client, state)
        self.assertNotIn(secret, state)

    @patch("api.api.list_active_services")
    def test_unexpected_navigation_failure_is_sanitized_even_with_debug(self, listing) -> None:  # type: ignore[no-untyped-def]
        secret = "DISTINCTIVE-NAVIGATION-FAILURE"
        listing.side_effect = RuntimeError(secret)

        with override_settings(DEBUG=True):
            response = self.client.get("/v1/services")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {"type": "invalid", "diagnostics": [{"code": "internal_error", "path": []}]},
        )
        self.assertNotIn(secret, response.content.decode())
