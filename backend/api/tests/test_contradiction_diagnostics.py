from __future__ import annotations

import json

from django.test import TransactionTestCase
from knowledge.models import (
    FactDefinition,
    Procedure,
    Service,
    ServiceContradiction,
    ServiceProcedureCandidate,
)
from knowledge.services import set_contradiction_facts


class ContradictionDiagnosticContractTests(TransactionTestCase):
    def setUp(self) -> None:
        self.influential, _ = FactDefinition.objects.get_or_create(
            key="is_student",
            defaults={"kind": "boolean", "enum_values": [], "is_published": True},
        )
        self.omitted, _ = FactDefinition.objects.get_or_create(
            key="has_current_enrollment_certificate",
            defaults={"kind": "boolean", "enum_values": [], "is_published": True},
        )

    def test_omitted_dominated_fact_is_not_reported_for_true_contradiction(self) -> None:
        influential = self.influential
        omitted = self.omitted
        service = Service.objects.create(
            semantic_id="contract.contradiction-dominance",
            text_ar="خدمة",
            text_en="Service",
            is_active=True,
        )
        procedure = Procedure.objects.create(
            semantic_id="contract.contradiction-dominance.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=service,
        )
        ServiceProcedureCandidate.objects.create(
            service=service,
            procedure=procedure,
            selection_predicate={"op": "eq", "fact": influential.key, "value": True},
        )
        contradiction = ServiceContradiction.objects.create(
            semantic_id="contract.secret.dominated-unknown",
            service=service,
            condition={
                "op": "any",
                "children": [
                    {"op": "eq", "fact": influential.key, "value": True},
                    {"op": "eq", "fact": omitted.key, "value": False},
                ],
            },
        )
        set_contradiction_facts(contradiction, (influential, omitted))

        response = self.client.post(
            "/v1/planning",
            data=json.dumps(
                {
                    "service_id": service.semantic_id,
                    "facts": {influential.key: True},
                    "locale": "en",
                    "evaluation_context": {"evaluation_date": "2026-09-01"},
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "type": "invalid",
                "diagnostics": [
                    {"code": "contradictory_facts", "path": ["facts", influential.key]}
                ],
            },
        )
        rendered = response.content.decode()
        self.assertNotIn(omitted.key, rendered)
        self.assertNotIn(contradiction.semantic_id, rendered)
