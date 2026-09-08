from __future__ import annotations

from datetime import date

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import RequestFactory, TestCase, TransactionTestCase

from knowledge.domain import load_knowledge_snapshot
from knowledge.models import (
    Authority,
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
    Source,
)
from knowledge.publication import PublicationRejected, publish_procedure_version
from knowledge.service_point_routing import (
    ProcedureServicePointAssociation,
    ServicePoint,
    ServicePointVersion,
)
from knowledge.services import set_evidence_link_sources


class RoutingFixtureMixin:
    def build(self) -> None:
        self.fact = FactDefinition.objects.create(
            key="routing_fact", kind="boolean", enum_values=[], is_published=True
        )
        self.rule = {"op": "eq", "fact": self.fact.key, "value": True}
        self.service = Service.objects.create(
            semantic_id="routing.service", text_ar="خدمة", text_en="Service"
        )
        ServiceQuestion.objects.create(
            semantic_id="routing.service.question.applicability",
            service=self.service,
            fact=self.fact,
            text_ar="هل ينطبق عليك شرط الخدمة؟",
            text_en="Does the service condition apply to you?",
            priority=100,
        )
        self.procedure = Procedure.objects.create(
            semantic_id="routing.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=self.service,
        )
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate=self.rule,
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="routing.procedure.v1",
            procedure=self.procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability=self.rule,
        )
        self.point = ServicePoint.objects.create(
            semantic_id="routing.point", name_ar="مكتب", name_en="Office"
        )
        self.material = ServicePointVersion.objects.create(
            semantic_id="routing.point.v1",
            service_point=self.point,
            address_ar="العنوان",
            address_en="Address",
            availability="available",
            effective_from=date(2026, 1, 1),
            verification_state="current",
            verified_on=date(2026, 9, 1),
        )
        self.association = ProcedureServicePointAssociation.objects.create(
            semantic_id="routing.association",
            procedure_version=self.version,
            service_point_version=self.material,
            applicability=self.rule,
            verification_state="current",
            verified_on=date(2026, 9, 1),
        )
        authority = Authority.objects.create(
            semantic_id="routing.authority", name_ar="جهة", name_en="Authority"
        )
        self.source = Source.objects.create(
            semantic_id="routing.source",
            authority=authority,
            title="Official routing",
            locator="https://example.test/routing",
            classification="official",
            retrieved_on=date(2026, 9, 1),
        )
        for field, owner in (
            ("service_point_version", self.material),
            ("procedure_service_point_association", self.association),
        ):
            link = EvidenceLink.objects.create(
                **{field: owner},
                passage="Passage",
                location="Section",
                applicability_context="Jurisdiction",
                support_status="supports",
                verification_state="current",
                verified_on=date(2026, 9, 1),
            )
            set_evidence_link_sources(link, (self.source,))


