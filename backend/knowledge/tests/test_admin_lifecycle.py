from __future__ import annotations

from datetime import date

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, User
from django.contrib.messages import get_messages
from django.test import RequestFactory, SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from planning.versions import (
    ProcedureVersionResolved,
    ProcedureVersionUnavailable,
    resolve_procedure_version,
)

from knowledge import (
    admin_lifecycle_admin,
    eligibility_basis_admin,
    fee_admin,
    procedure_dependency_admin,
    service_point_routing_admin,
)
from knowledge.admin import (
    ChecklistItemOwnerInline,
    EligibilityBasisAdmin,
    EvidenceLinkAdmin,
    EvidenceSourceInline,
    ProcedureVersionAdmin,
    StepOwnerInline,
    WarningOwnerInline,
)
from knowledge.admin_lifecycle import clone_published_procedure_version
from knowledge.admin_lifecycle_admin import (
    EvidenceLinkLifecycleAdmin,
    ProcedureVersionLifecycleAdmin,
)
from knowledge.domain import load_knowledge_snapshot
from knowledge.eligibility_basis_admin import EligibilityBasisOwnerInline
from knowledge.evidence_workflow import EvidenceReverificationEvent
from knowledge.fee_admin import FeeAdmin, FeeOwnerInline
from knowledge.fees import Fee
from knowledge.models import (
    Authority,
    ChecklistItem,
    EligibilityBasis,
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
    Source,
    Step,
    Warning,
)
from knowledge.planning_scenarios import PlanningScenario
from knowledge.procedure_dependencies import ProcedureDependency
from knowledge.procedure_dependency_admin import (
    ProcedureDependencyAdmin,
    ProcedureDependencyOwnerInline,
)
from knowledge.publication import publish_procedure_version, withdraw_procedure_version
from knowledge.review_workflow import (
    ProcedureVersionReviewApproval,
    ProcedureVersionReviewPolicy,
)
from knowledge.service_point_routing import (
    ProcedureServicePointAssociation,
    ServicePoint,
    ServicePointVersion,
)
from knowledge.service_point_routing_admin import (
    ProcedureServicePointAssociationAdmin,
    ProcedureServicePointAssociationInline,
    ServicePointAdmin,
    ServicePointVersionAdmin,
)
from knowledge.services import set_evidence_link_sources


