"""Durable safety regressions for the shared draft authoring interface."""

from __future__ import annotations

import json
import tempfile
import threading
import time
from collections.abc import Callable
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.management import call_command, load_command_class
from django.core.management.base import CommandError
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from knowledge import models as m
from knowledge.domain import load_knowledge_snapshot
from knowledge.draft_packs import export_draft_context, export_draft_pack, import_draft_pack
from knowledge.draft_packs.errors import DraftPackError
from knowledge.draft_packs.mapping import OWNED
from knowledge.draft_packs.schema import parse_draft_pack
from knowledge.draft_packs.state import digest, locked_snapshot
from knowledge.evidence_workflow import EvidenceReverificationEvent, open_evidence_discrepancy
from knowledge.planning_scenarios import PlanningScenario
from knowledge.publication import publish_procedure_version, withdraw_procedure_version
from knowledge.review_workflow import (
    ProcedureVersionReviewApproval,
    ProcedureVersionReviewPolicy,
    review_state_signature,
)
from knowledge.service_point_routing import ServicePoint, ServicePointVersion


def pack() -> dict[str, Any]:
    return {
        "format": "bardi.draft-pack",
        "format_version": 1,
        "base_revision": None,
        "catalog": {
            "services": [{"semantic_id": "research", "text_ar": "بحث", "text_en": "Research"}],
            "procedures": [
                {
                    "semantic_id": "procedure",
                    "text_ar": "بحث",
                    "text_en": "Research",
                    "primary_service": "research",
                }
            ],
            "facts": [{"key": "synthetic_ready", "kind": "boolean"}],
            "authorities": [],
            "sources": [],
            "document_types": [],
        },
        "version": {"semantic_id": "draft", "procedure": "procedure"},
        "risks": dict.fromkeys(
            ("legal", "military", "custody_guardianship", "contested_identity"), False
        ),
        "service_setup": {
            "service": "research",
            "questions": [
                {
                    "semantic_id": "ready",
                    "fact": "synthetic_ready",
                    "text_ar": "بحث؟",
                    "text_en": "Synthetic ready?",
                    "priority": 1,
                }
            ],
            "candidates": [{"procedure": "procedure", "selection_predicate": rule()}],
            "contradictions": [],
        },
        **{key: [] for key in OWNED},
        "evidence_links": [],
    }


def rule() -> dict[str, Any]:
    return {"op": "eq", "fact": "synthetic_ready", "value": True}


def claim(identity: str) -> dict[str, Any]:
    return {"semantic_id": identity, "text_ar": "بحث", "text_en": "Synthetic research"}


def rich_pack() -> dict[str, Any]:
    data = pack()
    data["catalog"]["authorities"] = [
        {"semantic_id": "synthetic-authority", "name_ar": "بحث", "name_en": "Synthetic"}
    ]
    data["catalog"]["sources"] = [
        {
            "semantic_id": "source",
            "authority": "synthetic-authority",
            "title": "Synthetic fixture only",
            "locator": "https://example.invalid/synthetic",
            "classification": "secondary",
            "retrieved_on": "2026-01-01",
        }
    ]
    data["catalog"]["document_types"] = [
        {"semantic_id": "document", "name_ar": "بحث", "name_en": "Synthetic"}
    ]
    data["catalog"]["procedures"].append({**claim("prerequisite"), "primary_service": "research"})
    data["catalog"]["facts"].append({"key": "synthetic_other", "kind": "boolean"})
    data["service_setup"]["questions"][0]["resolves_facts"] = ["synthetic_ready", "synthetic_other"]
    data["service_setup"]["contradictions"] = [
        {
            "semantic_id": "conflict",
            "condition": {
                "op": "all",
                "children": [rule(), {"op": "eq", "fact": "synthetic_other", "value": False}],
            },
            "facts": ["synthetic_other", "synthetic_ready"],
        }
    ]
    data["bases"] = [{**claim("basis"), "qualification": rule()}]
    data["checklist_items"] = [
        {
            **claim("item"),
            "classification": "candidate",
            "document_type": "document",
            "scope": "eligibility_basis",
            "scope_reference": "basis",
        }
    ]
    data["steps"] = [
        {
            **claim("step"),
            "phase": "prepare",
            "scope": "eligibility_basis",
            "eligibility_basis": "basis",
        }
    ]
    data["warnings"] = [{**claim("warning"), "kind": "administrative"}]
    data["fees"] = [
        {
            **claim("fee"),
            "value_state": "unverified",
            "amount": 5,
            "currency": "EGP",
            "scope": "eligibility_basis",
            "eligibility_basis": "basis",
        }
    ]
    data["dependencies"] = [
        {**claim("dependency"), "target_procedure": "prerequisite", "satisfied_when": rule()}
    ]
    data["routing_associations"] = [
        {
            "semantic_id": "routing",
            "service_point_version": "point-version",
            "applicability": rule(),
        }
    ]
    data["evidence_links"] = [
        {
            "semantic_id": "evidence",
            "owner": {"kind": spec.owner_kind, "semantic_id": data[key][0]["semantic_id"]},
            "passage": "Synthetic fixture, not a government claim.",
            "sources": ["source"],
        }
        for key, spec in OWNED.items()
        if spec.owner_kind
    ]
    data["scenarios"] = [
        {
            "name": "synthetic-invalid",
            "kind": "contradictory",
            "evaluation_context": {"evaluation_date": "2026-01-01", "locale": "en"},
            "source_facts": {"synthetic_ready": "deliberately invalid boolean"},
            "expected_result_family": "invalid",
            "expected_diagnostics": ["invalid_fact"],
        }
    ]
    return data