class ServicePointRoutingTests(RoutingFixtureMixin, TestCase):
    def setUp(self) -> None:
        self.build()

    def test_validation_owner_union_admin_and_detached_loading(self) -> None:
        invalid = ProcedureServicePointAssociation(
            procedure_version=self.version,
            service_point_version=self.material,
            semantic_id="invalid",
            applicability={},
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()
        with self.assertRaises(ValidationError):
            EvidenceLink(
                service_point_version=self.material,
                procedure_service_point_association=self.association,
            ).full_clean()
        self.assertIn(ServicePoint, admin.site._registry)
        self.assertIn(ServicePointVersion, admin.site._registry)
        self.assertIn(ProcedureServicePointAssociation, admin.site._registry)

        actor = get_user_model().objects.create_user(username="routing-publisher")
        publish_procedure_version(self.version.pk, actor=actor)
        snapshot = load_knowledge_snapshot()
        loaded = next(
            item
            for item in snapshot.procedure_versions
            if item.semantic_id == self.version.semantic_id
        )
        with self.assertNumQueries(0):
            self.assertEqual(
                loaded.service_point_associations[0].semantic_id,
                self.association.semantic_id,
            )
            self.assertEqual(
                loaded.service_point_associations[0].evidence_links[0].sources[0].semantic_id,
                self.source.semantic_id,
            )
            self.assertEqual(snapshot.service_point_versions[0].address.en, "Address")
            self.assertEqual(
                snapshot.service_point_versions[0].effective_from,
                date(2026, 1, 1),
            )

        self.association.refresh_from_db()
        self.material.refresh_from_db()
        self.point.refresh_from_db()
        request = RequestFactory().get("/admin/")
        request.user = get_user_model().objects.create_superuser(username="routing-admin")
        point_admin = admin.site._registry[ServicePoint]
        material_admin = admin.site._registry[ServicePointVersion]
        association_admin = admin.site._registry[ProcedureServicePointAssociation]
        self.assertFalse(point_admin.has_delete_permission(request, self.point))
        self.assertFalse(material_admin.has_delete_permission(request, self.material))
        self.assertFalse(association_admin.has_delete_permission(request, self.association))
        self.assertEqual(
            set(material_admin.get_readonly_fields(request, self.material)),
            {field.name for field in ServicePointVersion._meta.fields},
        )

    def test_draft_routing_deletion_requires_model_permission(self) -> None:
        user = get_user_model().objects.create_user(username="routing-editor", is_staff=True)
        request = RequestFactory().get("/admin/")
        request.user = user
        owners = (self.point, self.material, self.association)
        for owner in owners:
            model_admin = admin.site._registry[type(owner)]
            with self.subTest(model=owner._meta.model_name, authorized=False):
                self.assertFalse(model_admin.has_delete_permission(request, owner))
                self.assertFalse(model_admin.has_delete_permission(request, None))

        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="knowledge",
                codename__in=[f"delete_{owner._meta.model_name}" for owner in owners],
            )
        )
        # Reload rather than reuse Django's cached permission set.
        request.user = get_user_model().objects.get(pk=user.pk)
        for owner in owners:
            model_admin = admin.site._registry[type(owner)]
            with self.subTest(model=owner._meta.model_name, authorized=True):
                self.assertTrue(model_admin.has_delete_permission(request, owner))
                self.assertTrue(model_admin.has_delete_permission(request, None))

    def test_service_point_material_requires_an_effective_start(self) -> None:
        invalid = ServicePointVersion(
            semantic_id="routing.point.missing-start",
            service_point=self.point,
            address_ar="عنوان",
            address_en="Address",
            availability="available",
            verification_state="current",
            verified_on=date(2026, 9, 1),
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_service_point_material_and_evidence_are_reusable_across_draft_versions(self) -> None:
        second_version = ProcedureVersion.objects.create(
            semantic_id="routing.procedure.v2",
            procedure=self.procedure,
            text_ar="نسخة ثانية",
            text_en="Second version",
            applicability=self.rule,
        )
        ProcedureServicePointAssociation.objects.create(
            semantic_id="routing.association.reuse",
            procedure_version=second_version,
            service_point_version=self.material,
            applicability=self.rule,
        )
        link = EvidenceLink.objects.get(service_point_version=self.material)

        set_evidence_link_sources(link, (self.source,))

        self.assertEqual(self.material.associations.count(), 2)
        self.assertEqual(tuple(link.sources.all()), (self.source,))

    def test_publication_rejects_malformed_rules_and_missing_routing_evidence(self) -> None:
        EvidenceLink.objects.filter(procedure_service_point_association=self.association).delete()
        EvidenceLink.objects.filter(service_point_version=self.material).delete()
        ProcedureServicePointAssociation.objects.filter(pk=self.association.pk).update(
            applicability={"op": "unsupported"}
        )
        actor = get_user_model().objects.create_user(username="invalid-routing-publisher")

        with self.assertRaises(PublicationRejected) as caught:
            publish_procedure_version(self.version.pk, actor=actor)

        codes = {item.code for item in caught.exception.diagnostics}
        self.assertIn("unsupported_rule_operator:unsupported", codes)
        self.assertIn("association_evidence_required", codes)
        self.assertIn("material_evidence_required", codes)
        self.version.refresh_from_db()
        self.assertEqual(self.version.state, ProcedureVersion.State.DRAFT)


class ServicePointRoutingDatabaseTests(RoutingFixtureMixin, TransactionTestCase):
    def setUp(self) -> None:
        self.build()

    def test_current_material_overlap_is_rejected_but_association_overlap_is_allowed(self) -> None:
        ProcedureServicePointAssociation.objects.create(
            semantic_id="routing.association.duplicate-window",
            procedure_version=self.version,
            service_point_version=self.material,
            applicability=self.rule,
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            ServicePointVersion.objects.create(
                semantic_id="routing.point.v2",
                service_point=self.point,
                address_ar="عنوان آخر",
                address_en="Another address",
                availability="unknown",
                effective_from=date(2026, 1, 1),
                verification_state="current",
            )

    def test_database_rejects_material_without_an_effective_start(self) -> None:
        with self.assertRaises(DatabaseError), transaction.atomic():
            ServicePointVersion.objects.create(
                semantic_id="routing.point.no-start",
                service_point=self.point,
                address_ar="عنوان بدون بداية",
                address_en="Address without start",
                availability="unknown",
                verification_state="needs_reverification",
            )

    def test_database_preserves_published_routing_and_provenance(self) -> None:
        actor = get_user_model().objects.create_user(username="routing-db-publisher")
        publish_procedure_version(self.version.pk, actor=actor)

        for mutation in (
            lambda: ProcedureServicePointAssociation.objects.filter(pk=self.association.pk).update(
                semantic_id="changed"
            ),
            lambda: ServicePointVersion.objects.filter(pk=self.material.pk).update(
                address_en="Changed"
            ),
            lambda: Source.objects.filter(pk=self.source.pk).update(title="Changed"),
        ):
            with self.assertRaises(DatabaseError), transaction.atomic():
                mutation()
