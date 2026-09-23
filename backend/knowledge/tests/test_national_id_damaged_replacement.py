"""Disposable simulated editor review, NOT human review or fresh source verification.

No fixture publishes persistent data. Renewal's 35 authored cases are checked one by
one before ordinary saves; no direct signature writes or importer seal bypasses.
"""

from __future__ import annotations

import copy
import json
from datetime import date
from itertools import product
from pathlib import Path
from typing import Any

from api.application import execute_planning, project_result
from bardi.settings.base import PROCEDURE_VERSION_PUBLICATION_GATES
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from planning import PlanningInput, PlanResult, plan_stateless
from planning.case_preparation import (
    CasePreparationInvalid,
    CasePreparationSuccess,
    prepare_case,
)
from planning.evaluator import TruthValue, evaluate
from planning.facts import FactValue

from knowledge.draft_packs import export_draft_pack, import_draft_pack
from knowledge.draft_packs.errors import DraftPackError
from knowledge.draft_packs.schema import parse_draft_pack
from knowledge.draft_packs.state import LOCK_MODELS
from knowledge.draft_preview import check_draft_publication, preview_draft_scenario
from knowledge.evidence_workflow_temporal import load_knowledge_snapshot_as_of
from knowledge.importers.national_id_renewal import import_national_id_renewal
from knowledge.models import (
    EvidenceLink,
    FactDefinition,
    Procedure,
    ProcedureVersion,
    Service,
    ServiceProcedureCandidate,
    ServiceQuestion,
    Warning,
)
from knowledge.planning_scenarios import (
    _observed_result,
    _run_stored_scenarios,
    _scenario_matches,
)
from knowledge.publication import PublicationContext, publish_procedure_version
from knowledge.services import save_candidate, set_question_resolved_facts

ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "docs/draft-packs/examples/national-id-damaged-replacement.json"
SETUP = ROOT / "docs/evidence-packs/national-id-damaged-replacement/setup.json"
ADDITIONS = ROOT / "docs/draft-packs/scenarios/national-id-renewal-readiness.json"
KEY = "card_expires_after_evaluation_date"
CARD = "nid.damaged.warning.card"
RECHECK = "nid.damaged.warning.recheck"
DAY = date(2026, 9, 22)
DAMAGED_PROCEDURE = "ordinary_domestic_national_id_damaged_replacement"
# Independent approved-content oracle: never derive expected text from the artifact.
APPROVED_WARNINGS = {
    CARD: {
        "ar": (
            "تذكر إرشادات خدمات مصر لاستخراج بدل تالف لبطاقة الرقم القومي "
            "«بطاقة الرقم القومي التالفة»."
        ),
        "en": (
            "Khadamat Misr's damaged National ID replacement guidance lists "
            "the damaged National ID card."
        ),
        "kind": "administrative",
        "severity": "info",
        "role": "general",
    },
    RECHECK: {
        "ar": (
            "هذه إرشادات بحثية غير مكتملة. خلو قائمة المستندات لا يعني عدم وجود متطلبات. "
            "لم يُحسم انطباق مستند الزواج أو استحقاق استخدام القناة التي شملها البحث؛ "
            "الرسوم والخطوات والمكتب والمدة غير معروفة. أعد التحقق قبل التصرف. "
            "لا تغطي هذه المسودة اجتماع التلف مع انتهاء الصلاحية أو تغيير البيانات."
        ),
        "en": (
            "Incomplete research guidance. An empty checklist does not mean there are no "
            "requirements. Marriage-document applicability and entitlement to the researched "
            "channel remain unresolved; fees, steps, office and turnaround are unknown. "
            "Recheck before acting. This draft does not cover damage combined with expiry "
            "or data changes."
        ),
        "kind": "product",
        "severity": "important",
        "role": "regeneration",
    },
}
RENEWAL_CASE_NAMES = frozenset(
    """
    nid.contradictory.no_card_with_expiry
    nid.edge.deadline_exact_three_calendar_months nid.edge.deadline_month_end_clamping
    nid.edge.not_yet_expired nid.locale.ar nid.negative.damaged_card
    nid.negative.data_change nid.negative.first_issuance nid.negative.lost_card
    nid.negative.outside_egypt nid.positive.expired_held_no_changes
    nid.readiness.change_marital_status nid.readiness.change_multiple
    nid.readiness.change_other nid.readiness.change_profession
    nid.readiness.clamped_deadline_equal nid.readiness.clamped_deadline_passed
    nid.readiness.damaged_with_change nid.readiness.deadline_next_day
    nid.readiness.empty nid.readiness.expiry_equal nid.readiness.expiry_previous_day
    nid.readiness.freshness_sep_24 nid.readiness.freshness_sep_25
    nid.readiness.freshness_sep_26 nid.readiness.impossible_date
    nid.readiness.invalid_enum nid.readiness.lost_with_change
    nid.readiness.noncanonical_date nid.readiness.null_date
    nid.readiness.without_district nid.readiness.without_residence
    nid.unknown.data_change nid.unknown.expiry_date nid.unknown.possession_state
""".split()
)


