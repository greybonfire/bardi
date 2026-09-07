from __future__ import annotations

import json
import logging
from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from core.observability import (
    OPERATIONAL_OBSERVABILITY_FIELDS,
    OperationalPrivacyFilter,
    StructuredOperationalFormatter,
    normalize_operational_route,
    operational_observability_metadata,
)


class OperationalObservabilityTests(SimpleTestCase):
    def test_structured_filter_and_formatter_are_strictly_allow_listed(self) -> None:
        secret = "DISTINCTIVE-OPERATIONAL-SECRET"
        record = logging.LogRecord(
            "bardi.ops",
            logging.ERROR,
            __file__,
            1,
            "failure %s",
            (secret,),
            (RuntimeError, RuntimeError(secret), None),
        )
        record.event = "request_completed"
        record.method = "POST"
        record.route = "/v1/planning"
        record.status_code = 500
        record.duration_ms = 17
        record.database_status = "not_checked"
        record.request_id = "a" * 32
        record.request = {"body": secret}
        record.facts = {"secret": secret}
        record.trace = {"actual_value": secret}

        OperationalPrivacyFilter().filter(record)
        rendered = StructuredOperationalFormatter().format(record)
        parsed = json.loads(rendered)

        self.assertEqual(
            set(parsed),
            {"timestamp", "level", *OPERATIONAL_OBSERVABILITY_FIELDS},
        )
        self.assertEqual(parsed["event"], "request_completed")
        self.assertEqual(parsed["route"], "/v1/planning")
        self.assertEqual(parsed["status_code"], 500)
        self.assertEqual(parsed["request_id"], "a" * 32)
        self.assertNotIn(secret, rendered)
        self.assertIsNone(record.exc_info)
        self.assertFalse(hasattr(record, "request"))
        self.assertFalse(hasattr(record, "facts"))
        self.assertFalse(hasattr(record, "trace"))

    def test_operational_routes_never_include_dynamic_path_segments(self) -> None:
        self.assertEqual(normalize_operational_route("/v1/planning"), "/v1/planning")
        self.assertEqual(normalize_operational_route("/health/ready/"), "/health/ready")
        self.assertEqual(normalize_operational_route("/admin/auth/user/17/change/"), "/admin/*")
        self.assertEqual(normalize_operational_route("/user-supplied/secret"), "other")

    def test_operational_metadata_normalizes_hostile_values(self) -> None:
        secret = "DISTINCTIVE-METADATA-SECRET"
        metadata = operational_observability_metadata(
            event=secret,
            method=secret,
            route=secret,
            status_code=9999,
            duration_ms=-10,
            database_status=secret,
            request_id=secret,
        )
        self.assertNotIn(secret, repr(metadata))
        self.assertEqual(metadata["event"], "request_completed")
        self.assertEqual(metadata["route"], "other")
        self.assertEqual(metadata["status_code"], 500)


class HealthEndpointTests(TransactionTestCase):
    def test_liveness_is_database_independent_and_uncached(self) -> None:
        statements: list[str] = []

        def capture_sql(execute, sql, params, many, context):  # type: ignore[no-untyped-def]
            statements.append(sql)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(capture_sql):
            response = self.client.get("/health/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(statements, [])
        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")

    def test_readiness_checks_postgresql_and_is_uncached(self) -> None:
        response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ready", "checks": {"database": "ok"}},
        )
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")

    @override_settings(OPERATIONAL_OBSERVABILITY_ENABLED=True)
    def test_readiness_failure_is_sanitized_and_structured(self) -> None:
        secret = "DISTINCTIVE-DATABASE-FAILURE"
        logger = logging.getLogger("bardi.ops")
        with (
            self.assertLogs(logger, level="INFO") as captured,
            patch("core.health.connection.cursor", side_effect=RuntimeError(secret)),
        ):
            response = self.client.get("/health/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "not_ready", "checks": {"database": "unavailable"}},
        )
        self.assertNotIn(secret, response.content.decode())
        self.assertNotIn(secret, "\n".join(captured.output))