class AdminCompositionTests(SimpleTestCase):
    def test_migrated_admin_registry_uses_one_explicit_class_per_model(self) -> None:
        expected = {
            ProcedureVersion: ProcedureVersionAdmin,
            EvidenceLink: EvidenceLinkAdmin,
            EligibilityBasis: EligibilityBasisAdmin,
            Fee: FeeAdmin,
            ProcedureDependency: ProcedureDependencyAdmin,
            ServicePoint: ServicePointAdmin,
            ServicePointVersion: ServicePointVersionAdmin,
            ProcedureServicePointAssociation: ProcedureServicePointAssociationAdmin,
        }

        for model, admin_class in expected.items():
            with self.subTest(model=model._meta.label):
                self.assertIs(type(admin.site._registry[model]), admin_class)

        self.assertEqual(
            reverse("admin:knowledge_procedureversion_changelist"),
            "/admin/knowledge/procedureversion/",
        )
        self.assertEqual(
            reverse("admin:knowledge_evidencelink_changelist"),
            "/admin/knowledge/evidencelink/",
        )
        self.assertEqual(
            reverse("admin:knowledge_eligibilitybasis_changelist"),
            "/admin/knowledge/eligibilitybasis/",
        )
        self.assertEqual(reverse("admin:knowledge_fee_changelist"), "/admin/knowledge/fee/")
        self.assertEqual(
            reverse("admin:knowledge_proceduredependency_changelist"),
            "/admin/knowledge/proceduredependency/",
        )
        self.assertEqual(
            reverse("admin:knowledge_servicepoint_changelist"),
            "/admin/knowledge/servicepoint/",
        )
        self.assertEqual(
            reverse("admin:knowledge_servicepointversion_changelist"),
            "/admin/knowledge/servicepointversion/",
        )
        self.assertEqual(
            reverse("admin:knowledge_procedureservicepointassociation_changelist"),
            "/admin/knowledge/procedureservicepointassociation/",
        )

    def test_procedure_version_and_evidence_admin_configuration_is_explicit(self) -> None:
        self.assertEqual(
            ProcedureVersionAdmin.actions,
            (
                "publish_selected",
                "withdraw_selected",
                "clone_selected_to_draft",
                "approve_selected_versions",
            ),
        )
        self.assertEqual(
            ProcedureVersionAdmin.inlines,
            (
                ChecklistItemOwnerInline,
                StepOwnerInline,
                WarningOwnerInline,
                EligibilityBasisOwnerInline,
                FeeOwnerInline,
                ProcedureDependencyOwnerInline,
                ProcedureServicePointAssociationInline,
            ),
        )
        self.assertEqual(
            ProcedureVersionAdmin.list_display,
            (
                "semantic_id",
                "procedure",
                "state",
                "effective_from",
                "effective_to",
                "published_at",
            ),
        )
        self.assertEqual(
            ProcedureVersionAdmin.list_filter,
            ("state", "procedure", "effective_from", "effective_to"),
        )
        self.assertEqual(EvidenceLinkAdmin.actions, ("reverify_selected_evidence",))
        self.assertEqual(EvidenceLinkAdmin.inlines, (EvidenceSourceInline,))
        self.assertEqual(
            EvidenceLinkAdmin.list_display,
            ("semantic_id", "owner_display", "support_status", "verification_state"),
        )

    def test_migrated_admin_behavior_is_declared_without_installers(self) -> None:
        self.assertIs(ProcedureVersionAdmin.__mro__[1], ProcedureVersionLifecycleAdmin)
        self.assertIs(EvidenceLinkAdmin.__mro__[1], EvidenceLinkLifecycleAdmin)
        for method in (
            "clone_selected_to_draft",
            "has_clone_procedureversion_permission",
            "approve_selected_versions",
            "has_review_version_permission",
            "changelist_view",
        ):
            self.assertIn(method, ProcedureVersionLifecycleAdmin.__dict__)
        for method in (
            "reverify_selected_evidence",
            "has_reverify_evidence_permission",
            "changelist_view",
        ):
            self.assertIn(method, EvidenceLinkLifecycleAdmin.__dict__)

        self.assertNotIn("_procedure_version_admin", vars(admin_lifecycle_admin))
        self.assertNotIn("_evidence_link_admin", vars(admin_lifecycle_admin))
        for module in (
            eligibility_basis_admin,
            fee_admin,
            procedure_dependency_admin,
            service_point_routing_admin,
        ):
            self.assertFalse(
                any(name.startswith("install_procedure_version_") for name in vars(module))
            )


