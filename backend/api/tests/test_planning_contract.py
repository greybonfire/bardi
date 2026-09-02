from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TransactionTestCase
from knowledge.models import (
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
)
from knowledge.publication import publish_procedure_version


class PlanningHttpContractTests(SimpleTestCase):
    valid = {
        "service_id": "service",
        "facts": {"is_student": True},
        "locale": "en",
        "evaluation_context": {"evaluation_date": "2026-09-01"},
    }

    @patch("api.api.execute_planning")
    def test_semantic_result_is_http_200_and_exactly_projected(self, execute) -> None:  # type: ignore[no-untyped-def]
        execute.return_value = {
            "type": "inconclusive",
            "reason": "unknown_service",
            "message": "The service is unavailable.",
        }
        response = self.client.post(
            "/v1/planning", data=json.dumps(self.valid), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), execute.return_value)

    def test_structural_validation_is_sanitized_and_does_not_echo_input(self) -> None:
        secret = "DISTINCTIVE-SECRET"
        malformed = {
            **self.valid,
            "locale": "EN",
            "facts": {"is_student": secret, "nested": {"secret": secret}},
            "extra": secret,
        }
        response = self.client.post(
            "/v1/planning", data=json.dumps(malformed), content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)
        body = response.content.decode()
        self.assertNotIn(secret, body)
        self.assertEqual(response.json()["type"], "invalid")
        self.assertTrue(
            all(
                set(item) == {"path", "code"} and item["code"] == "invalid_request"
                for item in response.json()["diagnostics"]
            )
        )

    def test_malformed_json_uses_the_invalid_discriminator_without_echoing_input(self) -> None:
        secret = "DISTINCTIVE-MALFORMED-SECRET"
        response = self.client.post(
            "/v1/planning",
            data='{"facts":"' + secret,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "type": "invalid",
                "diagnostics": [{"code": "invalid_body", "path": ["body"]}],
            },
        )
        self.assertNotIn(secret, response.content.decode())

    def test_date_requires_canonical_calendar_form(self) -> None:
        for value in ("2026-9-1", "2026-09-01T00:00:00Z", "2026-02-30"):
            with self.subTest(value=value):
                payload = {**self.valid, "evaluation_context": {"evaluation_date": value}}
                response = self.client.post(
                    "/v1/planning", data=json.dumps(payload), content_type="application/json"
                )
                self.assertEqual(response.status_code, 422)
                self.assertNotIn(value, response.content.decode())

    def test_fact_transport_rejects_float_array_and_object_without_coercion(self) -> None:
        values: tuple[object, ...] = (1.5, [], {})
        for value in values:
            with self.subTest(value=value):
                payload = {**self.valid, "facts": {"fact": value}}
                response = self.client.post(
                    "/v1/planning", data=json.dumps(payload), content_type="application/json"
                )
                self.assertEqual(response.status_code, 422)

    def test_openapi_reserves_all_result_discriminators(self) -> None:
        response = self.client.get("/v1/openapi.json")
        self.assertEqual(response.status_code, 200)
        rendered = response.content.decode()
        for discriminator in ("next_question", "plan", "inconclusive", "invalid"):
            self.assertIn(discriminator, rendered)


