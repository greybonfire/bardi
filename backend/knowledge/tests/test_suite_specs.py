"""Database-free tests for the packaged suite manifests, not administrative approval."""

from dataclasses import replace
from unittest import TestCase

from knowledge.importers.suite_specs import load_suite, version_id


class SuiteManifestTests(TestCase):
    def test_catalog_counts_and_order(self) -> None:
        for key, prefix, count in (("passport", "P", 14), ("national_id", "N", 15)):
            suite = load_suite(key)
            self.assertEqual(
                [row.row for row in suite.families],
                [f"{prefix}{index:02}" for index in range(1, count + 1)],
            )

    def test_claim_and_source_coverage(self) -> None:
        passport, national_id = load_suite("passport"), load_suite("national_id")
        self.assertEqual((len(passport.claims), len(national_id.claims)), (35, 17))
        self.assertEqual(
            len({row.id for suite in (passport, national_id) for row in suite.claims}), 50
        )
        self.assertEqual(
            len({row.alias for suite in (passport, national_id) for row in suite.sources}), 25
        )

    def test_no_identity_is_invented_for_six_unresolved_transactions(self) -> None:
        missing = {
            row.row
            for key in ("passport", "national_id")
            for row in load_suite(key).families
            if row.procedure_id is None
        }
        self.assertEqual(missing, {"P07", "P12", "N08", "N09", "N10", "N13"})

    def test_all_drafts_have_unique_dated_ids(self) -> None:
        ids = [
            version_id(suite, family, scope)
            for suite in (load_suite("passport"), load_suite("national_id"))
            for family in suite.families
            for scope in family.scopes
        ]
        self.assertEqual(len(ids), 24)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(len(identity) <= 128 for identity in ids))
        self.assertTrue(all(identity.endswith("research-2026-09-12") for identity in ids))

    def test_all_drafts_retain_open_gates(self) -> None:
        for key in ("passport", "national_id"):
            self.assertTrue(all(family.blockers for family in load_suite(key).families))

    def test_privacy_policy_is_not_attached_to_any_claim(self) -> None:
        suite = load_suite("passport")
        self.assertIn("S23", {source.alias for source in suite.sources})
        self.assertFalse(any("S23" in claim.sources for claim in suite.claims))

    def test_lost_id_old_original_is_a_discrepancy_not_a_requirement(self) -> None:
        suite = load_suite("national_id")
        claim = next(item for item in suite.claims if item.id == "C-N-10")
        self.assertEqual(claim.kind, "note")
        self.assertIn("NOT imported as a document requirement", claim.text_en)

    def test_passport_replacement_and_issuance_fees_remain_distinct(self) -> None:
        suite = load_suite("passport")
        by_row = {family.row: family for family in suite.families}
        self.assertIn("C-P-16", by_row["P02"].scopes[0].claims)
        self.assertNotIn("C-P-17", by_row["P02"].scopes[0].claims)
        for row in ("P03", "P04", "P05"):
            self.assertIn("C-P-17", by_row[row].scopes[0].claims)
            self.assertNotIn("C-P-16", by_row[row].scopes[0].claims)

    def test_dubai_and_london_id_material_are_separate_versions(self) -> None:
        suite = load_suite("national_id")
        row = next(item for item in suite.families if item.row == "N12")
        scopes = {item.key: set(item.claims) for item in row.scopes}
        self.assertIn("C-O-08", scopes["dubai-research"])
        self.assertNotIn("C-O-13", scopes["dubai-research"])
        self.assertIn("C-O-13", scopes["london-research"])
        self.assertNotIn("C-O-08", scopes["london-research"])

    def test_compound_consular_prices_are_not_fabricated_as_one_fee_range(self) -> None:
        suite = load_suite("passport")
        claim = next(item for item in suite.claims if item.id == "C-O-06")
        self.assertEqual(claim.kind, "note")
        self.assertIsNone(claim.amount)

    def test_domestic_and_consular_loss_do_not_share_police_report_rule(self) -> None:
        suite = load_suite("passport")
        families = {item.row: item for item in suite.families}
        self.assertIn("C-P-12", families["P03"].scopes[0].claims)
        self.assertNotIn("C-P-12", families["P04"].scopes[0].claims)
        self.assertNotIn("C-P-12", families["P10"].scopes[0].claims)
        self.assertIn("C-O-03", families["P10"].scopes[0].claims)

    def test_fingerprint_is_deterministic_and_content_sensitive(self) -> None:
        suite = load_suite("passport")
        self.assertEqual(suite.fingerprint, load_suite("passport").fingerprint)
        changed = replace(suite, service_en="Edited")
        self.assertNotEqual(suite.fingerprint, changed.fingerprint)

    def test_duplicate_claims_are_rejected(self) -> None:
        suite = load_suite("passport")
        with self.assertRaises(ValueError):
            replace(suite, claims=suite.claims + (suite.claims[0],)).validate()

    def test_dangling_source_reference_is_rejected(self) -> None:
        suite = load_suite("passport")
        bad = replace(suite.claims[0], sources=("S99",))
        with self.assertRaises(ValueError):
            replace(suite, claims=(bad,) + suite.claims[1:]).validate()

    def test_dangling_claim_reference_is_rejected(self) -> None:
        suite = load_suite("passport")
        first = suite.families[0]
        bad = replace(first.scopes[0], claims=("C-P-99",))
        with self.assertRaises(ValueError):
            replace(
                suite, families=(replace(first, scopes=(bad,)),) + suite.families[1:]
            ).validate()

    def test_missing_catalog_row_is_rejected(self) -> None:
        suite = load_suite("national_id")
        with self.assertRaises(ValueError):
            replace(suite, families=suite.families[:-1]).validate()

    def test_credentials_in_source_locator_are_rejected(self) -> None:
        suite = load_suite("passport")
        bad = replace(suite.sources[0], locator="https://user:password@example.invalid/source")
        with self.assertRaises(ValueError):
            replace(suite, sources=(bad,) + suite.sources[1:]).validate()

    def test_arbitrary_manifest_path_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            load_suite("../../unexpected")

    def test_every_claim_has_a_scoped_draft_home(self) -> None:
        for key in ("passport", "national_id"):
            suite = load_suite(key)
            used = {
                claim
                for family in suite.families
                for scope in family.scopes
                for claim in scope.claims
            }
            self.assertEqual(used, {claim.id for claim in suite.claims})

    def test_service_identity_cannot_be_silently_forked(self) -> None:
        with self.assertRaises(ValueError):
            replace(load_suite("passport"), service_id="another_service").validate()

    def test_one_family_cannot_reuse_another_procedure_identity(self) -> None:
        suite = load_suite("passport")
        first, second = suite.families[:2]
        with self.assertRaises(ValueError):
            replace(
                suite,
                families=(first, replace(second, procedure_id=first.procedure_id))
                + suite.families[2:],
            ).validate()

    def test_existing_identity_text_must_have_both_languages(self) -> None:
        suite = load_suite("passport")
        first = replace(suite.families[0], identity_ar="عنوان قائم", identity_en=None)
        with self.assertRaises(ValueError):
            replace(suite, families=(first,) + suite.families[1:]).validate()