@override_settings(
    PROCEDURE_VERSION_PUBLICATION_GATES=PROCEDURE_VERSION_PUBLICATION_GATES,
    PLANNING_SCENARIOS_REQUIRED=True,
    SELECTION_QUESTIONS_REQUIRED=True,
    PROCEDURE_VERSION_REVIEW_MODE="solo",
)
class DamagedReplacementTests(TestCase):
    def setUp(self) -> None:
        self.actor = User.objects.create_superuser("damaged-editor", password="unused")
        self.renewal = import_national_id_renewal(author=self.actor)
        self.assertEqual(self.renewal.planning_scenarios.count(), 14)
        renewal_pack = export_draft_pack(self.renewal.semantic_id, actor=self.actor)
        renewal_pack["scenarios"].extend(json.loads(ADDITIONS.read_text()))
        import_draft_pack(renewal_pack, actor=self.actor, target_version=self.renewal.semantic_id)
        self.original_renewal = export_draft_pack(self.renewal.semantic_id, actor=self.actor)
        self.assertEqual(len(self.original_renewal["scenarios"]), 35)
        self.old_questions = list(ServiceQuestion.objects.order_by("pk").values())
        self.old_candidates = list(ServiceProcedureCandidate.objects.order_by("pk").values())
        self.pack = json.loads(PACK.read_text())
        self.setup_spec = json.loads(SETUP.read_text())
        # Native supported operations, separate from the generic transport.
        self.fact = FactDefinition(**self.setup_spec["fact"])
        self.fact.full_clean()
        self.fact.save()
        service = Service.objects.get(semantic_id=self.setup_spec["service"])
        procedure_data = dict(self.setup_spec["procedure"])
        procedure_data.pop("primary_service")
        procedure = Procedure(primary_service=service, **procedure_data)
        procedure.full_clean()
        procedure.save()
        question_data = dict(self.setup_spec["question"])
        resolved = question_data.pop("resolves_facts")
        question_data["fact"] = FactDefinition.objects.get(key=question_data["fact"])
        question = ServiceQuestion(service=service, **question_data)
        question.full_clean()
        question.save()
        set_question_resolved_facts(
            question, tuple(FactDefinition.objects.get(key=k) for k in resolved)
        )
        save_candidate(
            ServiceProcedureCandidate(
                service=service,
                procedure=procedure,
                selection_predicate=self.setup_spec["candidate"]["selection_predicate"],
            )
        )

    def state(self) -> dict[str, Any]:
        return {m._meta.label: list(m.objects.order_by("pk").values()) for m in LOCK_MODELS}

    def install(self) -> ProcedureVersion:
        import_draft_pack(self.pack, actor=self.actor)
        return ProcedureVersion.objects.get(semantic_id=self.pack["version"]["semantic_id"])

    def review(self, version: ProcedureVersion, *, damaged_reason: str | None = None) -> None:
        """Simulate an editor checking each case, then resaving normally (test only)."""
        for row in version.planning_scenarios.order_by("name"):
            if row.name == "nid.negative.damaged_card" and damaged_reason is not None:
                row.expected_identifiers = {"reason": damaged_reason}
            results, failures = _run_stored_scenarios(
                PublicationContext(version, self.actor, {}), (row,)
            )
            self.assertEqual(failures, (), row.name)
            self.assertTrue(
                _scenario_matches(row, results[row.pk]),
                (row.name, _observed_result(results[row.pk])),
            )
            row.save()

    def publish_catalog(self) -> ProcedureVersion:
        version = self.install()
        # ONLY this compatible optional Fact and these two named evidence objects.
        self.fact.is_published = True
        self.fact.save()
        # With only the Fact published, unverified administrative text stays absent.
        before = self.state()
        preview = preview_draft_scenario(
            version.pk,
            version.planning_scenarios.get(name="nid.damaged.positive").pk,
            actor=self.actor,
        )
        self.assertEqual(preview.diagnostics, ())
        self.assertTrue(preview.matches_expectations)
        self.assertEqual(self.state(), before)
        for obj in (
            Warning.objects.get(procedure_version=version, semantic_id=CARD),
            EvidenceLink.objects.get(
                warning__procedure_version=version, semantic_id="EL-NID-DAMAGED-S10"
            ),
        ):
            obj.verification_state = "current"
            obj.verified_on = DAY
            obj.reverify_on = date(2026, 10, 22)
            obj.full_clean()
            obj.save()
        for name in ("nid.damaged.positive", "nid.damaged.tomorrow"):
            row = version.planning_scenarios.get(name=name)
            row.expected_identifiers["warning_ids"] = [CARD, RECHECK]
            # Check changed expectation BEFORE ordinary save, like every reviewed case.
            results, failures = _run_stored_scenarios(
                PublicationContext(version, self.actor, {}), (row,)
            )
            self.assertEqual(failures, ())
            self.assertTrue(
                _scenario_matches(row, results[row.pk]), _observed_result(results[row.pk])
            )
            row.save()
        self.review(version)
        publish_procedure_version(version.pk, actor=self.actor)
        self.review(self.renewal, damaged_reason="not_yet_effective")
        publish_procedure_version(self.renewal.pk, actor=self.actor)
        return version

    def test_import_preserves_catalog_and_all_35_renewal_cases_and_trust(self) -> None:
        parse_draft_pack(self.pack)
        with self.assertRaises(DraftPackError):
            parse_draft_pack(self.setup_spec)
        before = self.state()
        self.assertEqual(
            import_draft_pack(self.pack, actor=self.actor, dry_run=True)["status"], "dry_run"
        )
        self.assertEqual(self.state(), before)
        version = self.install()
        after = self.state()
        imported = export_draft_pack(version.semantic_id, actor=self.actor)
        for pack in (self.pack, imported):
            self.assertEqual(len(pack["warnings"]), 2)
            for warning in pack["warnings"]:
                expected = APPROVED_WARNINGS[warning["semantic_id"]]
                for locale in ("ar", "en"):
                    self.assertEqual(warning["text_" + locale], expected[locale])
                for field in ("kind", "severity", "role"):
                    self.assertEqual(warning[field], expected[field])
                self.assertEqual(warning.get("applicability", {}), {})
            (link,) = pack["evidence_links"]
            self.assertEqual(link["owner"], {"kind": "warning", "semantic_id": CARD})
            self.assertEqual(link["passage"], "بطاقة الرقم القومي التالفة")
            self.assertEqual(link["retrieved_on"], "2026-09-12")
            self.assertEqual(link["sources"], ["nid.damaged.source.s10"])
            self.assertEqual(
                link["location"],
                "S10 required-documents anchor; PR147 C-N-08, not a full response transcription.",
            )
            self.assertEqual(
                link["applicability_context"],
                "Khadamat Misr channel only. Preserved PR147 head "
                "dd0d8cda84a7bda55871836e477341594755f300; attributed retrieval 2026-09-12, "
                "no fresh verification. D03 marriage applicability, G02 complete checklist/channel "
                "and G07 combined transactions unresolved. No quantities, copies, originals "
                "or surrender inferred.",
            )
            source = next(
                s
                for s in pack["catalog"]["sources"]
                if s["semantic_id"] == "nid.damaged.source.s10"
            )
            self.assertEqual(source["locator"], "https://www.khadamatmisr.gov.eg/node/64")
            self.assertEqual(source["classification"], "official")
            self.assertEqual(source["retrieved_on"], "2026-09-12")
        self.assertEqual(
            Warning.objects.get(procedure_version=version, semantic_id=RECHECK).applicability, {}
        )
        for label, rows in before.items():
            for row in rows:
                self.assertIn(row, after[label], label)
        self.assertEqual(import_draft_pack(self.pack, actor=self.actor)["status"], "noop")
        self.assertEqual(self.state(), after)
        renewed = export_draft_pack(self.renewal.semantic_id, actor=self.actor)
        for key in self.original_renewal:
            if key not in {"base_revision", "service_setup", "catalog"}:
                self.assertEqual(renewed[key], self.original_renewal[key], key)
        for collection, rows in self.original_renewal["catalog"].items():
            for row in rows:
                self.assertIn(row, renewed["catalog"][collection])
        self.assertEqual(
            list(
                ServiceQuestion.objects.filter(pk__in=[r["id"] for r in self.old_questions])
                .order_by("pk")
                .values()
            ),
            self.old_questions,
        )
        self.assertEqual(
            list(
                ServiceProcedureCandidate.objects.filter(
                    pk__in=[r["id"] for r in self.old_candidates]
                )
                .order_by("pk")
                .values()
            ),
            self.old_candidates,
        )
        self.assertEqual(ServiceQuestion.objects.count(), len(self.old_questions) + 1)
        self.assertFalse(FactDefinition.objects.get(key=KEY).is_published)
        self.assertEqual(version.state, "draft")
        unverified: list[Warning | EvidenceLink] = [
            *version.warnings.all(),
            *EvidenceLink.objects.filter(warning__procedure_version=version),
        ]
        for claim in unverified:
            self.assertEqual(claim.verification_state, "unknown")
            self.assertIsNone(claim.verified_on)
        changed = copy.deepcopy(self.pack)
        changed["warnings"][0]["text_en"] += " conflict"
        with self.assertRaises(DraftPackError):
            import_draft_pack(changed, actor=self.actor)
        self.assertEqual(self.state(), after)

    def test_atomic_failure_does_not_leave_partial_owned_or_shared_rows(self) -> None:
        before = self.state()
        broken = copy.deepcopy(self.pack)
        broken["evidence_links"][0]["sources"] = ["missing-source"]
        with self.assertRaises(DraftPackError):
            import_draft_pack(broken, actor=self.actor)
        self.assertEqual(self.state(), before)

    def test_raw_readiness_preview_are_readonly_and_do_not_hide_unpublished_fact(self) -> None:
        version = self.install()
        before = self.state()
        readiness = check_draft_publication(version.pk, actor=self.actor)
        expected_damaged = [
            ("core.applicability", "unsupported_rule_fact:" + KEY, ""),
            ("core.planning_scenarios", "scenario_execution_failed", "nid.damaged.contradictory"),
        ]
        self.assertEqual(
            [(d.gate, d.code, d.detail) for d in readiness.diagnostics], expected_damaged
        )
        renewal_readiness = check_draft_publication(self.renewal.pk, actor=self.actor)
        self.assertEqual(len(RENEWAL_CASE_NAMES), 35)
        self.assertEqual(
            [(d.gate, d.code, d.detail) for d in renewal_readiness.diagnostics],
            [
                ("core.planning_scenarios", "scenario_stale_after_semantic_change", name)
                for name in sorted(RENEWAL_CASE_NAMES)
            ],
        )
        preview = preview_draft_scenario(
            version.pk,
            version.planning_scenarios.get(name="nid.damaged.positive").pk,
            actor=self.actor,
        )
        self.assertIsNone(preview.result)
        self.assertEqual([d.code for d in preview.diagnostics], ["scenario_execution_failed"])
        old_preview = preview_draft_scenario(
            self.renewal.pk,
            self.renewal.planning_scenarios.get(name="nid.positive.expired_held_no_changes").pk,
            actor=self.actor,
        )
        self.assertTrue(old_preview.stale)
        self.assertEqual(self.state(), before)
        # Existing cases are reviewed explicitly, not silently resealed by the pack.
        self.review(self.renewal, damaged_reason="no_published_version")
        current = export_draft_pack(self.renewal.semantic_id, actor=self.actor)["scenarios"]
        expected = copy.deepcopy(self.original_renewal["scenarios"])
        for row in expected:
            if row["name"] == "nid.negative.damaged_card":
                row["expected_identifiers"] = {"reason": "no_published_version"}
        self.assertEqual(current, expected)
        before = self.state()
        self.assertEqual(check_draft_publication(self.renewal.pk, actor=self.actor).diagnostics, ())
        self.assertEqual(
            [
                (d.gate, d.code, d.detail)
                for d in check_draft_publication(version.pk, actor=self.actor).diagnostics
            ],
            expected_damaged,
        )
        self.assertEqual(self.state(), before)
        self.renewal.refresh_from_db()
        version.refresh_from_db()
        self.assertEqual((self.renewal.state, version.state), ("draft", "draft"))

    def test_canonical_publication_bilingual_partial_plan_and_all_stored_cases(self) -> None:
        version = self.publish_catalog()
        before = self.state()
        snapshot = load_knowledge_snapshot_as_of(DAY)
        service = next(s for s in snapshot.services if s.semantic_id == "get_egyptian_national_id")
        self.assertEqual(len(service.candidates), 2)
        domains = (
            ("held", "lost", "damaged", "none"),
            ("inside_egypt", "outside_egypt"),
            ("none", "residence", "profession", "marital_status", "other", "multiple"),
        )
        keys = (
            "national_id_possession_state",
            "application_location",
            "national_id_data_change_kind",
        )
        for key, domain in zip(keys, domains, strict=True):
            self.assertEqual(snapshot.fact_definitions[key].enum_values, domain)
        matrix_count = valid_count = contradictory_count = renewal_true_count = 0
        renewal_procedure = "ordinary_domestic_national_id_renewal"
        positive_renewal_control = False
        for possession, location, change, citizenship, expiry in product(
            *domains,
            (None, "egyptian", "other"),
            (None, date(2026, 9, 21), DAY, date(2026, 9, 23)),
        ):
            values: dict[str, FactValue] = dict(
                zip(keys, (possession, location, change), strict=True)
            )
            if citizenship is not None:
                values["citizenship"] = citizenship
            if expiry is not None:
                values["national_id_expiry_date"] = expiry
            matrix_count += 1
            with self.subTest(values=values):
                outcome = prepare_case(snapshot.fact_definitions, service, values, DAY)
                if possession == "none" and expiry is not None:
                    self.assertIsInstance(outcome, CasePreparationInvalid)
                    assert isinstance(outcome, CasePreparationInvalid)
                    self.assertEqual(
                        [(d.code, d.path) for d in outcome.diagnostics],
                        [
                            ("contradictory_facts", ("facts", key))
                            for key in ("national_id_expiry_date", "national_id_possession_state")
                        ],
                    )
                    contradictory_count += 1
                    continue
                self.assertIsInstance(outcome, CasePreparationSuccess)
                assert isinstance(outcome, CasePreparationSuccess)
                valid_count += 1
                prepared = outcome.prepared_facts
                selected = {
                    candidate.procedure_semantic_id
                    for candidate in service.candidates
                    if evaluate(
                        candidate.selection_predicate,
                        prepared.values,
                        submitted_keys=prepared.submitted_keys,
                    ).value
                    is TruthValue.TRUE
                }
                self.assertLessEqual(len(selected), 1)
                self.assertEqual(
                    renewal_procedure in selected,
                    possession == "held"
                    and location == "inside_egypt"
                    and change == "none"
                    and expiry is not None
                    and expiry < DAY,
                )
                self.assertEqual(
                    DAMAGED_PROCEDURE in selected,
                    possession == "damaged" and location == "inside_egypt" and change == "none",
                )
                renewal_true_count += renewal_procedure in selected
                if (
                    possession == "held"
                    and location == "inside_egypt"
                    and change == "none"
                    and citizenship is None
                    and expiry == date(2026, 9, 21)
                ):
                    self.assertEqual(selected, {renewal_procedure})
                    positive_renewal_control = True
        self.assertEqual(matrix_count, 576)
        self.assertEqual((valid_count, contradictory_count), (468, 108))
        self.assertTrue(positive_renewal_control)
        self.assertGreater(renewal_true_count, 0)
        self.assertEqual(renewal_true_count, 3)
        for row in version.planning_scenarios.all():
            facts = dict(row.source_facts)
            if isinstance(facts.get("national_id_expiry_date"), str):
                facts["national_id_expiry_date"] = date.fromisoformat(
                    facts["national_id_expiry_date"]
                )
            result = plan_stateless(
                load_knowledge_snapshot_as_of(DAY),
                PlanningInput(self.setup_spec["service"], facts, "en", DAY),
            )
            self.assertTrue(_scenario_matches(row, result), (row.name, _observed_result(result)))
            if row.name == "nid.damaged.positive":
                assert isinstance(result, PlanResult)
                ar, en = (project_result(result, locale) for locale in ("ar", "en"))
                self.assertNotEqual(ar["title"], en["title"])
                for projection in (ar, en):
                    self.assertEqual(projection["checklist_items"], [])
                    self.assertEqual(projection["steps"], [])
                    self.assertEqual(projection["fees"], [])
                self.assertEqual(result.dependencies, ())
                self.assertEqual(result.routing.status, "unresolved")
                self.assertEqual([w.id for w in result.warnings], [CARD, RECHECK])
                for locale in ("ar", "en"):
                    projection = project_result(result, locale)
                    self.assertEqual(
                        projection["routing"],
                        {"status": "unresolved", "destinations": [], "verification_sources": []},
                    )
                    projected_warnings = projection["warnings"]
                    assert isinstance(projected_warnings, list)
                    for warning in projected_warnings:
                        expected_warning = APPROVED_WARNINGS[warning["id"]]
                        self.assertEqual(warning["text"], expected_warning[locale])
                        self.assertEqual(
                            warning["sources"],
                            [
                                {
                                    "id": "nid.damaged.source.s10",
                                    "authority_id": "authority.khadamat_misr",
                                    "title": "Khadamat Misr — damaged National ID replacement "
                                    "(S10, preserved PR147)",
                                    "locator": "https://www.khadamatmisr.gov.eg/node/64",
                                    "classification": "official",
                                    "retrieved_on": date(2026, 9, 12),
                                }
                            ]
                            if warning["id"] == CARD
                            else [],
                        )
                        for field in ("kind", "severity", "role"):
                            self.assertEqual(warning[field], expected_warning[field])
                    self.assertEqual(
                        execute_planning(
                            PlanningInput(self.setup_spec["service"], facts, locale, DAY),
                            snapshot_loader=lambda: load_knowledge_snapshot_as_of(DAY),
                        ),
                        project_result(result, locale),
                    )
        self.assertEqual(self.state(), before)
        final = export_draft_pack(self.renewal.semantic_id, actor=self.actor)["scenarios"]
        expected = copy.deepcopy(self.original_renewal["scenarios"])
        for row in expected:
            if row["name"] == "nid.negative.damaged_card":
                row["expected_identifiers"] = {"reason": "not_yet_effective"}
        self.assertEqual(final, expected)

    def test_stateless_corrections_invalid_derived_and_trust_fallback(self) -> None:
        version = self.publish_catalog()
        common = dict(version.planning_scenarios.get(name="nid.damaged.positive").source_facts)
        common["national_id_expiry_date"] = date(2027, 1, 1)
        cases = [
            ({**common, "national_id_expiry_date": None}, "invalid", "invalid_fact_value"),
            (common, "plan", None),
            ({**common, KEY: True}, "invalid", "derived_fact_cannot_be_submitted"),
            ({**common, "national_id_possession_state": "none"}, "invalid", "contradictory_facts"),
            (common, "plan", None),
            (
                {
                    **common,
                    "national_id_possession_state": "held",
                    "national_id_expiry_date": date(2026, 5, 1),
                },
                "plan",
                None,
            ),
            (common, "plan", None),
        ]
        for facts, family, diagnostic in cases:
            result = plan_stateless(
                load_knowledge_snapshot_as_of(DAY),
                PlanningInput(self.setup_spec["service"], facts, "en", DAY),
            )
            observed, ids, diagnostics = _observed_result(result)
            self.assertEqual(observed, family)
            if diagnostic:
                self.assertIn(diagnostic, diagnostics)
            elif family == "plan":
                self.assertEqual(
                    ids["procedure_version_id"],
                    self.renewal.semantic_id
                    if facts["national_id_possession_state"] == "held"
                    else version.semantic_id,
                )
        for field, question in (
            ("application_location", "application_location"),
            ("national_id_possession_state", "possession_state"),
            ("national_id_data_change_kind", "data_change_kind"),
            ("national_id_expiry_date", "expiry_date"),
            ("citizenship", "citizenship"),
        ):
            facts = {key: value for key, value in common.items() if key != field}
            result = plan_stateless(
                load_knowledge_snapshot_as_of(DAY),
                PlanningInput(self.setup_spec["service"], facts, "en", DAY),
            )
            self.assertEqual(
                _observed_result(result),
                (
                    "next_question",
                    {
                        "service_id": self.setup_spec["service"],
                        "question_id": "q.nid." + question,
                    },
                    [],
                ),
            )
        result = plan_stateless(
            load_knowledge_snapshot_as_of(date(2026, 10, 23)),
            PlanningInput(self.setup_spec["service"], common, "en", date(2026, 10, 23)),
        )
        assert isinstance(result, PlanResult)
        self.assertEqual([w.id for w in result.warnings], [RECHECK])
        self.assertEqual(result.checklist_items, ())