class ReachableResultFamilyTests(TransactionTestCase):
    def setUp(self) -> None:
        self.fact, _ = FactDefinition.objects.get_or_create(
            key="is_student",
            defaults={"kind": "boolean", "enum_values": [], "is_published": True},
        )
        self.service = Service.objects.create(
            semantic_id="contract.service",
            text_ar="خدمة",
            text_en="Service",
            is_active=True,
        )
        self.procedure = Procedure.objects.create(
            semantic_id="contract.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=self.service,
        )
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate={"op": "eq", "fact": self.fact.key, "value": True},
        )
        ServiceQuestion.objects.create(
            semantic_id="contract.question",
            service=self.service,
            fact=self.fact,
            text_ar="هل أنت طالب؟",
            text_en="Are you a student?",
            priority=1,
        )

    def post(self, *, service_id: str = "contract.service", facts: object = None):  # type: ignore[no-untyped-def]
        payload = {
            "service_id": service_id,
            "facts": {} if facts is None else facts,
            "locale": "en",
            "evaluation_context": {"evaluation_date": "2026-09-01"},
        }
        return self.client.post(
            "/v1/planning", data=json.dumps(payload), content_type="application/json"
        )

    def test_next_question_invalid_and_inconclusive_shapes(self) -> None:
        question = self.post()
        self.assertEqual(question.status_code, 200)
        self.assertEqual(
            question.json(),
            {
                "type": "next_question",
                "service_id": "contract.service",
                "question": {
                    "id": "contract.question",
                    "text": "Are you a student?",
                    "answers": [
                        {
                            "key": "is_student",
                            "kind": "boolean",
                            "enum_options": [],
                            "minimum": None,
                        }
                    ],
                },
            },
        )
        invalid = self.post(facts={"is_student": None})
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(
            invalid.json(),
            {
                "type": "invalid",
                "diagnostics": [{"code": "invalid_fact_value", "path": ["facts", "is_student"]}],
            },
        )
        no_match = self.post(facts={"is_student": False})
        self.assertEqual(no_match.status_code, 200)
        self.assertEqual(no_match.json()["type"], "inconclusive")
        self.assertEqual(no_match.json()["reason"], "no_matching_researched_procedure")
        self.assertEqual(self.post(service_id="missing").json()["reason"], "unknown_service")

    def test_unresolved_and_resolved_version_staged_boundaries(self) -> None:
        unresolved = self.post(facts={"is_student": True})
        self.assertEqual(unresolved.json()["reason"], "no_published_version")

        actor = get_user_model().objects.create_user(username="contract-publisher")
        version = ProcedureVersion.objects.create(
            semantic_id="contract.version",
            procedure=self.procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability={"op": "eq", "fact": self.fact.key, "value": True},
        )
        publish_procedure_version(version.pk, actor=actor)
        resolved = self.post(facts={"is_student": True})
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.json()["type"], "inconclusive")
        self.assertEqual(resolved.json()["reason"], "plan_assembly_unavailable")

    def test_inactive_and_case_preparation_boundaries_do_not_evaluate(self) -> None:
        inactive = Service.objects.create(
            semantic_id="contract.inactive", text_ar="غير نشطة", text_en="Inactive"
        )
        self.assertEqual(
            self.post(service_id=inactive.semantic_id).json()["reason"], "inactive_service"
        )

        FactDefinition.objects.get_or_create(
            key="age_years_on_evaluation_date",
            defaults={"kind": "integer", "enum_values": [], "minimum": 0, "derived": True},
        )
        derived_service = Service.objects.create(
            semantic_id="contract.derived",
            text_ar="مشتقة",
            text_en="Derived",
            is_active=True,
        )
        derived_procedure = Procedure.objects.create(
            semantic_id="contract.derived.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=derived_service,
        )
        ServiceProcedureCandidate.objects.create(
            service=derived_service,
            procedure=derived_procedure,
            selection_predicate={
                "op": "gte",
                "fact": "age_years_on_evaluation_date",
                "value": 18,
            },
        )
        self.assertEqual(
            self.post(service_id=derived_service.semantic_id).json()["reason"],
            "case_preparation_unavailable",
        )

    def test_malformed_stored_knowledge_is_redacted(self) -> None:
        ServiceProcedureCandidate.objects.filter(service=self.service).update(
            selection_predicate={"op": "secret-broken-rule"}
        )
        response = self.post(facts={"is_student": "DISTINCTIVE-SECRET"})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {
                "type": "invalid",
                "diagnostics": [{"code": "knowledge_snapshot_invalid", "path": []}],
            },
        )
        self.assertNotIn("DISTINCTIVE-SECRET", response.content.decode())
        self.assertNotIn("secret-broken-rule", response.content.decode())