@override_settings(PROCEDURE_VERSION_PUBLICATION_GATES=())
class SafeAdminLifecycleTests(TransactionTestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.author = user_model.objects.create_user(username="lifecycle-author", is_staff=True)
        self.researcher = user_model.objects.create_user(
            username="lifecycle-researcher", is_staff=True
        )
        self.reviewer = user_model.objects.create_user(username="lifecycle-reviewer", is_staff=True)
        self.specialist = user_model.objects.create_user(
            username="lifecycle-specialist", is_staff=True
        )
        self.publisher = user_model.objects.create_user(
            username="lifecycle-publisher", is_staff=True
        )
        self.withdrawer = user_model.objects.create_user(
            username="lifecycle-withdrawer", is_staff=True
        )
        self.reverifier = user_model.objects.create_user(
            username="lifecycle-reverifier", is_staff=True
        )
        self.viewer = user_model.objects.create_user(username="lifecycle-viewer", is_staff=True)

        self.fact = FactDefinition.objects.create(
            key="admin_lifecycle_flag",
            kind=FactDefinition.Kind.BOOLEAN,
            enum_values=[],
            is_published=True,
        )
        self.service = Service.objects.create(
            semantic_id="admin.lifecycle.service",
            text_ar="خدمة",
            text_en="Service",
        )
        ServiceQuestion.objects.create(
            semantic_id="admin.lifecycle.service.question.applicability",
            service=self.service,
            fact=self.fact,
            text_ar="هل ينطبق عليك شرط الخدمة؟",
            text_en="Does the service condition apply to you?",
            priority=100,
        )
        self.procedure = Procedure.objects.create(
            semantic_id="admin.lifecycle.procedure",
            text_ar="إجراء",
            text_en="Procedure",
            primary_service=self.service,
        )
        rule = {"op": "eq", "fact": self.fact.key, "value": True}
        ServiceProcedureCandidate.objects.create(
            service=self.service,
            procedure=self.procedure,
            selection_predicate=rule,
        )
        target_service = Service.objects.create(
            semantic_id="admin.lifecycle.target.service",
            text_ar="خدمة مستهدفة",
            text_en="Target service",
        )
        self.target_procedure = Procedure.objects.create(
            semantic_id="admin.lifecycle.target.procedure",
            text_ar="إجراء مستهدف",
            text_en="Target procedure",
            primary_service=target_service,
        )
        self.version = ProcedureVersion.objects.create(
            semantic_id="admin.lifecycle.v1",
            procedure=self.procedure,
            text_ar="نسخة",
            text_en="Version",
            applicability=rule,
            effective_from=date(2026, 1, 1),
        )
        self.authority = Authority.objects.create(
            semantic_id="admin.lifecycle.authority",
            name_ar="جهة",
            name_en="Authority",
        )
        self.source = Source.objects.create(
            semantic_id="admin.lifecycle.source",
            authority=self.authority,
            title="Official source",
            locator="https://example.test/admin-lifecycle",
            classification=Source.Classification.OFFICIAL,
            retrieved_on=date(2026, 9, 1),
        )
        self.basis = EligibilityBasis.objects.create(
            procedure_version=self.version,
            semantic_id="admin.lifecycle.basis",
            text_ar="أساس",
            text_en="Basis",
            qualification=rule,
            verification_state="current",
        )
        self.checklist = ChecklistItem.objects.create(
            procedure_version=self.version,
            semantic_id="admin.lifecycle.checklist",
            text_ar="مستند",
            text_en="Document",
            classification=ChecklistItem.Classification.PRACTICAL_PREPARATION,
            verification_state="current",
        )
        self.step = Step.objects.create(
            procedure_version=self.version,
            semantic_id="admin.lifecycle.step",
            text_ar="خطوة",
            text_en="Step",
            phase="submit",
            phase_order=1,
            slot=1,
            scope=Step.Scope.ELIGIBILITY_BASIS,
            eligibility_basis=self.basis,
            verification_state="current",
        )
        self.warning = Warning.objects.create(
            procedure_version=self.version,
            semantic_id="admin.lifecycle.regenerate",
            text_ar="أعد إنشاء الخطة",
            text_en="Regenerate the plan",
            severity=Warning.Severity.IMPORTANT,
            kind=Warning.Kind.PRODUCT,
            role=Warning.Role.REGENERATION,
            verification_state="current",
        )
        self.fee = Fee.objects.create(
            procedure_version=self.version,
            semantic_id="admin.lifecycle.fee",
            text_ar="رسوم",
            text_en="Fee",
            value_state=Fee.ValueState.UNKNOWN,
            currency="EGP",
            scope=Fee.Scope.ELIGIBILITY_BASIS,
            eligibility_basis=self.basis,
            verification_state="unknown",
        )
        self.dependency = ProcedureDependency.objects.create(
            procedure_version=self.version,
            semantic_id="admin.lifecycle.dependency",
            text_ar="متطلب سابق",
            text_en="Prerequisite",
            target_procedure=self.target_procedure,
            satisfied_when=rule,
            verification_state="current",
        )
        self.point = ServicePoint.objects.create(
            semantic_id="admin.lifecycle.point",
            name_ar="مكتب",
            name_en="Office",
        )
        self.point_version = ServicePointVersion.objects.create(
            semantic_id="admin.lifecycle.point.v1",
            service_point=self.point,
            address_ar="العنوان",
            address_en="Address",
            availability=ServicePointVersion.Availability.AVAILABLE,
            effective_from=date(2026, 1, 1),
            verification_state="current",
        )
        self.association = ProcedureServicePointAssociation.objects.create(
            procedure_version=self.version,
            semantic_id="admin.lifecycle.routing",
            service_point_version=self.point_version,
            applicability=rule,
            verification_state="current",
        )
        self.evidence: dict[str, EvidenceLink] = {}
        for name, owner_kwargs in (
            ("basis", {"eligibility_basis": self.basis}),
            ("checklist", {"checklist_item": self.checklist}),
            ("step", {"step": self.step}),
            ("dependency", {"procedure_dependency": self.dependency}),
            (
                "association",
                {"procedure_service_point_association": self.association},
            ),
            ("point", {"service_point_version": self.point_version}),
        ):
            link = EvidenceLink.objects.create(
                **owner_kwargs,
                passage=f"{name} passage",
                location=f"{name} section",
                applicability_context="Applies to this procedure",
                verification_state="current",
                support_status=EvidenceLink.SupportStatus.SUPPORTS,
            )
            set_evidence_link_sources(link, (self.source,))
            self.evidence[name] = link

        PlanningScenario.objects.create(
            procedure_version=self.version,
            name="positive",
            kind=PlanningScenario.Kind.POSITIVE,
            evaluation_context={"evaluation_date": "2026-09-06", "locale": "en"},
            source_facts={},
            expected_result_family=PlanningScenario.ResultFamily.PLAN,
            expected_identifiers={"procedure_version_id": self.version.semantic_id},
            expected_diagnostics=[],
        )
        ProcedureVersionReviewPolicy.objects.create(
            procedure_version=self.version,
            author=self.author,
            military_risk=True,
        )
        self.version = publish_procedure_version(self.version.pk, actor=self.author)

    def _permission(self, codename: str) -> Permission:
        return Permission.objects.get(
            content_type__app_label="knowledge",
            codename=codename,
        )

    def _grant(self, user: User, *codenames: str) -> None:
        user.user_permissions.add(*(self._permission(codename) for codename in codenames))
        for cache_name in ("_perm_cache", "_user_perm_cache"):
            if hasattr(user, cache_name):
                delattr(user, cache_name)

    def _request_for(self, user: User):  # type: ignore[no-untyped-def]
        request = RequestFactory().get("/admin/")
        request.user = user
        return request

    def test_clone_copies_complete_editable_successor_without_workflow_history(self) -> None:
        successor = clone_published_procedure_version(self.version.pk, actor=self.researcher)

        self.assertEqual(successor.state, ProcedureVersion.State.DRAFT)
        self.assertEqual(successor.semantic_id, "admin.lifecycle.v1.successor")
        self.version.refresh_from_db()
        self.assertEqual(self.version.state, ProcedureVersion.State.PUBLISHED)

        new_basis = successor.eligibility_bases.get(semantic_id=self.basis.semantic_id)
        new_step = successor.steps.get(semantic_id=self.step.semantic_id)
        new_fee = successor.fees.get(semantic_id=self.fee.semantic_id)
        new_association = successor.service_point_associations.get(
            semantic_id=self.association.semantic_id
        )
        self.assertNotEqual(new_basis.pk, self.basis.pk)
        self.assertEqual(new_step.eligibility_basis_id, new_basis.pk)
        self.assertEqual(new_fee.eligibility_basis_id, new_basis.pk)
        self.assertEqual(new_association.service_point_version_id, self.point_version.pk)

        scenario = successor.planning_scenarios.get(name="positive")
        self.assertEqual(
            scenario.expected_identifiers["procedure_version_id"],
            successor.semantic_id,
        )
        policy = successor.review_policy
        self.assertEqual(policy.author, self.researcher)
        self.assertTrue(policy.military_risk)
        self.assertFalse(successor.review_approvals.exists())
        self.assertFalse(successor.audit_events.exists())

        new_checklist = successor.checklist_items.get(semantic_id=self.checklist.semantic_id)
        cloned_link = new_checklist.evidence_links.get()
        self.assertNotEqual(cloned_link.pk, self.evidence["checklist"].pk)
        self.assertEqual(tuple(cloned_link.sources.all()), (self.source,))
        self.assertEqual(self.point_version.evidence_links.count(), 1)

        new_checklist.text_en = "Editable successor document"
        new_checklist.save()
        self.checklist.refresh_from_db()
        self.assertEqual(self.checklist.text_en, "Document")

    def test_withdrawn_version_is_auditable_but_not_selected_for_new_plans(self) -> None:
        withdrawn = withdraw_procedure_version(self.version.pk, actor=self.author)
        snapshot = load_knowledge_snapshot()

        current = resolve_procedure_version(
            snapshot,
            self.procedure.semantic_id,
            date(2026, 9, 6),
        )
        self.assertIsInstance(current, ProcedureVersionUnavailable)
        assert isinstance(current, ProcedureVersionUnavailable)
        self.assertEqual(current.reason_code, "no_published_version")

        historical = resolve_procedure_version(
            snapshot,
            self.procedure.semantic_id,
            date(2026, 9, 6),
            historical_version_id=withdrawn.semantic_id,
        )
        self.assertIsInstance(historical, ProcedureVersionResolved)
        assert isinstance(historical, ProcedureVersionResolved)
        self.assertTrue(historical.historical)
        self.assertTrue(withdrawn.audit_events.filter(event_type="withdrawn").exists())

    def test_admin_action_permissions_are_separated_by_capability(self) -> None:
        version_admin = ProcedureVersionAdmin(ProcedureVersion, admin.site)
        evidence_admin = EvidenceLinkAdmin(EvidenceLink, admin.site)

        self._grant(
            self.researcher,
            "view_procedureversion",
            "add_procedureversion",
            "change_procedureversion",
        )
        research_actions = version_admin.get_actions(self._request_for(self.researcher))
        self.assertIn("clone_selected_to_draft", research_actions)
        self.assertNotIn("publish_selected", research_actions)
        self.assertNotIn("withdraw_selected", research_actions)
        self.assertNotIn("approve_selected_versions", research_actions)

        self._grant(self.reviewer, "view_procedureversion", "review_procedureversion")
        review_actions = version_admin.get_actions(self._request_for(self.reviewer))
        self.assertIn("approve_selected_versions", review_actions)
        self.assertNotIn("publish_selected", review_actions)
        self.assertNotIn("clone_selected_to_draft", review_actions)

        self._grant(
            self.specialist,
            "view_procedureversion",
            "specialist_approve_military",
        )
        specialist_actions = version_admin.get_actions(self._request_for(self.specialist))
        self.assertIn("approve_selected_versions", specialist_actions)
        self.assertNotIn("publish_selected", specialist_actions)

        self._grant(self.publisher, "view_procedureversion", "publish_procedureversion")
        publisher_actions = version_admin.get_actions(self._request_for(self.publisher))
        self.assertIn("publish_selected", publisher_actions)
        self.assertNotIn("approve_selected_versions", publisher_actions)

        self._grant(self.withdrawer, "view_procedureversion", "withdraw_procedureversion")
        withdraw_actions = version_admin.get_actions(self._request_for(self.withdrawer))
        self.assertIn("withdraw_selected", withdraw_actions)
        self.assertNotIn("publish_selected", withdraw_actions)

        self._grant(
            self.reverifier,
            "view_evidencelink",
            "add_evidencereverificationevent",
        )
        reverify_actions = evidence_admin.get_actions(self._request_for(self.reverifier))
        self.assertIn("reverify_selected_evidence", reverify_actions)
        self._grant(self.viewer, "view_evidencelink", "view_procedureversion")
        self.assertNotIn(
            "reverify_selected_evidence",
            evidence_admin.get_actions(self._request_for(self.viewer)),
        )

    def test_authorized_review_post_uses_service(self) -> None:
        draft = clone_published_procedure_version(self.version.pk, actor=self.researcher)
        self._grant(self.reviewer, "view_procedureversion", "review_procedureversion")
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse("admin:knowledge_procedureversion_changelist"),
            {
                "action": "approve_selected_versions",
                "_selected_action": str(draft.pk),
                "apply": "1",
                "approval": "dimension:rule_logic",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ProcedureVersionReviewApproval.objects.filter(
                procedure_version=draft,
                dimension=ProcedureVersionReviewApproval.Dimension.RULE_LOGIC,
                reviewer=self.reviewer,
            ).exists()
        )

    def test_unauthorized_review_post_is_rejected(self) -> None:
        draft = clone_published_procedure_version(self.version.pk, actor=self.researcher)
        self._grant(self.viewer, "view_procedureversion")
        self.client.force_login(self.viewer)

        response = self.client.post(
            reverse("admin:knowledge_procedureversion_changelist"),
            {
                "action": "approve_selected_versions",
                "_selected_action": str(draft.pk),
                "apply": "1",
                "approval": "dimension:rule_logic",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ProcedureVersionReviewApproval.objects.filter(
                procedure_version=draft,
                reviewer=self.viewer,
            ).exists()
        )
        self.assertIn(
            "You do not have permission to perform that lifecycle action.",
            [str(message) for message in get_messages(response.wsgi_request)],
        )

    def test_authorized_reverification_post_uses_service(self) -> None:
        self._grant(
            self.reverifier,
            "view_evidencelink",
            "add_evidencereverificationevent",
        )
        self.client.force_login(self.reverifier)
        link = self.evidence["checklist"]

        response = self.client.post(
            reverse("admin:knowledge_evidencelink_changelist"),
            {
                "action": "reverify_selected_evidence",
                "_selected_action": str(link.pk),
                "apply": "1",
                "verification_state": "current",
                "verified_on": "2026-09-06",
                "reverify_on": "2026-12-06",
                "rationale": "Admin lifecycle re-verification test.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            EvidenceReverificationEvent.objects.filter(
                anchor_evidence_link=link,
                actor=self.reverifier,
            ).exists()
        )

    def test_unauthorized_reverification_post_is_rejected(self) -> None:
        self._grant(self.viewer, "view_evidencelink")
        self.client.force_login(self.viewer)
        link = self.evidence["checklist"]
        before = EvidenceReverificationEvent.objects.filter(anchor_evidence_link=link).count()

        response = self.client.post(
            reverse("admin:knowledge_evidencelink_changelist"),
            {
                "action": "reverify_selected_evidence",
                "_selected_action": str(link.pk),
                "apply": "1",
                "verification_state": "current",
                "verified_on": "2026-09-06",
                "reverify_on": "2026-12-06",
                "rationale": "Unauthorized re-verification attempt.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            EvidenceReverificationEvent.objects.filter(anchor_evidence_link=link).count(),
            before,
        )
        self.assertIn(
            "You do not have permission to perform that lifecycle action.",
            [str(message) for message in get_messages(response.wsgi_request)],
        )

    def test_authorized_clone_post_uses_service(self) -> None:
        self._grant(
            self.researcher,
            "view_procedureversion",
            "add_procedureversion",
            "change_procedureversion",
        )
        self.client.force_login(self.researcher)
        before = ProcedureVersion.objects.count()

        response = self.client.post(
            reverse("admin:knowledge_procedureversion_changelist"),
            {
                "action": "clone_selected_to_draft",
                "_selected_action": str(self.version.pk),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProcedureVersion.objects.count(), before + 1)
        successor = ProcedureVersion.objects.get(semantic_id="admin.lifecycle.v1.successor")
        self.assertEqual(successor.state, ProcedureVersion.State.DRAFT)
        self.assertEqual(successor.procedure_id, self.version.procedure_id)
        self.version.refresh_from_db()
        self.assertEqual(self.version.state, ProcedureVersion.State.PUBLISHED)

    def test_unauthorized_clone_post_is_rejected(self) -> None:
        self._grant(self.viewer, "view_procedureversion")
        self.client.force_login(self.viewer)
        before = ProcedureVersion.objects.count()

        response = self.client.post(
            reverse("admin:knowledge_procedureversion_changelist"),
            {
                "action": "clone_selected_to_draft",
                "_selected_action": str(self.version.pk),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProcedureVersion.objects.count(), before)
        self.assertIn(
            "You do not have permission to perform that lifecycle action.",
            [str(message) for message in get_messages(response.wsgi_request)],
        )
