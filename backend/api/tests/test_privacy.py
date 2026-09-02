from __future__ import annotations

import json
import logging
from typing import Any, cast

from django.apps import apps
from django.contrib.sessions.models import Session
from django.test import SimpleTestCase, TransactionTestCase

from api.privacy import PlanningPrivacyFilter


class PrivacyLoggingTests(SimpleTestCase):
    def test_filter_removes_body_arguments_and_exception(self) -> None:
        secret = "DISTINCTIVE-SECRET"
        record = logging.LogRecord(
            "django.request",
            logging.ERROR,
            __file__,
            1,
            "failure %s /v1/planning",
            (secret,),
            (ValueError, ValueError(secret), None),
        )
        record.args = (500, "POST /v1/planning HTTP/1.1", secret)
        record.body = secret
        PlanningPrivacyFilter().filter(record)
        rendered = record.getMessage()
        self.assertNotIn(secret, rendered)
        self.assertEqual(rendered, "POST /v1/planning 500 request_error")
        self.assertIsNone(record.exc_info)
        self.assertIsNone(cast(Any, record).body)


class StatelessPlanningTests(TransactionTestCase):
    def test_request_is_repeatable_and_persists_no_case_or_session_data(self) -> None:
        secret = "DISTINCTIVE-PERSISTENCE-SECRET"
        payload = {
            "service_id": "missing.service",
            "facts": {"unknown": secret},
            "locale": "en",
            "evaluation_context": {"evaluation_date": "2026-09-01"},
        }
        knowledge_models = tuple(apps.get_app_config("knowledge").get_models())
        before = {model: cast(Any, model).objects.count() for model in knowledge_models}
        sessions_before = Session.objects.count()

        first = self.client.post(
            "/v1/planning", data=json.dumps(payload), content_type="application/json"
        )
        second = self.client.post(
            "/v1/planning", data=json.dumps(payload), content_type="application/json"
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.content, second.content)
        self.assertNotIn(secret, first.content.decode())
        self.assertEqual(
            {model: cast(Any, model).objects.count() for model in knowledge_models},
            before,
        )
        self.assertEqual(Session.objects.count(), sessions_before)
        self.assertNotIn("sessionid", first.cookies)
