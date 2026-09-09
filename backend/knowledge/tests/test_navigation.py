from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from knowledge.models import (
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
)
from knowledge.navigation import ServiceNavigationEntry, load_active_service_navigation
from knowledge.publication import publish_procedure_version, withdraw_procedure_version


class ServiceNavigationReadTests(TestCase):
    def test_navigation_filters_only_active_services_and_ignores_version_usability(self) -> None:
        active_without_procedure = Service.objects.create(
            semantic_id="active.no-procedure",
            text_ar="بلا إجراء",
            text_en="No procedure",
            is_active=True,
        )
        active_without_version = Service.objects.create(
            semantic_id="active.no-version",
            text_ar="بلا نسخة",
            text_en="No version",
            is_active=True,
        )
        Procedure.objects.create(
            semantic_id="active.no-version.procedure",
            text_ar="إجراء بلا نسخة",
            text_en="Procedure without version",
            primary_service=active_without_version,
        )
        active_draft_only = Service.objects.create(
            semantic_id="active.draft-only",
            text_ar="مسودة فقط",
            text_en="Draft only",
            is_active=True,
        )
        draft_procedure = Procedure.objects.create(
            semantic_id="active.draft-only.procedure",
            text_ar="إجراء مسودة",
            text_en="Draft procedure",
            primary_service=active_draft_only,
        )
        ProcedureVersion.objects.create(
            semantic_id="active.draft-only.version",
            procedure=draft_procedure,
            text_ar="نسخة مسودة",
            text_en="Draft version",
        )
        active_withdrawn_only = Service.objects.create(
            semantic_id="active.withdrawn-only",
            text_ar="مسحوب فقط",
            text_en="Withdrawn only",
            is_active=True,
        )
        withdrawn_procedure = Procedure.objects.create(
            semantic_id="active.withdrawn-only.procedure",
            text_ar="إجراء مسحوب",
            text_en="Withdrawn procedure",
            primary_service=active_withdrawn_only,
        )
        ServiceProcedureCandidate.objects.create(
            service=active_withdrawn_only,
            procedure=withdrawn_procedure,
            selection_predicate={"op": "eq", "fact": "is_student", "value": True},
        )
        ServiceQuestion.objects.create(
            semantic_id="active.withdrawn-only.question",
            service=active_withdrawn_only,
            fact=FactDefinition.objects.get(key="is_student"),
            text_ar="هل أنت طالب؟",
            text_en="Are you a student?",
            priority=1,
        )
        withdrawn_version = ProcedureVersion.objects.create(
            semantic_id="active.withdrawn-only.version",
            procedure=withdrawn_procedure,
            text_ar="نسخة مسحوبة",
            text_en="Withdrawn version",
            applicability={"op": "eq", "fact": "is_student", "value": True},
        )
        actor = get_user_model().objects.create_user(username="navigation-publisher")
        publish_procedure_version(withdrawn_version.pk, actor=actor)
        withdraw_procedure_version(withdrawn_version.pk, actor=actor)
        Service.objects.create(
            semantic_id="inactive.service",
            text_ar="غير نشطة",
            text_en="Inactive",
            is_active=False,
        )

        entries = load_active_service_navigation()

        self.assertEqual(
            tuple(entry.semantic_id for entry in entries),
            tuple(
                sorted(
                    (
                        active_without_procedure.semantic_id,
                        active_without_version.semantic_id,
                        active_draft_only.semantic_id,
                        active_withdrawn_only.semantic_id,
                    )
                )
            ),
        )
        self.assertEqual(
            {entry.semantic_id: (entry.text_ar, entry.text_en) for entry in entries},
            {
                active_without_procedure.semantic_id: ("بلا إجراء", "No procedure"),
                active_without_version.semantic_id: ("بلا نسخة", "No version"),
                active_draft_only.semantic_id: ("مسودة فقط", "Draft only"),
                active_withdrawn_only.semantic_id: ("مسحوب فقط", "Withdrawn only"),
            },
        )

    def test_python_ordering_handles_case_punctuation_numeric_and_unicode_ids(self) -> None:
        semantic_ids = ("item-10", "item-2", "Item!", "item.1", "خدمة", "item_0")
        for position, semantic_id in enumerate(semantic_ids):
            Service.objects.create(
                semantic_id=semantic_id,
                text_ar=f"عنوان {position}",
                text_en=f"Title {position}",
                is_active=True,
            )

        entries = load_active_service_navigation()

        self.assertEqual(
            tuple(entry.semantic_id for entry in entries),
            tuple(sorted(semantic_ids)),
        )

    def test_query_is_one_select_with_only_navigation_columns(self) -> None:
        Service.objects.create(
            semantic_id="query.active",
            text_ar="نشطة",
            text_en="Active",
            is_active=True,
        )
        Service.objects.create(
            semantic_id="query.inactive",
            text_ar="غير نشطة",
            text_en="Inactive",
            is_active=False,
        )

        with CaptureQueriesContext(connection) as queries:
            entries = load_active_service_navigation()

        self.assertEqual(len(queries), 1)
        sql = queries[0]["sql"].lower()
        self.assertIn(
            'select "knowledge_service"."semantic_id" as "semantic_id", '
            '"knowledge_service"."text_ar" as "text_ar", '
            '"knowledge_service"."text_en" as "text_en"',
            sql,
        )
        self.assertIn('where "knowledge_service"."is_active"', sql)
        self.assertNotIn(" join ", sql)
        for unrelated_table in (
            "knowledge_procedure",
            "knowledge_procedureversion",
            "knowledge_serviceprocedurecandidate",
            "knowledge_servicequestion",
            "knowledge_servicecontradiction",
            "knowledge_evidencelink",
            "knowledge_source",
            "knowledge_evidencediscrepancy",
        ):
            self.assertNotIn(unrelated_table, sql)
        self.assertEqual(entries, (ServiceNavigationEntry("query.active", "نشطة", "Active"),))

    def test_entries_are_eager_detached_and_serializable_without_queries(self) -> None:
        service = Service.objects.create(
            semantic_id="detached.service",
            text_ar="خدمة",
            text_en="Service",
            is_active=True,
        )

        with self.assertNumQueries(1):
            entries = load_active_service_navigation()

        with self.assertNumQueries(0):
            serialized = json.dumps(
                [asdict(entry) for entry in entries], ensure_ascii=False, sort_keys=True
            )
            self.assertEqual(
                serialized,
                '[{"semantic_id": "detached.service", "text_ar": "خدمة", "text_en": "Service"}]',
            )

        Service.objects.filter(pk=service.pk).update(text_en="Changed")
        self.assertEqual(entries[0].text_en, "Service")

    def test_malformed_unrelated_catalog_rule_does_not_affect_navigation(self) -> None:
        service = Service.objects.create(
            semantic_id="malformed-catalog.service",
            text_ar="خدمة",
            text_en="Service",
            is_active=True,
        )
        procedure = Procedure.objects.create(
            semantic_id="malformed-catalog.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=service,
        )
        candidate = ServiceProcedureCandidate.objects.create(
            service=service,
            procedure=procedure,
            selection_predicate={"op": "eq", "fact": "is_student", "value": True},
        )
        ServiceProcedureCandidate.objects.filter(pk=candidate.pk).update(
            selection_predicate={"op": "broken"}
        )

        self.assertEqual(
            load_active_service_navigation(),
            (ServiceNavigationEntry("malformed-catalog.service", "خدمة", "Service"),),
        )

    def test_database_errors_propagate_from_navigation_loader(self) -> None:
        failure = DatabaseError("navigation database failure")
        with patch.object(Service.objects, "filter", side_effect=failure):
            with self.assertRaisesRegex(DatabaseError, "navigation database failure"):
                load_active_service_navigation()
