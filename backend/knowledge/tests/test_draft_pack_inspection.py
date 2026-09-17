"""The inspector must report the applied importer state and leave no authoring writes."""

from __future__ import annotations

import copy
import threading
from datetime import date
from typing import Any
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings

from knowledge import models as m
from knowledge.draft_packs import export_draft_pack, import_draft_pack, inspect_draft_pack
from knowledge.draft_packs.errors import DraftPackError
from knowledge.draft_packs.state import LOCK_MODELS, digest
from knowledge.review_workflow import ProcedureVersionReviewPolicy
from knowledge.tests.test_draft_packs import claim, pack, rich_pack


def tables() -> str:
    return digest(
        {model._meta.label: list(model.objects.order_by("pk").values()) for model in LOCK_MODELS}
    )


def rich() -> dict[str, Any]:
    data = rich_pack()
    data["routing_associations"] = []
    data["evidence_links"] = [
        row
        for row in data["evidence_links"]
        if row["owner"]["kind"] != "procedure_service_point_association"
    ]
    return data


class InspectionTests(TestCase):
    def setUp(self) -> None:
        self.actor = User.objects.create_superuser("inspector", password="unused")

    def test_new_real_diff_proposed_diagnostics_rolls_back_and_confirms(self) -> None:
        before = tables()
        checked = inspect_draft_pack(rich(), actor=self.actor)
        self.assertEqual(tables(), before)
        kinds = {change.kind for change in checked.diff}
        self.assertTrue({"shared_create", "setup_create", "add"} <= kinds)
        version = next(change for change in checked.diff if change.path == ("version",))
        self.assertIsNone(version.before)
        assert version.after is not None
        self.assertEqual(version.after["semantic_id"], "draft")
        self.assertNotIn("id", version.after)
        self.assertTrue(checked.publication.diagnostics)
        self.assertEqual(checked.publication.prospective_publisher_id, self.actor.pk)
        result = import_draft_pack(
            rich(), actor=self.actor, inspection_precondition=checked.precondition
        )
        self.assertEqual(result["status"], "written")
        self.assertNotEqual(result["revision"], checked.import_result["revision"])
        # The pre-write token remains valid for an exact receipt-proven retry only.
        self.assertEqual(
            import_draft_pack(
                rich(), actor=self.actor, inspection_precondition=checked.precondition
            )["status"],
            "noop",
        )
        retried = inspect_draft_pack(rich(), actor=self.actor)
        self.assertEqual(retried.diff, ())
        self.assertEqual(retried.import_result["status"], "dry_run")

    def test_update_delete_evidence_scope_and_actual_trust_dates(self) -> None:
        import_draft_pack(rich(), actor=self.actor)
        m.ChecklistItem.objects.update(
            verification_state="current", verified_on=date(2026, 1, 1), reverify_on=date(2027, 1, 1)
        )
        m.EvidenceLink.objects.update(
            verification_state="current", verified_on=date(2026, 1, 1), reverify_on=date(2027, 1, 1)
        )
        data = export_draft_pack("draft", actor=self.actor)
        data["checklist_items"][0]["text_en"] = "Edited research"
        data["warnings"] = []
        data["evidence_links"] = [
            row for row in data["evidence_links"] if row["owner"]["kind"] != "warning"
        ]
        before = tables()
        checked = inspect_draft_pack(data, actor=self.actor, target_version="draft")
        self.assertEqual(before, tables())
        self.assertTrue(checked.requires_deletions)
        changes = {(change.kind, change.path): change for change in checked.diff}
        reset = changes[("trust_reset", ("checklist_items", "item"))]
        assert reset.before is not None and reset.after is not None
        self.assertEqual(reset.before["verified_on"], "2026-01-01")
        self.assertEqual(reset.after["verification_state"], "unknown")
        self.assertIsNone(reset.after["verified_on"])
        self.assertIsNone(reset.after["reverify_on"])
        self.assertIn(
            ("trust_reset", ("evidence_links", "checklist_item", "item", "evidence")), changes
        )
        self.assertIn(("delete", ("evidence_links", "warning", "warning", "evidence")), changes)
        with self.assertRaises(DraftPackError) as caught:
            import_draft_pack(
                data,
                actor=self.actor,
                target_version="draft",
                inspection_precondition=checked.precondition,
            )
        self.assertEqual(caught.exception.diagnostics[0].code, "deletions_require_confirmation")
        import_draft_pack(
            data,
            actor=self.actor,
            target_version="draft",
            allow_deletions=True,
            inspection_precondition=checked.precondition,
        )
        self.assertFalse(m.Warning.objects.exists())

    def test_scalar_types_and_evidence_reparent_are_not_lost(self) -> None:
        from knowledge.draft_packs.inspection import _diff

        changes = _diff(
            {("scenarios", "test"): {"source_facts": {"a": True}}},
            {("scenarios", "test"): {"source_facts": {"a": 1}}},
        )
        self.assertEqual(changes[0].fields, ("source_facts",))
        data = rich()
        data["checklist_items"].append({**claim("other"), "classification": "candidate"})
        import_draft_pack(data, actor=self.actor)
        exported = export_draft_pack("draft", actor=self.actor)
        for link in exported["evidence_links"]:
            if link["owner"]["kind"] == "checklist_item":
                link["owner"]["semantic_id"] = "other"
        checked = inspect_draft_pack(exported, actor=self.actor, target_version="draft")
        paths = {(c.kind, c.path) for c in checked.diff}
        self.assertIn(("delete", ("evidence_links", "checklist_item", "item", "evidence")), paths)
        self.assertIn(("add", ("evidence_links", "checklist_item", "other", "evidence")), paths)

    @override_settings(PROCEDURE_VERSION_REVIEW_MODE="independent")
    def test_stale_new_shared_and_configuration_inputs(self) -> None:
        checked = inspect_draft_pack(pack(), actor=self.actor)
        m.Authority.objects.create(semantic_id="unrelated", name_ar="جهة", name_en="Authority")
        with self.assertRaises(DraftPackError) as caught:
            import_draft_pack(
                pack(), actor=self.actor, inspection_precondition=checked.precondition
            )
        self.assertEqual(caught.exception.diagnostics[0].code, "stale_inspection")
        self.assertFalse(m.ProcedureVersion.objects.exists())
        checked = inspect_draft_pack(pack(), actor=self.actor)
        for setting, value in (
            ("PROCEDURE_VERSION_REVIEW_MODE", "solo"),
            ("PLANNING_SCENARIOS_REQUIRED", True),
            ("SELECTION_QUESTIONS_REQUIRED", True),
            ("PROCEDURE_VERSION_PUBLICATION_GATES", []),
        ):
            with self.subTest(setting=setting), override_settings(**{setting: value}):
                with self.assertRaises(DraftPackError) as caught:
                    import_draft_pack(
                        pack(), actor=self.actor, inspection_precondition=checked.precondition
                    )
                self.assertEqual(caught.exception.diagnostics[0].code, "stale_inspection")

    def test_stale_review_trust_and_exported_base_are_independent_checks(self) -> None:
        import_draft_pack(rich(), actor=self.actor)
        data = export_draft_pack("draft", actor=self.actor)
        data["version"]["text_en"] = "new draft text"
        for mutate in (
            lambda: ProcedureVersionReviewPolicy.objects.update(legal_risk=True),
            lambda: m.ChecklistItem.objects.update(verified_on=date(2026, 1, 1)),
        ):
            checked = inspect_draft_pack(data, actor=self.actor, target_version="draft")
            mutate()
            with self.assertRaises(DraftPackError) as caught:
                import_draft_pack(
                    data,
                    actor=self.actor,
                    target_version="draft",
                    inspection_precondition=checked.precondition,
                )
            self.assertEqual(caught.exception.diagnostics[0].code, "stale_inspection")
            data = export_draft_pack("draft", actor=self.actor)
            data["version"]["text_en"] = "new draft text"
        checked = inspect_draft_pack(data, actor=self.actor, target_version="draft")
        data["base_revision"] = "0" * 64
        with self.assertRaises(DraftPackError) as caught:
            import_draft_pack(
                data,
                actor=self.actor,
                target_version="draft",
                inspection_precondition=checked.precondition,
            )
        self.assertEqual(caught.exception.diagnostics[0].code, "stale_revision")

    def test_database_failure_is_safe_and_rolls_back_speculative_writes(self) -> None:
        before = tables()
        with patch(
            "knowledge.draft_packs.service._manual", side_effect=DatabaseError("private pack")
        ):
            with self.assertRaises(DraftPackError) as caught:
                inspect_draft_pack(pack(), actor=self.actor)
        self.assertEqual(caught.exception.diagnostics[0].code, "database_error")
        self.assertNotIn("private pack", str(caught.exception))
        self.assertEqual(before, tables())

    def test_import_inspection_needs_change_not_view_and_reauthorizes_confirm(self) -> None:
        actor = User.objects.create_user("editor", is_staff=True)
        permissions = Permission.objects.filter(content_type__app_label="knowledge").exclude(
            codename="view_procedureversion"
        )
        actor.user_permissions.set(permissions)
        checked = inspect_draft_pack(pack(), actor=actor)
        actor.user_permissions.clear()
        with self.assertRaises(DraftPackError) as caught:
            import_draft_pack(pack(), actor=actor, inspection_precondition=checked.precondition)
        self.assertEqual(caught.exception.diagnostics[0].code, "permission_denied")

    def test_risk_increase_and_unchanged_scenario_staleness(self) -> None:
        import_draft_pack(rich(), actor=self.actor)
        data = export_draft_pack("draft", actor=self.actor)
        data["risks"]["legal"] = True
        data["version"]["text_en"] = "changed"
        checked = inspect_draft_pack(data, actor=self.actor, target_version="draft")
        changes = {(row.kind, row.path): row for row in checked.diff}
        self.assertEqual(changes[("risk_increase", ("risks", "legal"))].after, {"legal": True})
        self.assertIn(("scenario_stale", ("scenarios", "synthetic-invalid")), changes)


class InspectionConcurrencyTests(TransactionTestCase):
    def test_two_connection_writer_conflict_is_safe_and_retryable(self) -> None:
        actor = User.objects.create_superuser("inspector", password="unused")
        ready, release = threading.Event(), threading.Event()
        errors: list[BaseException] = []

        def writer() -> None:
            close_old_connections()
            try:
                with transaction.atomic():
                    m.Authority.objects.create(semantic_id="busy", name_ar="جهة", name_en="Busy")
                    ready.set()
                    release.wait(15)
            except BaseException as exc:
                errors.append(exc)
            finally:
                connection.close()

        thread = threading.Thread(target=writer)
        thread.start()
        try:
            self.assertTrue(ready.wait(10))
            with self.assertRaises(DraftPackError) as caught:
                inspect_draft_pack(copy.deepcopy(pack()), actor=actor)
            self.assertEqual(caught.exception.diagnostics[0].code, "concurrent_edit")
        finally:
            release.set()
            thread.join(15)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertFalse(m.ProcedureVersion.objects.exists())