class DraftPackTests(TestCase):
    def setUp(self) -> None:
        self.actor = User.objects.create_superuser("author", password="unused")

    def apply(self, data: Any, **kwargs: Any) -> dict[str, Any]:
        return import_draft_pack(data, actor=self.actor, **kwargs)

    def exported(self) -> dict[str, Any]:
        return export_draft_pack("draft", actor=self.actor)

    def reject(self, code: str, data: Any, **kwargs: Any) -> DraftPackError:
        with self.assertRaises(DraftPackError) as caught:
            self.apply(data, **kwargs)
        self.assertIn(code, {d.code for d in caught.exception.diagnostics})
        return caught.exception

    def rich(self) -> dict[str, Any]:
        point = ServicePoint.objects.create(semantic_id="point", name_ar="بحث", name_en="Synthetic")
        ServicePointVersion.objects.create(
            semantic_id="point-version",
            service_point=point,
            address_ar="بحث",
            address_en="Synthetic",
            availability="unknown",
            effective_from=date(2026, 1, 1),
        )
        data = rich_pack()
        self.apply(data)
        return data

    def test_documented_synthetic_example_imports_in_disposable_database(self) -> None:
        example = (
            Path(__file__).resolve().parents[3] / "docs/draft-packs/examples/minimal-research.json"
        )
        result = self.apply(example.read_bytes())
        self.assertEqual(result["status"], "written")
        self.assertFalse(m.Service.objects.get().is_active)
        self.assertEqual(m.ServiceQuestion.objects.count(), 1)
        load_knowledge_snapshot()

    def test_new_inactive_unpublished_setup_and_proven_retry(self) -> None:
        data = pack()
        result = self.apply(data)
        self.assertEqual(result["status"], "written")
        self.assertFalse(m.Service.objects.get().is_active)
        self.assertFalse(m.FactDefinition.objects.get(key="synthetic_ready").is_published)
        self.assertEqual(m.ServiceQuestion.objects.get().resolved_fact_keys, ("synthetic_ready",))
        self.assertEqual(self.apply(data)["status"], "noop")
        self.assertEqual(m.DraftPackImportReceipt.objects.count(), 1)
        load_knowledge_snapshot()  # inactive setup validates against all Fact definitions

    def test_full_owned_roundtrip_does_not_save_or_reseal(self) -> None:
        self.rich()
        data = self.exported()
        parse_draft_pack(data)
        before = {key: list(spec.model.objects.values()) for key, spec in OWNED.items()}
        with CaptureQueriesContext(connection) as queries:
            result = self.apply(data, target_version="draft")
        writes = [q["sql"] for q in queries if q["sql"].startswith(("UPDATE", "INSERT", "DELETE"))]
        self.assertTrue(all("draftpackimportreceipt" in sql for sql in writes), writes)
        self.assertEqual(result["status"], "noop")
        self.assertEqual(
            before, {key: list(spec.model.objects.values()) for key, spec in OWNED.items()}
        )
        self.assertEqual(self.exported(), data)
        self.assertEqual(m.EvidenceLink.objects.count(), 7)
        self.assertEqual(
            OWNED["fees"].model.objects.get().verification_state, "needs_reverification"
        )

    def test_dry_run_and_structural_error_rollback_everything(self) -> None:
        self.assertEqual(self.apply(pack(), dry_run=True)["status"], "dry_run")
        self.assertFalse(m.Service.objects.exists())
        self.assertFalse(m.DraftPackImportReceipt.objects.exists())
        data = pack()
        data["steps"] = [
            {
                **claim("step"),
                "phase": "prepare",
                "scope": "eligibility_basis",
                "eligibility_basis": "missing",
            }
        ]
        error = self.reject("unresolved_reference", data)
        self.assertEqual(error.diagnostics[0].path, ("steps", 0, "eligibility_basis"))
        self.assertFalse(m.Service.objects.exists())

    def test_existing_active_and_inactive_service_setup_is_compare_only(self) -> None:
        self.apply(pack())
        for active in (False, True):
            m.Service.objects.update(is_active=active)
            data = self.exported()
            data["service_setup"]["questions"][0]["text_en"] = "Changed"
            self.reject("protected_service_setup", data, target_version="draft")
            data = self.exported()
            data["service_setup"]["questions"] = []
            self.reject("protected_service_setup", data, target_version="draft")
            data["service_setup"] = None
            self.apply(data, target_version="draft")
            self.assertEqual(m.ServiceQuestion.objects.count(), 1)

    def test_preexisting_empty_service_cannot_receive_initial_setup(self) -> None:
        m.Service.objects.create(**pack()["catalog"]["services"][0])
        self.reject("protected_service_setup", pack())
        self.assertFalse(m.ProcedureVersion.objects.exists())

    def test_shared_conflicts_do_not_overwrite(self) -> None:
        self.apply(pack())
        data = self.exported()
        data["catalog"]["facts"][0]["kind"] = "string"
        self.reject("shared_conflict", data, target_version="draft")
        self.assertEqual(m.FactDefinition.objects.get(key="synthetic_ready").kind, "boolean")

    def test_actor_flags_and_permissions_are_reloaded(self) -> None:
        self.actor.is_staff = False  # DB truth wins over caller flags
        self.apply(pack())
        User.objects.filter(pk=self.actor.pk).update(is_active=False)
        self.actor.is_active = self.actor.is_staff = True
        self.reject("permission_denied", self.export_for_permissions(), target_version="draft")
        with self.assertRaises(DraftPackError):
            export_draft_context(actor=self.actor)

    def export_for_permissions(self) -> dict[str, Any]:
        return pack()

    def test_catalog_and_setup_creation_require_individual_permissions(self) -> None:
        staff = User.objects.create_user("staff", is_staff=True)
        staff.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["add_procedureversion", "change_procedureversion"]
            )
        )
        with self.assertRaises(DraftPackError):
            import_draft_pack(pack(), actor=staff)
        staff.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["add_service", "add_procedure", "add_factdefinition"]
            )
        )
        with self.assertRaises(DraftPackError) as caught:
            import_draft_pack(pack(), actor=staff)
        self.assertEqual(caught.exception.diagnostics[0].path[:2], ("service_setup", "questions"))
        self.assertFalse(m.Service.objects.exists())

    def test_author_retained_and_risk_cannot_be_cleared(self) -> None:
        data = pack()
        data["risks"]["legal"] = True
        self.apply(data)
        other = User.objects.create_superuser("other", password="unused")
        exported = self.exported()
        exported["version"]["text_en"] = "Update"
        import_draft_pack(exported, actor=other, target_version="draft")
        self.assertEqual(ProcedureVersionReviewPolicy.objects.get().author_id, self.actor.pk)
        exported = self.exported()
        exported["risks"]["legal"] = False
        self.reject("risk_reduction", exported, target_version="draft")
        self.assertFalse(ProcedureVersionReviewApproval.objects.exists())

    def test_trust_only_change_invalidates_revision_and_receipt(self) -> None:
        data = self.rich()
        exported = self.exported()
        m.ChecklistItem.objects.filter(semantic_id="item").update(verification_state="current")
        self.reject("stale_revision", exported, target_version="draft")
        self.reject("identity_collision", data)

    def test_exact_stale_retry_requires_complete_unchanged_post_state(self) -> None:
        self.apply(pack())
        data = self.exported()
        data["version"]["text_en"] = "Changed"
        self.apply(data, target_version="draft")
        self.assertEqual(self.apply(data, target_version="draft")["status"], "noop")
        m.FactDefinition.objects.update(is_published=True)
        self.reject("stale_revision", data, target_version="draft")

    def test_explicit_target_and_exact_identity_required(self) -> None:
        self.apply(pack())
        self.reject("identity_collision", self.exported())
        data = self.exported()
        data["version"]["semantic_id"] = "renamed"
        self.reject("identity_mismatch", data, target_version="draft")
        self.reject("not_found", data, target_version="missing")

    def test_deletions_require_confirmation_and_dry_run_reports(self) -> None:
        self.rich()
        data = self.exported()
        data["evidence_links"] = []
        data["checklist_items"] = []
        self.reject("deletions_require_confirmation", data, target_version="draft")
        result = self.apply(data, target_version="draft", dry_run=True)
        self.assertTrue(any(c["kind"] == "delete" for c in result["changes"]))
        self.assertEqual(m.EvidenceLink.objects.count(), 7)
        self.apply(data, target_version="draft", allow_deletions=True)
        self.assertFalse(m.ChecklistItem.objects.exists())
        self.assertFalse(m.EvidenceLink.objects.exists())

    def test_changed_basis_resets_dependents_and_evidence_not_scenario_seal(self) -> None:
        self.rich()
        for key in ("bases", "checklist_items", "steps"):
            OWNED[key].model.objects.update(
                verification_state="current", verified_on=date(2026, 1, 1)
            )
        m.EvidenceLink.objects.update(verification_state="current", verified_on=date(2026, 1, 1))
        seal = PlanningScenario.objects.get().behavior_signature
        data = self.exported()
        data["bases"][0]["text_en"] = "Changed basis"
        result = self.apply(data, target_version="draft")
        for key in ("bases", "checklist_items", "steps"):
            self.assertEqual(OWNED[key].model.objects.get().verification_state, "unknown")
        self.assertEqual(PlanningScenario.objects.get().behavior_signature, seal)
        self.assertTrue(any(row["code"] == "scenario_stale" for row in result["manual_actions"]))
        self.assertEqual(
            m.EvidenceLink.objects.get(step__isnull=False).verification_state, "unknown"
        )

    def test_evidence_change_resets_owner_and_siblings(self) -> None:
        self.rich()
        item = m.ChecklistItem.objects.get()
        sibling = m.EvidenceLink.objects.create(
            checklist_item=item, semantic_id="sibling", passage="Synthetic"
        )
        m.ChecklistItem.objects.update(verification_state="current")
        m.EvidenceLink.objects.filter(checklist_item=item).update(verification_state="current")
        data = self.exported()
        next(row for row in data["evidence_links"] if row["owner"]["kind"] == "checklist_item")[
            "passage"
        ] = "Different synthetic passage"
        self.apply(data, target_version="draft")
        item.refresh_from_db()
        sibling.refresh_from_db()
        self.assertEqual(item.verification_state, "unknown")
        self.assertEqual(sibling.verification_state, "unknown")

    def test_discrepancy_history_blocks_edits_and_deletions(self) -> None:
        self.rich()
        link = m.EvidenceLink.objects.get(checklist_item__isnull=False)
        open_evidence_discrepancy(
            anchor_evidence_link=link,
            evidence_links=[link],
            rationale="Synthetic concern",
            actor=self.actor,
        )
        data = self.exported()
        data["checklist_items"][0]["text_en"] = "Changed"
        self.reject("protected_history", data, target_version="draft")
        data = self.exported()
        data["checklist_items"] = []
        data["evidence_links"] = [
            r for r in data["evidence_links"] if r["owner"]["kind"] != "checklist_item"
        ]
        self.reject("protected_history", data, target_version="draft", allow_deletions=True)

    def test_reverification_history_blocks_parent_semantic_change(self) -> None:
        self.rich()
        link = m.EvidenceLink.objects.get(step__isnull=False)
        # Model/Admin history can exist even though the public workflow service
        # directs ordinary draft authors to edit instead of re-verifying.
        EvidenceReverificationEvent.objects.create(
            anchor_evidence_link=link,
            reverify_on=None,
            verification_state="current",
            verified_on=date(2026, 1, 1),
            rationale="Synthetic review",
            actor=self.actor,
        )
        data = self.exported()
        data["version"]["text_en"] = "Changed"
        self.reject("protected_history", data, target_version="draft")

    def test_blank_legacy_evidence_export_errors_without_repair(self) -> None:
        self.rich()
        link = m.EvidenceLink.objects.first()
        assert link is not None
        link.semantic_id = ""
        link.save()
        with self.assertRaises(DraftPackError) as caught:
            self.exported()
        self.assertEqual(caught.exception.diagnostics[0].code, "legacy_evidence_identity")
        link.refresh_from_db()
        self.assertEqual(link.semantic_id, "")

    def test_context_not_importable(self) -> None:
        self.apply(pack())
        data = export_draft_context("research", actor=self.actor)
        self.assertFalse(
            next(row for row in data["facts"] if row["key"] == "synthetic_ready")["is_published"]
        )
        self.reject("invalid_schema", data)

    def test_timeout_restored_success_failure_and_dry_run(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '1234ms'")
        for data, kwargs in ((pack(), {"dry_run": True}), (pack(), {})):
            self.apply(data, **kwargs)
            with connection.cursor() as cursor:
                cursor.execute("SHOW lock_timeout")
                self.assertEqual(cursor.fetchone()[0], "1234ms")
        data = self.exported()
        data["version"]["procedure"] = "no"
        self.reject("identity_mismatch", data, target_version="draft")
        with connection.cursor() as cursor:
            cursor.execute("SHOW lock_timeout")
            self.assertEqual(cursor.fetchone()[0], "1234ms")

    def test_existing_derived_fact_is_reference_only(self) -> None:
        data = pack()
        data["version"]["applicability"] = {
            "op": "gte",
            "fact": "age_years_on_evaluation_date",
            "value": 18,
        }
        self.apply(data)
        self.assertNotIn(
            "age_years_on_evaluation_date",
            {row["key"] for row in self.exported()["catalog"]["facts"]},
        )
        data = self.exported()
        data["catalog"]["facts"].append(
            {"key": "age_years_on_evaluation_date", "kind": "integer", "minimum": 0}
        )
        self.reject("shared_conflict", data, target_version="draft")

    def test_blocking_dependency_cycle_is_rejected_atomically(self) -> None:
        self.apply(pack())
        procedure = m.Procedure.objects.create(
            **claim("target"), primary_service=m.Service.objects.get()
        )
        target = m.ProcedureVersion.objects.create(semantic_id="target-draft", procedure=procedure)
        OWNED["dependencies"].model.objects.create(
            procedure_version=target,
            **claim("back"),
            target_procedure=m.Procedure.objects.get(semantic_id="procedure"),
            satisfied_when=rule(),
        )
        data = self.exported()
        data["dependencies"] = [
            {**claim("cycle"), "target_procedure": "target", "satisfied_when": rule()}
        ]
        self.reject("dependency_cycle", data, target_version="draft")
        self.assertFalse(m.ProcedureVersion.objects.get(semantic_id="draft").dependencies.exists())

    def test_invalid_rule_and_fee_shape_are_field_addressed(self) -> None:
        data = pack()
        data["version"]["applicability"] = {"op": "eq", "fact": "undefined", "value": True}
        with self.assertRaises(DraftPackError) as caught:
            self.apply(data)
        self.assertEqual(caught.exception.diagnostics[0].path[:2], ("version", "applicability"))
        self.assertFalse(m.Service.objects.exists())
        data = pack()
        data["fees"] = [
            {
                **claim("fee"),
                "value_state": "range",
                "minimum_amount": 10,
                "maximum_amount": 2,
                "currency": "EGP",
            }
        ]
        self.reject("invalid_model", data)
        self.assertFalse(m.Service.objects.exists())

    def test_published_and_withdrawn_targets_and_retries_are_immutable(self) -> None:
        data = pack()
        self.apply(data)
        with patch("knowledge.publication._run_policy", return_value=()):
            version = publish_procedure_version(
                m.ProcedureVersion.objects.get().pk, actor=self.actor
            )
        self.reject("immutable_version", data)
        self.reject("immutable_version", self.exported(), target_version="draft")
        withdraw_procedure_version(version.pk, actor=self.actor)
        self.reject("immutable_version", self.exported(), target_version="draft")
        self.assertEqual(m.ProcedureVersionAuditEvent.objects.count(), 2)

    def test_approvals_preserved_and_new_approval_changes_revision(self) -> None:
        self.apply(pack())
        before = self.exported()
        signature = review_state_signature(m.ProcedureVersion.objects.get())
        approval = ProcedureVersionReviewApproval.objects.create(
            procedure_version=m.ProcedureVersion.objects.get(),
            approval_kind="dimension",
            dimension="rule_logic",
            reviewer=self.actor,
            reviewed_signature=signature,
            approved_at=timezone.now(),
        )
        self.reject("stale_revision", before, target_version="draft")
        stored = list(ProcedureVersionReviewApproval.objects.values())
        data = self.exported()
        data["version"]["text_en"] = "Edited"
        self.apply(data, target_version="draft")
        self.assertEqual(stored, list(ProcedureVersionReviewApproval.objects.values()))
        self.assertEqual(approval.reviewed_signature, signature)
        self.assertNotEqual(review_state_signature(m.ProcedureVersion.objects.get()), signature)

    def test_changed_scenario_is_resealed_but_same_scenario_is_not(self) -> None:
        self.rich()
        old = PlanningScenario.objects.get().behavior_signature
        data = self.exported()
        data["version"]["text_en"] = "Change behavior"
        self.apply(data, target_version="draft")
        self.assertEqual(PlanningScenario.objects.get().behavior_signature, old)
        data = self.exported()
        data["scenarios"][0]["source_facts"] = {"synthetic_ready": False}
        self.apply(data, target_version="draft")
        self.assertNotEqual(PlanningScenario.objects.get().behavior_signature, old)

    def test_json_type_only_scenario_edits_are_stored_reported_and_sealed(self) -> None:
        self.rich()
        for before, after in ((0, False), (1, 1.0)):
            with self.subTest(before=before, after=after):
                data = self.exported()
                data["scenarios"][0]["source_facts"] = {"synthetic_ready": before}
                self.apply(data, target_version="draft")
                old = PlanningScenario.objects.get().behavior_signature
                data = self.exported()
                data["version"]["text_en"] += " changed"
                self.apply(data, target_version="draft")
                data = self.exported()
                data["scenarios"][0]["source_facts"] = {"synthetic_ready": after}
                result = self.apply(data, target_version="draft")
                row = PlanningScenario.objects.get()
                self.assertIs(type(row.source_facts["synthetic_ready"]), type(after))
                self.assertNotEqual(row.behavior_signature, old)
                self.assertTrue(
                    any("source_facts" in change.get("fields", []) for change in result["changes"])
                )

    def test_setup_boolean_to_integer_is_a_protected_edit(self) -> None:
        self.apply(pack())
        data = self.exported()
        data["service_setup"]["candidates"][0]["selection_predicate"]["value"] = 1
        self.reject("protected_service_setup", data, target_version="draft")

    def test_invalid_scenario_nested_identity_like_facts_roundtrip_via_command(self) -> None:
        self.rich()
        data = self.exported()
        facts = {
            "synthetic_ready": [{"owner": {}}, {"semantic_id": []}, {"name": "x"}, {"name": "x"}]
        }
        data["scenarios"][0]["source_facts"] = facts
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "pack.json"
            source.write_text(json.dumps(data))
            output = StringIO()
            call_command(
                "import_draft_pack",
                str(source),
                target_version="draft",
                actor="author",
                stdout=output,
            )
            self.assertEqual(json.loads(output.getvalue())["status"], "written")
        exported = json.loads(json.dumps(self.exported()))
        self.assertEqual(exported["scenarios"][0]["source_facts"], facts)
        self.assertEqual(exported["scenarios"][0]["expected_diagnostics"], ["invalid_fact"])

    def test_version_semantics_reset_entire_trust_aggregate(self) -> None:
        self.rich()
        m.Warning.objects.update(verification_state="current", verified_on=date(2026, 1, 1))
        m.EvidenceLink.objects.update(verification_state="current")
        data = self.exported()
        data["version"]["applicability"] = rule()
        self.apply(data, target_version="draft")
        self.assertEqual(m.Warning.objects.get().verification_state, "unknown")
        self.assertFalse(m.EvidenceLink.objects.exclude(verification_state="unknown").exists())

    def test_source_membership_changes_reset_trust_but_never_edit_source(self) -> None:
        self.rich()
        m.Warning.objects.update(verification_state="current")
        before = list(m.Source.objects.values())
        data = self.exported()
        next(row for row in data["evidence_links"] if row["owner"]["kind"] == "warning")[
            "sources"
        ] = []
        self.apply(data, target_version="draft")
        self.assertEqual(m.Warning.objects.get().verification_state, "unknown")
        self.assertEqual(before, list(m.Source.objects.values()))

    def test_basis_can_be_deleted_after_surviving_claims_leave_its_scope(self) -> None:
        self.rich()
        data = self.exported()
        data["bases"] = []
        data["evidence_links"] = [
            row for row in data["evidence_links"] if row["owner"]["kind"] != "eligibility_basis"
        ]
        for key in ("checklist_items", "steps", "fees"):
            data[key][0]["scope"] = "procedure"
            data[key][0]["scope_reference" if key == "checklist_items" else "eligibility_basis"] = (
                "" if key == "checklist_items" else None
            )
        self.apply(data, target_version="draft", allow_deletions=True)
        self.assertFalse(m.EligibilityBasis.objects.exists())
        self.assertEqual(m.Step.objects.count(), 1)

    def test_complete_revision_keeps_submillisecond_workflow_timestamps(self) -> None:
        first = datetime(2026, 1, 1, microsecond=1001)
        second = first.replace(microsecond=1002)
        self.assertNotEqual(digest({"occurred_at": first}), digest({"occurred_at": second}))

    def test_prerequisite_trust_is_part_of_complete_revision(self) -> None:
        self.rich()
        target = m.ProcedureVersion.objects.create(
            semantic_id="prerequisite-draft",
            procedure=m.Procedure.objects.get(semantic_id="prerequisite"),
        )
        warning = m.Warning.objects.create(
            procedure_version=target, **claim("target-warning"), kind="administrative"
        )
        data = self.exported()
        m.Warning.objects.filter(pk=warning.pk).update(verification_state="current")
        self.reject("stale_revision", data, target_version="draft")

    def test_unchanged_rows_still_receive_structural_rule_validation(self) -> None:
        self.rich()
        m.ChecklistItem.objects.update(
            applicability={"op": "eq", "fact": "undefined", "value": True}
        )
        with self.assertRaises(DraftPackError) as caught:
            self.apply(self.exported(), target_version="draft")
        self.assertEqual(
            caught.exception.diagnostics[0].path[:3], ("checklist_items", 0, "applicability")
        )

    def test_product_warning_cannot_retain_unchanged_evidence(self) -> None:
        self.rich()
        data = self.exported()
        data["warnings"][0]["kind"] = "product"
        self.reject("invalid_model", data, target_version="draft")
        self.assertEqual(m.Warning.objects.get().kind, "administrative")

    def test_update_needs_change_not_add_permission(self) -> None:
        self.apply(pack())
        staff = User.objects.create_user("editor", is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename="change_procedureversion"))
        data = self.exported()
        data["version"]["text_en"] = "Edited by permitted staff"
        result = import_draft_pack(data, actor=staff, target_version="draft")
        self.assertEqual(result["status"], "written")
        with self.assertRaises(DraftPackError):
            import_draft_pack(pack(), actor=staff)

    def test_missing_readiness_is_manual_not_import_rejection(self) -> None:
        data = pack()
        data["service_setup"] = None
        data["version"]["applicability"] = rule()
        result = self.apply(data)
        codes = {row["code"] for row in result["manual_actions"]}
        self.assertTrue(
            {
                "question_coverage_required",
                "scenario_coverage_required",
                "fact_publication_required",
            }
            <= codes
        )

    def test_cli_database_failure_is_safe_machine_json(self) -> None:
        output = StringIO()
        with patch(
            "knowledge.management.commands.export_draft_pack.export_draft_pack",
            side_effect=DatabaseError("sensitive detail"),
        ):
            with self.assertRaises(CommandError):
                call_command("export_draft_pack", version="draft", actor="author", stdout=output)
        result = json.loads(output.getvalue())
        self.assertEqual(result["diagnostics"][0]["code"], "database_error")
        self.assertNotIn("sensitive", output.getvalue())

    def test_cli_json_bounded_reads_and_safe_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "pack.json"
            source.write_text(json.dumps(pack()))
            output = StringIO()
            call_command("import_draft_pack", str(source), new=True, actor="author", stdout=output)
            self.assertEqual(json.loads(output.getvalue())["status"], "written")
            target = Path(directory) / "export.json"
            call_command(
                "export_draft_pack",
                version="draft",
                actor="author",
                output=str(target),
                stdout=StringIO(),
            )
            parse_draft_pack(target.read_bytes())
            before = source.read_bytes()
            errors = StringIO()
            with self.assertRaises(CommandError):
                call_command(
                    "export_draft_pack",
                    version="draft",
                    actor="author",
                    output=str(source),
                    stdout=errors,
                )
            self.assertEqual(json.loads(errors.getvalue())["diagnostics"][0]["code"], "file_error")
            self.assertEqual(source.read_bytes(), before)
            source.write_bytes(b"x" * (8 * 1024 * 1024 + 1))
            errors = StringIO()
            with self.assertRaises(CommandError):
                call_command(
                    "import_draft_pack", str(source), new=True, actor="author", stdout=errors
                )
            self.assertEqual(json.loads(errors.getvalue())["diagnostics"][0]["code"], "size_limit")


