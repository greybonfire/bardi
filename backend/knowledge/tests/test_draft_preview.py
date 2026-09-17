"""Readiness and stored-scenario preview exercise production gates without publishing."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import patch

from bardi.settings.base import PROCEDURE_VERSION_PUBLICATION_GATES
from django.contrib.auth.models import Permission, User
from django.db import connection, transaction
from django.test import TestCase, override_settings

from knowledge import models as m
from knowledge.draft_packs import import_draft_pack, inspect_draft_pack
from knowledge.draft_packs.errors import DraftPackError
from knowledge.draft_preview import check_draft_publication, preview_draft_scenario
from knowledge.planning_scenarios import PlanningScenario
from knowledge.publication import (
    PublicationContext,
    PublicationDiagnostic,
    PublicationRejected,
    ReviewPublicationDecision,
    publish_procedure_version,
)
from knowledge.review_workflow import ProcedureVersionReviewPolicy
from knowledge.tests.test_draft_pack_inspection import tables
from knowledge.tests.test_draft_packs import pack, rule

CALLBACKS: list[str] = []


class SideEffectGate:
    name = "test.side_effect"

    def validate(self, context: PublicationContext) -> tuple[PublicationDiagnostic, ...]:
        m.Authority.objects.create(semantic_id="gate-write", name_ar="جهة", name_en="Gate")
        transaction.on_commit(lambda: CALLBACKS.append("committed"))
        context.version.text_en = "gate-mutated instance"
        context.version.save()
        return ()


class PoisonGate:
    name = "test.poison"

    def validate(self, context: PublicationContext) -> tuple[PublicationDiagnostic, ...]:
        transaction.on_commit(lambda: CALLBACKS.append("poison"))
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 / 0")
        return ()


class LaterGate:
    name = "test.later"

    def validate(self, context: PublicationContext) -> tuple[PublicationDiagnostic, ...]:
        # An actual query proves a poisoned preceding gate was isolated.
        m.ProcedureVersion.objects.count()
        return (PublicationDiagnostic(self.name, "later_gate_ran"),)


class BadDecisionGate:
    name = "test.bad_decision"

    def validate(self, context: PublicationContext) -> tuple[PublicationDiagnostic, ...]:
        if context.review_decision is None:
            context.review_decision = ReviewPublicationDecision("solo", -1, -1, "bad", ())
        else:
            context.review_decision = replace(context.review_decision, signature="bad")
        return ()


@override_settings(
    PROCEDURE_VERSION_PUBLICATION_GATES=PROCEDURE_VERSION_PUBLICATION_GATES,
    PLANNING_SCENARIOS_REQUIRED=True,
    SELECTION_QUESTIONS_REQUIRED=True,
    PROCEDURE_VERSION_REVIEW_MODE="solo",
)
class DraftPreviewTests(TestCase):
    def setUp(self) -> None:
        self.actor = User.objects.create_superuser("previewer", password="unused")
        data = pack()
        data["version"].update(text_ar="بحث", text_en="Research", applicability=rule())
        import_draft_pack(data, actor=self.actor)
        m.Service.objects.update(is_active=True)
        m.FactDefinition.objects.filter(key="synthetic_ready").update(is_published=True)
        self.version = m.ProcedureVersion.objects.get(semantic_id="draft")
        self.scenarios = [
            self.scenario(
                "positive", {"synthetic_ready": True}, "plan", {"procedure_version_id": "draft"}
            ),
            self.scenario(
                "negative",
                {"synthetic_ready": False},
                "inconclusive",
                {"reason": "no_matching_researched_procedure"},
            ),
            self.scenario("unknown", {}, "next_question", {"question_id": "ready"}),
        ]
        CALLBACKS.clear()

    def scenario(
        self,
        kind: str,
        facts: dict[str, Any],
        family: str,
        identifiers: dict[str, Any],
        diagnostics: list[str] | None = None,
    ) -> PlanningScenario:
        return PlanningScenario.objects.create(
            procedure_version=self.version,
            name=kind,
            kind=kind,
            evaluation_context={"evaluation_date": "2026-01-01", "locale": "ar"},
            source_facts=facts,
            expected_result_family=family,
            expected_identifiers=identifiers,
            expected_diagnostics=diagnostics or [],
        )

    def test_readiness_parity_with_production_gates_and_no_publication(self) -> None:
        before = tables()
        checked = check_draft_publication(self.version.pk, actor=self.actor)
        self.assertEqual(checked.diagnostics, ())
        self.assertEqual(checked.review_mode, "solo")
        self.assertEqual(before, tables())
        published = publish_procedure_version(self.version.pk, actor=self.actor)
        self.assertEqual(published.state, "published")

    def test_independent_and_all_four_risks_remain_blocking_in_both_modes(self) -> None:
        ProcedureVersionReviewPolicy.objects.update(
            legal_risk=True,
            military_risk=True,
            custody_guardianship_risk=True,
            contested_identity_risk=True,
        )
        for mode in ("solo", "independent"):
            with self.subTest(mode=mode), override_settings(PROCEDURE_VERSION_REVIEW_MODE=mode):
                before = tables()
                checked = check_draft_publication(self.version.pk, actor=self.actor)
                self.assertEqual(before, tables())
                specialists = {
                    d.detail for d in checked.diagnostics if d.code == "missing_specialist_approval"
                }
                self.assertEqual(
                    specialists, {"legal", "military", "custody_guardianship", "contested_identity"}
                )
                self.assertEqual(
                    any(d.code == "missing_review_approval" for d in checked.diagnostics),
                    mode == "independent",
                )
                with self.assertRaises(PublicationRejected) as caught:
                    publish_procedure_version(self.version.pk, actor=self.actor)
                self.assertEqual(checked.diagnostics, caught.exception.diagnostics)

    def test_missing_publish_privilege_does_not_short_circuit_other_gates(self) -> None:
        viewer = User.objects.create_user("viewer", is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename="view_procedureversion"))
        self.scenarios[0].delete()
        checked = check_draft_publication(self.version.pk, actor=viewer)
        codes = {d.code for d in checked.diagnostics}
        self.assertIn("missing_publish_permission", codes)
        self.assertIn("missing_required_scenario", codes)
        viewer.is_active = False
        viewer.save()
        with self.assertRaises(DraftPackError):
            check_draft_publication(self.version.pk, actor=viewer)

    def test_side_effects_callbacks_and_poisoned_gates_are_rolled_back(self) -> None:
        paths = tuple(
            f"knowledge.tests.test_draft_preview.{name}"
            for name in ("SideEffectGate", "PoisonGate", "LaterGate")
        )
        before = tables()
        with override_settings(PROCEDURE_VERSION_PUBLICATION_GATES=paths[:1]):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                checked = check_draft_publication(self.version.pk, actor=self.actor)
            self.assertEqual(checked.diagnostics, ())
            self.assertEqual(callbacks, [])
            self.assertEqual(before, tables())
        with override_settings(PROCEDURE_VERSION_PUBLICATION_GATES=paths):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                checked = check_draft_publication(self.version.pk, actor=self.actor)
            self.assertEqual(callbacks, [])
            self.assertEqual(before, tables())
            self.assertEqual(CALLBACKS, [])
            self.assertIn("gate_execution_failed", {d.code for d in checked.diagnostics})
            self.assertIn("later_gate_ran", {d.code for d in checked.diagnostics})
            # Proposed-state inspection must isolate gate writes, too.
            from knowledge.draft_packs import export_draft_pack

            data = export_draft_pack("draft", actor=self.actor)
            data["version"]["text_en"] = "proposed text"
            checked_pack = inspect_draft_pack(data, actor=self.actor, target_version="draft")
            self.assertEqual(before, tables())
            change = next(c for c in checked_pack.diff if c.path == ("version",))
            assert change.after is not None
            self.assertEqual(change.after["text_en"], "proposed text")

    def test_post_gate_review_decision_validation_is_shared(self) -> None:
        paths = (
            *PROCEDURE_VERSION_PUBLICATION_GATES,
            "knowledge.tests.test_draft_preview.BadDecisionGate",
        )
        with override_settings(PROCEDURE_VERSION_PUBLICATION_GATES=paths):
            checked = check_draft_publication(self.version.pk, actor=self.actor)
            self.assertIn("invalid_review_decision", {d.code for d in checked.diagnostics})
            with self.assertRaises(PublicationRejected) as caught:
                publish_procedure_version(self.version.pk, actor=self.actor)
            self.assertEqual(checked.diagnostics, caught.exception.diagnostics)

    def test_four_result_families_detached_and_unchanged(self) -> None:
        invalid = self.scenario(
            "contradictory",
            {"synthetic_ready": "wrong type"},
            "invalid",
            {},
            ["invalid_fact_value"],
        )
        before = tables()
        for scenario in (*self.scenarios, invalid):
            with self.subTest(family=scenario.expected_result_family):
                preview = preview_draft_scenario(self.version.pk, scenario.pk, actor=self.actor)
                assert preview.result is not None
                self.assertEqual(preview.result.type, scenario.expected_result_family)
                self.assertTrue(preview.matches_expectations)
                self.assertFalse(preview.stale)
                self.assertEqual(preview.diagnostics, ())
                self.assertEqual(preview.authored_locale, "ar")
        self.assertEqual(before, tables())

    def test_stale_valid_runs_without_resealing_and_mismatch_is_separate(self) -> None:
        m.ProcedureVersion.objects.filter(pk=self.version.pk).update(text_en="Changed")
        before = tables()
        preview = preview_draft_scenario(self.version.pk, self.scenarios[0].pk, actor=self.actor)
        self.assertTrue(preview.stale)
        self.assertTrue(preview.matches_expectations)
        self.assertEqual(before, tables())
        PlanningScenario.objects.filter(pk=self.scenarios[0].pk).update(
            expected_identifiers={"procedure_version_id": "draft", "service_id": "wrong"}
        )
        preview = preview_draft_scenario(self.version.pk, self.scenarios[0].pk, actor=self.actor)
        self.assertFalse(preview.matches_expectations)
        self.assertTrue(preview.stale)

    def test_invalid_owner_notfound_permission_and_finalized(self) -> None:
        PlanningScenario.objects.filter(pk=self.scenarios[0].pk).update(evaluation_context={})
        preview = preview_draft_scenario(self.version.pk, self.scenarios[0].pk, actor=self.actor)
        self.assertIsNone(preview.result)
        self.assertIsNone(preview.matches_expectations)
        self.assertEqual(preview.diagnostics[0].code, "invalid_scenario")
        # Malformed legacy JSON can raise AttributeError within model.clean, not ValidationError.
        PlanningScenario.objects.filter(pk=self.scenarios[2].pk).update(expected_identifiers=[])
        preview = preview_draft_scenario(self.version.pk, self.scenarios[2].pk, actor=self.actor)
        self.assertIsNone(preview.result)
        self.assertEqual(preview.diagnostics[0].code, "invalid_scenario")
        other = m.ProcedureVersion.objects.create(
            semantic_id="other", procedure=self.version.procedure
        )
        for version, scenario in (
            (other.pk, self.scenarios[0].pk),
            (self.version.pk, -1),
            (-1, -1),
        ):
            with self.assertRaises(DraftPackError) as caught:
                preview_draft_scenario(version, scenario, actor=self.actor)
            self.assertEqual(caught.exception.diagnostics[0].code, "not_found")
        viewer = User.objects.create_user("nonstaff")
        with self.assertRaises(DraftPackError):
            preview_draft_scenario(self.version.pk, self.scenarios[1].pk, actor=viewer)
        with override_settings(
            PROCEDURE_VERSION_PUBLICATION_GATES=(), PLANNING_SCENARIOS_REQUIRED=False
        ):
            publish_procedure_version(self.version.pk, actor=self.actor)
        with self.assertRaises(DraftPackError) as caught:
            check_draft_publication(self.version.pk, actor=self.actor)
        self.assertEqual(caught.exception.diagnostics[0].code, "immutable_version")
        with self.assertRaises(DraftPackError):
            preview_draft_scenario(self.version.pk, self.scenarios[1].pk, actor=self.actor)

    def test_overlap_is_unavailable_and_inactive_service_is_honest(self) -> None:
        m.Service.objects.update(is_active=False)
        before = tables()
        preview = preview_draft_scenario(self.version.pk, self.scenarios[0].pk, actor=self.actor)
        assert preview.result is not None
        self.assertEqual(preview.result.type, "inconclusive")
        self.assertFalse(preview.matches_expectations)
        self.assertEqual(before, tables())
        other = m.ProcedureVersion.objects.create(
            semantic_id="published",
            procedure=self.version.procedure,
            applicability=rule(),
            text_ar="بحث",
            text_en="Research",
        )
        with override_settings(PROCEDURE_VERSION_PUBLICATION_GATES=()):
            publish_procedure_version(other.pk, actor=self.actor)
        before = tables()
        preview = preview_draft_scenario(self.version.pk, self.scenarios[0].pk, actor=self.actor)
        self.assertIsNone(preview.result)
        self.assertIsNone(preview.matches_expectations)
        self.assertEqual(preview.diagnostics[0].code, "overlapping_published_version")
        self.assertEqual(before, tables())

    def test_shared_runner_reuses_snapshots_per_date_and_keeps_prior_failures(self) -> None:
        from knowledge.evidence_workflow_temporal import load_knowledge_snapshot_as_of
        from knowledge.planning_scenarios import _execute_scenarios, _run_stored_scenarios

        context = PublicationContext(self.version, self.actor, {})
        before = tables()
        with patch(
            "knowledge.evidence_workflow_temporal.load_knowledge_snapshot_as_of",
            wraps=load_knowledge_snapshot_as_of,
        ) as load:
            results, diagnostics = _run_stored_scenarios(context, tuple(self.scenarios))
        self.assertEqual(diagnostics, ())
        self.assertEqual(len(results), 3)
        self.assertEqual(load.call_count, 1)
        with (
            patch(
                "knowledge.planning_scenarios.plan_stateless",
                side_effect=[
                    results[self.scenarios[0].pk],
                    RuntimeError("private failure"),
                ],
            ),
            patch("knowledge.planning_scenarios._scenario_matches", return_value=False),
        ):
            diagnostics = _execute_scenarios(context, tuple(self.scenarios))
        self.assertEqual(
            {(d.code, d.detail) for d in diagnostics},
            {
                ("scenario_failed", "positive"),
                ("scenario_execution_failed", "negative"),
            },
        )
        self.assertEqual(before, tables())

    def test_evaluation_error_and_poisoned_database_restore_settings(self) -> None:
        before = tables()
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('bardi.procedure_version_lifecycle', 'caller', true)")
        for poison in (False, True):

            def fail(*args: Any, poison: bool = poison, **kwargs: Any) -> Any:
                transaction.on_commit(lambda: CALLBACKS.append("planner"))
                if poison:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT 1 / 0")
                raise RuntimeError("private source facts must not leak")

            with (
                self.subTest(poison=poison),
                patch("knowledge.planning_scenarios.plan_stateless", side_effect=fail),
                self.captureOnCommitCallbacks(execute=True) as callbacks,
            ):
                preview = preview_draft_scenario(
                    self.version.pk, self.scenarios[0].pk, actor=self.actor
                )
                self.assertIsNone(preview.result)
                self.assertIsNone(preview.matches_expectations)
                self.assertEqual(preview.diagnostics[0].code, "scenario_execution_failed")
                self.assertNotIn("private", str(preview))
            self.assertEqual(callbacks, [])
            self.assertEqual(CALLBACKS, [])
            self.assertEqual(before, tables())
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('bardi.procedure_version_lifecycle')")
                self.assertEqual(cursor.fetchone()[0], "caller")
        preview_draft_scenario(self.version.pk, self.scenarios[0].pk, actor=self.actor)
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('bardi.procedure_version_lifecycle')")
            self.assertEqual(cursor.fetchone()[0], "caller")
