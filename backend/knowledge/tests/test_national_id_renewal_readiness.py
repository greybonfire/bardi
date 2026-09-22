"""Reusable additions to the researched draft, never an alternative importer."""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path
from typing import Any, cast

from api.application import project_result
from bardi.settings.base import PROCEDURE_VERSION_PUBLICATION_GATES
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from planning import InvalidResult, PlanningInput, PlanResult, plan_stateless

from knowledge.domain import load_knowledge_snapshot
from knowledge.draft_packs import export_draft_pack, import_draft_pack
from knowledge.draft_packs.errors import DraftPackError
from knowledge.draft_packs.schema import Scenario, parse_draft_pack
from knowledge.draft_packs.state import LOCK_MODELS
from knowledge.draft_preview import check_draft_publication, preview_draft_scenario
from knowledge.importers.national_id_renewal import VERSION_ID, import_national_id_renewal
from knowledge.models import ProcedureVersion
from knowledge.planning_scenarios import PlanningScenario, _observed_result, _run_stored_scenarios
from knowledge.publication import PublicationContext

ARTIFACT = (
    Path(__file__).resolve().parents[3]
    / "docs/draft-packs/scenarios/national-id-renewal-readiness.json"
)


@override_settings(
    PROCEDURE_VERSION_PUBLICATION_GATES=PROCEDURE_VERSION_PUBLICATION_GATES,
    PLANNING_SCENARIOS_REQUIRED=True,
    SELECTION_QUESTIONS_REQUIRED=True,
    PROCEDURE_VERSION_REVIEW_MODE="solo",
)
class NationalIdRenewalReadinessTests(TestCase):
    author: User
    operator: User
    version: ProcedureVersion
    additions: list[dict[str, Any]]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.author = User.objects.create_user("readiness-author", is_staff=True)
        cls.operator = User.objects.create_superuser("readiness-operator", password="unused")
        cls.version = import_national_id_renewal(author=cls.author)
        cls.additions = json.loads(ARTIFACT.read_text())

    def assembled(self) -> dict[str, Any]:
        """Start from a real export; equal rows are reusable, conflicts stop."""
        pack = export_draft_pack(VERSION_ID, actor=self.operator)
        existing = {row["name"]: row for row in pack["scenarios"]}
        for row in self.additions:
            if row["name"] in existing:
                if existing[row["name"]] != row:
                    raise ValueError(f"Scenario conflict: {row['name']}")
            else:
                pack["scenarios"].append(copy.deepcopy(row))
        return pack

    def apply(self, pack: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return import_draft_pack(pack, actor=self.operator, target_version=VERSION_ID, **kwargs)

    def state(self) -> dict[str, Any]:
        return {
            model._meta.label: list(model.objects.order_by("pk").values()) for model in LOCK_MODELS
        }

    def test_native_additions_roundtrip_preserves_every_other_row_and_retry_contract(self) -> None:
        self.assertEqual(len(self.additions), 21)
        self.assertEqual(len({row["name"] for row in self.additions}), 21)
        for row in self.additions:
            self.assertTrue(row["name"].startswith("nid.readiness."))
            Scenario.model_validate(row)
            PlanningScenario(procedure_version=self.version, **row).clean()
        before = self.state()
        baseline = before["knowledge.PlanningScenario"]
        self.assertEqual(len(baseline), 14)
        pack = self.assembled()
        parse_draft_pack(pack)
        self.assertEqual(self.apply(pack, dry_run=True)["status"], "dry_run")
        self.assertEqual(self.state(), before)
        self.assertEqual(self.apply(pack)["status"], "written")
        after = self.state()
        for label, rows in before.items():
            if label not in {"knowledge.PlanningScenario", "knowledge.DraftPackImportReceipt"}:
                self.assertEqual(after[label], rows, label)
        self.assertEqual(
            [
                row
                for row in after["knowledge.PlanningScenario"]
                if row["id"] in {r["id"] for r in baseline}
            ],
            baseline,
        )
        self.assertEqual(len(after["knowledge.PlanningScenario"]), 35)
        self.assertEqual(len(after["knowledge.DraftPackImportReceipt"]), 1)
        self.assertEqual(self.apply(pack)["status"], "noop")
        self.assertEqual(self.state(), after)
        self.assertEqual(len(self.assembled()["scenarios"]), 35)
        changed = copy.deepcopy(pack)
        changed["scenarios"][-1]["evaluation_context"]["locale"] = "ar"
        with self.assertRaises(DraftPackError) as caught:
            self.apply(changed)
        self.assertIn("stale_revision", {d.code for d in caught.exception.diagnostics})
        self.additions[0]["evaluation_context"]["locale"] = "ar"
        with self.assertRaisesMessage(ValueError, "Scenario conflict"):
            self.assembled()
        with self.assertRaisesMessage(ValidationError, "semantic conflict in scenarios"):
            import_national_id_renewal(author=self.author)
        self.assertEqual(self.state(), after)

    def test_all_previews_and_readiness_are_read_only_and_honest(self) -> None:
        self.apply(self.assembled())
        before = self.state()
        for scenario in PlanningScenario.objects.filter(procedure_version=self.version):
            with self.subTest(name=scenario.name):
                preview = preview_draft_scenario(self.version.pk, scenario.pk, actor=self.operator)
                self.assertEqual(preview.diagnostics, ())
                self.assertFalse(preview.stale)
                self.assertTrue(
                    preview.matches_expectations,
                    _observed_result(preview.result) if preview.result is not None else None,
                )
                if isinstance(preview.result, PlanResult):
                    result = preview.result
                    self.assertNotIn(
                        "nid.requirement.previous_card", [i.id for i in result.checklist_items]
                    )
                    self.assertEqual(result.dependencies, ())
                    self.assertEqual(result.routing.status, "unresolved")
                    self.assertEqual(result.routing.destinations, ())
                    self.assertEqual(result.routing.verification_sources, ())
                    self.assertEqual([fee.id for fee in result.fees], ["nid.fee.ordinary"])
                    fee = result.fees[0]
                    self.assertEqual(fee.value_state, "unknown")
                    self.assertEqual(
                        (fee.amount, fee.minimum_amount, fee.maximum_amount), (None, None, None)
                    )
                    self.assertTrue(fee.current_value_unknown)
                    if scenario.name == "nid.readiness.without_residence":
                        ar, en = (project_result(result, locale) for locale in ("ar", "en"))
                        self.assertEqual(ar["procedure_version_id"], en["procedure_version_id"])
                        self.assertNotEqual(ar["title"], en["title"])
                        self.assertEqual(ar["routing"], en["routing"])
                        self.assertEqual(ar["inconclusive_sections"], en["inconclusive_sections"])
                        for projection in (ar, en):
                            fees = cast(list[dict[str, Any]], projection["fees"])
                            self.assertEqual([fee["id"] for fee in fees], ["nid.fee.ordinary"])
                            self.assertEqual(fees[0]["value_state"], "unknown")
                            self.assertTrue(fees[0]["current_value_unknown"])
                            for field in ("amount", "minimum_amount", "maximum_amount"):
                                self.assertIsNone(fees[0][field])
                            checklist = cast(list[dict[str, Any]], projection["checklist_items"])
                            self.assertEqual(
                                [item["id"] for item in checklist],
                                ["nid.requirement.renew_after_expiry"],
                            )
        readiness = check_draft_publication(self.version.pk, actor=self.operator)
        self.assertEqual(readiness.diagnostics, ())
        with override_settings(PROCEDURE_VERSION_REVIEW_MODE="independent"):
            independent = check_draft_publication(self.version.pk, actor=self.operator)
        self.assertEqual(
            [item.code for item in independent.diagnostics], ["missing_review_approval"] * 4
        )
        self.assertEqual(self.state(), before)

    def test_derived_input_is_rejected_by_runtime_model_and_transport(self) -> None:
        row = copy.deepcopy(self.additions[0])
        row["source_facts"] = {"renewal_deadline_passed": True}
        with self.assertRaisesMessage(ValidationError, "defined source Facts only"):
            PlanningScenario(procedure_version=self.version, **row).clean()
        pack = self.assembled()
        pack["scenarios"].append({**row, "name": "nid.readiness.forbidden"})
        with self.assertRaises(DraftPackError):
            self.apply(pack)
        result = plan_stateless(
            load_knowledge_snapshot(),
            PlanningInput("get_egyptian_national_id", row["source_facts"], "en", date(2026, 8, 26)),
        )
        self.assertIsInstance(result, InvalidResult)
        assert isinstance(result, InvalidResult)
        self.assertEqual([d.code for d in result.diagnostics], ["derived_fact_cannot_be_submitted"])

    def test_stateless_corrections_do_not_retain_invalid_or_contradictory_answers(self) -> None:
        self.apply(self.assembled())
        common = next(
            row["source_facts"]
            for row in self.additions
            if row["name"].endswith("freshness_sep_24")
        )
        cases = [
            ({**common, "national_id_expiry_date": None}, "invalid", None),
            (
                {k: v for k, v in common.items() if k != "national_id_expiry_date"},
                "next_question",
                "q.nid.expiry_date",
            ),
            (common, "plan", None),
            ({**common, "national_id_possession_state": "none"}, "invalid", None),
            (
                {
                    k: v
                    for k, v in {**common, "national_id_possession_state": "none"}.items()
                    if k != "national_id_expiry_date"
                },
                "inconclusive",
                "no_matching_researched_procedure",
            ),
            (common, "plan", None),
        ]
        # Transient copies exercise the same stateless planner without changing authored rows.
        before = self.state()
        row = PlanningScenario.objects.get(name="nid.readiness.null_date")
        context = PublicationContext(self.version, self.operator, {})
        for facts, family, identifier in cases:
            row.source_facts = facts
            results, failures = _run_stored_scenarios(context, (row,))
            self.assertEqual(failures, ())
            observed, ids, diagnostics = _observed_result(results[row.pk])
            self.assertEqual(observed, family)
            if identifier:
                self.assertIn(identifier, ids.values())
            if (
                facts.get("national_id_possession_state") == "none"
                and "national_id_expiry_date" in facts
            ):
                self.assertEqual(diagnostics, ["contradictory_facts", "contradictory_facts"])
            elif family == "invalid":
                self.assertEqual(diagnostics, ["invalid_fact_value"])
        self.assertEqual(self.state(), before)