class DraftPackCommandEntrypointTests(TransactionTestCase):
    def test_cli_huge_integer_is_one_safe_json_error(self) -> None:
        # run_from_argv closes all connections. TestCase's class-wide atomic block
        # cannot survive that real CLI teardown; use committed transaction fixtures.
        User.objects.create_superuser("author", password="unused")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "pack.json"
            source.write_text('{"format_version":' + "9" * 5000 + "}")
            output = StringIO()
            errors = StringIO()
            command = type(load_command_class("knowledge", "import_draft_pack"))(
                stdout=output, stderr=errors
            )
            with self.assertRaises(SystemExit) as caught:
                command.run_from_argv(
                    ["manage.py", "import_draft_pack", str(source), "--new", "--actor", "author"]
                )
            self.assertNotEqual(caught.exception.code, 0)
            self.assertNotIn("Traceback", errors.getvalue())
            result = json.loads(output.getvalue())
            self.assertEqual(result["diagnostics"][0]["code"], "invalid_json")
            self.assertEqual(len(result["diagnostics"]), 1)
            self.assertNotIn("Traceback", output.getvalue())
            self.assertNotIn("9999999999", output.getvalue())
        # Real CLI teardown must not poison later database work in the test process.
        self.assertTrue(User.objects.filter(username="author").exists())


