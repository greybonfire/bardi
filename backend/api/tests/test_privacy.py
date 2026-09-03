from __future__ import annotations

import json
import logging
from io import StringIO
from typing import Any, cast
from unittest.mock import patch

from django.apps import apps
from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from knowledge.models import (
    FactDefinition,
    Procedure,
    Service,
    ServiceContradiction,
    ServiceProcedureCandidate,
    ServiceQuestion,
)
from knowledge.services import set_contradiction_facts

from api.privacy import (
    PLANNING_OBSERVABILITY_FIELDS,
    PLANNING_ROUTE,
    PlanningPrivacyFilter,
    planning_observability_metadata,
)


class _RequestWithSecrets:
    path = PLANNING_ROUTE
    method = "POST"
    body = b"DISTINCTIVE-REQUEST-BODY"
    data = {"fact": "DISTINCTIVE-REQUEST-DATA"}
    META = {"DISTINCTIVE-HEADER": "DISTINCTIVE-METADATA"}


class _HostileCapture(logging.Handler):
    """Retain LogRecords exactly as a downstream observability handler would."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class PrivacyLoggingTests(SimpleTestCase):
    def test_filter_replaces_every_possible_sensitive_record_field(self) -> None:
        secret = "DISTINCTIVE-SECRET"
        record = logging.LogRecord(
            "django.request",
            logging.ERROR,
            __file__,
            1,
            "failure %s",
            (secret,),
            (ValueError, ValueError(secret), None),
        )
        record.request = _RequestWithSecrets()
        record.status_code = 500
        record.error_code = "request_error"
        record.exc_text = f"traceback {secret}"
        record.stack_info = f"stack {secret}"
        record.planning_input = {"facts": {"secret": secret}}
        record.trace = {"actual_value": secret}
        record.selection = object()

        PlanningPrivacyFilter().filter(record)

        self.assertEqual(record.getMessage(), "POST /v1/planning 500 request_error")
        self.assertEqual(
            {
                key
                for key in record.__dict__
                if key not in logging.LogRecord("", 0, "", 0, "", (), None).__dict__
            },
            set(PLANNING_OBSERVABILITY_FIELDS),
        )
        self.assertFalse(hasattr(record, "request"))
        self.assertIsNone(record.exc_info)
        self.assertIsNone(record.exc_text)
        self.assertIsNone(record.stack_info)
        for attribute in ("planning_input", "trace", "selection"):
            self.assertFalse(hasattr(record, attribute))
        self.assertNotIn(secret, repr(record.__dict__))

    def test_filter_recognizes_django_server_arguments_and_fixed_route_metadata(self) -> None:
        for marker in (
            (500, "POST /v1/planning HTTP/1.1"),
            {"request": "POST /v1/planning"},
        ):
            record = logging.LogRecord("django.server", 40, __file__, 1, "%s", (), None)
            record.args = marker
            PlanningPrivacyFilter().filter(record)
            self.assertEqual(record.getMessage(), "POST /v1/planning 500 request_error")

        record = logging.LogRecord("bardi.api", 40, __file__, 1, "secret", (), None)
        record.route = PLANNING_ROUTE
        record.method = "POST"
        record.status_code = 500
        record.error_code = "internal_error"
        PlanningPrivacyFilter().filter(record)
        self.assertEqual(record.getMessage(), "POST /v1/planning 500 internal_error")

    def test_observability_metadata_has_an_exact_coarse_allow_list(self) -> None:
        metadata = planning_observability_metadata(
            method="POST", status_code=500, error_code="internal_error"
        )
        self.assertEqual(set(metadata), set(PLANNING_OBSERVABILITY_FIELDS))
        self.assertEqual(
            metadata,
            {
                "method": "POST",
                "route": "/v1/planning",
                "status_code": 500,
                "error_code": "internal_error",
            },
        )
        secret = "DISTINCTIVE-HELPER-SECRET"
        self.assertNotIn(
            secret,
            repr(
                planning_observability_metadata(method=secret, status_code=9999, error_code=secret)
            ),
        )
        with self.assertRaises(TypeError):
            planning_observability_metadata(  # type: ignore[call-arg]
                method="POST", status_code=500, error_code="internal_error", facts={secret: secret}
            )

    def test_unexpected_failure_is_sanitized_with_debug_on_and_off(self) -> None:
        secret = "DISTINCTIVE-UNEXPECTED-SECRET"

        class SensitiveFailure(RuntimeError):
            def __init__(self) -> None:
                super().__init__(secret)
                self.planning_input = {"facts": {"answer": secret}}
                self.trace = {"actual_value": secret}

        logger = logging.getLogger("bardi.api")
        capture = _HostileCapture()
        stream = StringIO()
        text_capture = logging.StreamHandler(stream)
        logger.addHandler(capture)
        logger.addHandler(text_capture)
        try:
            for debug in (True, False):
                with (
                    self.subTest(debug=debug),
                    override_settings(DEBUG=debug),
                    patch("api.api.execute_planning", side_effect=SensitiveFailure()),
                ):
                    response = self.client.post(
                        "/v1/planning",
                        data=json.dumps(
                            {
                                "service_id": "service",
                                "facts": {"answer": secret},
                                "locale": "en",
                                "evaluation_context": {"evaluation_date": "2026-09-01"},
                            }
                        ),
                        content_type="application/json",
                    )
                    self.assertEqual(response.status_code, 500)
                    self.assertEqual(
                        response.json(),
                        {
                            "type": "invalid",
                            "diagnostics": [{"code": "internal_error", "path": []}],
                        },
                    )
                    self.assertNotIn(secret, response.content.decode())
        finally:
            logger.removeHandler(capture)
            logger.removeHandler(text_capture)

        self.assertNotIn(secret, stream.getvalue())
        self.assertTrue(capture.records)
        for record in capture.records:
            self.assertEqual(record.getMessage(), "POST /v1/planning 500 internal_error")
            self.assertIsNone(getattr(record, "request", None))
            self.assertIsNone(record.exc_info)
            self.assertNotIn(secret, repr(record.__dict__))


class StatelessPlanningTests(TransactionTestCase):
    def setUp(self) -> None:
        self.secret = "DISTINCTIVE-PERSISTENCE-SECRET"
        self.fact = FactDefinition.objects.create(
            key="privacy.transient_string", kind=FactDefinition.Kind.STRING
        )
        FactDefinition.objects.filter(pk=self.fact.pk).update(is_published=True)
        self.fact.refresh_from_db()
        self.service = Service.objects.create(
            semantic_id="privacy.service", text_ar="خدمة", text_en="Service", is_active=True
        )
        procedure = Procedure.objects.create(
            semantic_id="privacy.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=self.service,
        )
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=procedure,
            selection_predicate={
                "op": "eq",
                "fact": self.fact.key,
                "value": "PUBLIC-NONMATCHING-VALUE",
            },
        )
        question_fact = FactDefinition.objects.get(key="has_current_enrollment_certificate")
        ServiceQuestion.objects.create(
            semantic_id="privacy.question",
            service=self.service,
            fact=question_fact,
            text_ar="سؤال",
            text_en="Question",
            priority=1,
        )
        contradiction_fact = FactDefinition.objects.get(key="is_student")
        contradiction = ServiceContradiction.objects.create(
            semantic_id="privacy.contradiction",
            service=self.service,
            condition={"op": "eq", "fact": contradiction_fact.key, "value": True},
        )
        set_contradiction_facts(contradiction, (contradiction_fact,))

    def _counts(self) -> dict[type[Any], int]:
        return {
            model: cast(Any, model).objects.count()
            for model in apps.get_models()
            if model._meta.managed and not model._meta.proxy
        }

    def test_request_paths_are_repeatable_and_execute_no_database_mutation(self) -> None:
        valid = {
            "service_id": self.service.semantic_id,
            "facts": {self.fact.key: self.secret, "is_student": False},
            "locale": "en",
            "evaluation_context": {"evaluation_date": "2026-09-01"},
        }
        requests = (
            # A submitted string is evaluated by the candidate and placed in the transient
            # EvaluationTrace.actual_value before the trace is discarded.
            (json.dumps(valid), "application/json"),
            (json.dumps({**valid, "facts": {self.fact.key: 123}}), "application/json"),
            (json.dumps({**valid, "facts": {"unsupported.fact": self.secret}}), "application/json"),
            (
                json.dumps(
                    {
                        **valid,
                        "facts": {self.fact.key: self.secret, "is_student": True},
                    }
                ),
                "application/json",
            ),
            (json.dumps({**valid, "locale": "EN"}), "application/json"),
            ('{"facts":"' + self.secret, "application/json"),
        )

        for body, content_type in requests:
            with self.subTest(body=body[:20]):
                before = self._counts()
                statements: list[tuple[str, object]] = []

                def capture_sql(  # type: ignore[no-untyped-def]
                    execute, sql, params, many, context, captured=statements
                ):
                    captured.append((sql, params))
                    return execute(sql, params, many, context)

                with connection.execute_wrapper(capture_sql):
                    first = self.client.post("/v1/planning", data=body, content_type=content_type)
                second = self.client.post("/v1/planning", data=body, content_type=content_type)

                self.assertEqual(first.status_code, second.status_code)
                self.assertEqual(first.content, second.content)
                self.assertNotIn(self.secret, first.content.decode())
                self.assertEqual(self._counts(), before)
                self.assertNotIn("sessionid", first.cookies)
                mutation_tokens = (
                    "INSERT ",
                    "UPDATE ",
                    "DELETE ",
                    "MERGE ",
                    "CREATE ",
                    "ALTER ",
                    "DROP ",
                    "TRUNCATE ",
                )
                for sql, params in statements:
                    normalized = " ".join(sql.upper().split())
                    self.assertFalse(normalized.startswith(mutation_tokens), sql)
                    self.assertNotIn(self.secret, sql)
                    self.assertNotIn(self.secret, repr(params))