class DraftPackConcurrencyTests(TransactionTestCase):
    def setUp(self) -> None:
        self.actor = User.objects.create_superuser("author", password="unused")
        import_draft_pack(pack(), actor=self.actor)
        self.data = export_draft_pack("draft", actor=self.actor)

    def held(self, operation: Callable[[], object], attempted: Callable[[], None]) -> None:
        ready, release = threading.Event(), threading.Event()
        errors = []

        def worker() -> None:
            close_old_connections()
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '2s'")
                        cursor.execute("SET LOCAL statement_timeout = '4s'")
                    operation()
                    ready.set()
                    if not release.wait(5):
                        raise AssertionError("Main test failed to release writer")
            except BaseException as exc:
                errors.append(exc)
                ready.set()
            finally:
                close_old_connections()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            self.assertTrue(ready.wait(5))
            self.assertFalse(errors, errors)
            start = time.monotonic()
            attempted()
            self.assertLess(time.monotonic() - start, 3)
        finally:
            release.set()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors, errors)

    def concurrent_import(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SHOW lock_timeout")
            before = cursor.fetchone()[0]
        with self.assertRaises(DraftPackError) as caught:
            import_draft_pack(self.data, actor=self.actor, target_version="draft")
        self.assertEqual(caught.exception.diagnostics[0].code, "concurrent_edit")
        with connection.cursor() as cursor:
            cursor.execute("SHOW lock_timeout")
            self.assertEqual(cursor.fetchone()[0], before)

    def test_new_draft_fk_targets_are_bounded_through_real_outer_commit(self) -> None:
        for target in (m.Procedure, User):
            for nested in (False, True):
                with self.subTest(target=target, nested=nested):
                    data = pack()
                    data["version"]["semantic_id"] = "new-draft"
                    data["catalog"]["authorities"] = [
                        {"semantic_id": "no-leak", "name_ar": "بحث", "name_en": "No leak"}
                    ]

                    def attempted(data: Any = data, nested: bool = nested) -> None:
                        with connection.cursor() as cursor:
                            cursor.execute("SHOW lock_timeout")
                            before = cursor.fetchone()[0]
                        with self.assertRaises(DraftPackError) as caught:
                            if nested:
                                with transaction.atomic():
                                    import_draft_pack(data, actor=self.actor)
                            else:
                                import_draft_pack(data, actor=self.actor)
                        self.assertEqual(caught.exception.diagnostics[0].code, "concurrent_edit")
                        with connection.cursor() as cursor:
                            cursor.execute("SHOW lock_timeout")
                            self.assertEqual(cursor.fetchone()[0], before)
                        self.assertFalse(
                            m.ProcedureVersion.objects.filter(semantic_id="new-draft").exists()
                        )
                        self.assertFalse(m.Authority.objects.filter(semantic_id="no-leak").exists())
                        self.assertEqual(m.DraftPackImportReceipt.objects.count(), 1)

                    def lock_target(target: Any = target) -> object:
                        return target.objects.select_for_update().get()

                    self.held(lock_target, attempted)
                    # Successful path actually commits too, and releases SET LOCAL.
                    if nested:
                        with transaction.atomic():
                            import_draft_pack(data, actor=self.actor)
                    else:
                        import_draft_pack(data, actor=self.actor)
                    self.assertTrue(
                        m.ProcedureVersion.objects.filter(semantic_id="new-draft").exists()
                    )
                    # Use a distinct identity on the next iteration.
                    m.ProcedureVersion.objects.filter(semantic_id="new-draft").delete()
                    m.Authority.objects.filter(semantic_id="no-leak").delete()

    def test_nested_import_fk_locks_survive_timeout_restore_until_commit(self) -> None:
        data = pack()
        data["version"]["semantic_id"] = "nested-draft"

        def imported() -> None:
            with connection.cursor() as cursor:
                cursor.execute("SHOW lock_timeout")
                before = cursor.fetchone()[0]
            import_draft_pack(data, actor=self.actor)
            with connection.cursor() as cursor:
                cursor.execute("SHOW lock_timeout")
                self.assertEqual(cursor.fetchone()[0], before)

        def attempted() -> None:
            for model in (m.Procedure, User):
                with self.assertRaises(DatabaseError):
                    with transaction.atomic():
                        model.objects.select_for_update(nowait=True).get()

        self.held(imported, attempted)
        self.assertTrue(m.ProcedureVersion.objects.filter(semantic_id="nested-draft").exists())
        self.assertEqual(m.DraftPackImportReceipt.objects.count(), 2)

    def test_ordinary_child_insert_is_not_an_invisible_phantom(self) -> None:
        self.held(
            lambda: m.Warning.objects.create(
                procedure_version=m.ProcedureVersion.objects.get(),
                **claim("writer"),
                kind="product",
            ),
            self.concurrent_import,
        )

    def test_ordinary_shared_update_is_retryable(self) -> None:
        self.held(
            lambda: m.FactDefinition.objects.filter(key="synthetic_ready").update(minimum=None),
            self.concurrent_import,
        )

    def test_publisher_style_version_row_lock_does_not_deadlock(self) -> None:
        self.held(
            lambda: m.ProcedureVersion.objects.select_for_update().get(), self.concurrent_import
        )

    def test_procedure_row_lock_is_nowait_too(self) -> None:
        self.held(lambda: m.Procedure.objects.select_for_update().get(), self.concurrent_import)

    def test_import_table_lock_excludes_an_ordinary_child_writer(self) -> None:
        def lock_tables() -> None:
            with locked_snapshot():
                pass  # Locks survive this savepoint until held() releases the outer tx.

        def attempted() -> None:
            with self.assertRaises(DatabaseError):
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '200ms'")
                    m.Warning.objects.create(
                        procedure_version=m.ProcedureVersion.objects.get(),
                        **claim("blocked-writer"),
                        kind="product",
                    )
            self.assertFalse(m.Warning.objects.filter(semantic_id="blocked-writer").exists())

        self.held(lock_tables, attempted)

    def test_export_rejects_inflight_writer_instead_of_mixed_snapshot(self) -> None:
        def attempted() -> None:
            with self.assertRaises(DraftPackError) as caught:
                export_draft_pack("draft", actor=self.actor)
            self.assertEqual(caught.exception.diagnostics[0].code, "concurrent_edit")

        self.held(lambda: m.Service.objects.update(text_en="Writer"), attempted)
