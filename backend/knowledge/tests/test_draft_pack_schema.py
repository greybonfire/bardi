"""Database-free regression coverage for the explicit authoring transport."""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from knowledge.draft_packs.errors import Diagnostic, DraftPackError
from knowledge.draft_packs.schema import MAX_BYTES, DraftPack, parse_draft_pack

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "docs/draft-packs/examples/minimal-research.json"


class DraftPackSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack: dict[str, Any] = json.loads(EXAMPLE.read_text())

    def rejects(self, raw: Any, code: str = "invalid_schema") -> DraftPackError:
        with self.assertRaises(DraftPackError) as caught:
            parse_draft_pack(raw)
        self.assertIn(code, [d.code for d in caught.exception.diagnostics])
        return caught.exception

    def test_example_is_canonical_and_self_contained(self) -> None:
        for raw in (self.pack, EXAMPLE.read_bytes(), EXAMPLE.read_text()):
            self.assertEqual(parse_draft_pack(raw).model_dump(mode="json"), self.pack)
        self.assertEqual(self.pack["catalog"]["sources"], [])
        self.assertEqual(len(self.pack["service_setup"]["questions"]), 1)
        self.assertEqual(len(self.pack["service_setup"]["candidates"]), 1)

    def test_schema_artifact_has_no_drift(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/export_draft_pack_schema.py"), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        schema = json.loads((ROOT / "docs/draft-packs/draft-pack-v1.schema.json").read_text())
        self.assertEqual(set(schema["required"]), set(DraftPack.model_fields))
        self.assertFalse(schema["additionalProperties"])

    def test_full_root_and_catalog_required(self) -> None:
        for field in self.pack:
            with self.subTest(field=field):
                value = copy.deepcopy(self.pack)
                del value[field]
                self.rejects(value)
        for field in self.pack["catalog"]:
            value = copy.deepcopy(self.pack)
            del value["catalog"][field]
            self.rejects(value)

    def test_protected_unknown_fields_rejected_at_typed_boundaries(self) -> None:
        for path, key in [
            ((), "author"),
            (("version",), "state"),
            (("catalog", "services", 0), "is_active"),
            (("catalog", "facts", 0), "derived"),
            (("service_setup", "questions", 0), "is_published"),
            (("service_setup",), "overwrite"),
        ]:
            value = copy.deepcopy(self.pack)
            node: Any = value
            for part in path:
                node = node[part]
            node[key] = True
            error = self.rejects(value)
            self.assertTrue(any(d.path == (*path, key) for d in error.diagnostics))

    def test_scalars_identifiers_and_calendar_dates_are_strict(self) -> None:
        for field, bad in [
            ("format_version", True),
            ("format_version", 1.0),
            ("format_version", "1"),
            ("base_revision", "A" * 64),
        ]:
            self.rejects({**self.pack, field: bad})
        for bad in (True, 0, "", "  ", "x" * 129):
            self.pack["version"]["semantic_id"] = bad
            self.rejects(self.pack)
        self.pack = json.loads(EXAMPLE.read_text())
        for bad in ("2025-02-29", "2024-2-29", "2024-02-29T00:00:00", 20240229):
            self.pack["version"]["effective_from"] = bad
            self.rejects(self.pack)
        self.pack["version"]["effective_from"] = "2024-02-29"
        self.assertEqual(parse_draft_pack(self.pack).version.effective_from, "2024-02-29")
        self.pack["risks"]["legal"] = 1
        self.rejects(self.pack)

    def test_malformed_json_duplicate_keys_and_nonfinite(self) -> None:
        for raw in (b"\xff", "{", "[]", '"text"', "\ud800"):
            self.rejects(raw, "invalid_json")
        self.rejects('{"catalog":{"services":[],"services":[]}}', "duplicate_key")
        for literal in ("NaN", "Infinity", "-Infinity", "1e999"):
            self.rejects('{"x":' + literal + "}", "nonfinite_number")
        self.rejects({"x": float("nan")}, "nonfinite_number")

    def test_resource_limits(self) -> None:
        self.rejects(b" " * (MAX_BYTES + 1), "size_limit")
        self.rejects("[" * 513 + "]" * 513, "depth_limit")
        cycle: dict[str, Any] = {}
        cycle["self"] = cycle
        self.rejects(cycle, "depth_limit")
        with patch("knowledge.draft_packs.schema.MAX_RECORDS", 1):
            self.rejects(self.pack, "record_limit")
        with patch("knowledge.draft_packs.schema.MAX_BYTES", 1):
            self.rejects(self.pack, "size_limit")

    def test_rule_shapes_and_limits(self) -> None:
        bad_rules = [
            None,
            {"formula": "eval()"},
            {"op": "exists", "fact": "x", "value": True},
            {"op": "all", "children": []},
            {"op": "not", "children": []},
            {"op": "eq", "fact": "x", "value": None},
            {"op": "eq", "fact": "x", "value": 1.2},
            {"op": "eq", "fact": "x", "value": {"$date": "2025-02-29"}},
            {"op": "in", "fact": "x", "value": list(range(129))},
            {"op": "all", "children": [{"op": "exists", "fact": "x"}] * 128},
        ]
        for rule in bad_rules:
            with self.subTest(rule=rule):
                self.pack["version"]["applicability"] = rule
                self.rejects(self.pack)
        rule = {"op": "eq", "fact": "x", "value": {"$date": "2024-02-29"}}
        self.pack["version"]["applicability"] = rule
        self.assertEqual(
            parse_draft_pack(self.pack).model_dump(mode="json")["version"]["applicability"], rule
        )
        self.pack["version"]["applicability"] = {}
        self.pack["service_setup"]["candidates"][0]["selection_predicate"] = {}
        self.rejects(self.pack)

    def test_duplicate_identities_and_evidence_owner_scope(self) -> None:
        self.pack["catalog"]["services"] *= 2
        error = self.rejects(self.pack, "duplicate_identity")
        self.assertEqual(error.diagnostics[0].path, ("catalog", "services", 1))
        self.pack["catalog"]["services"].pop()
        evidence: dict[str, Any] = {
            "semantic_id": "citation",
            "owner": {"kind": "step", "semantic_id": "one"},
            "passage": "Synthetic",
            "sources": [],
        }
        other = copy.deepcopy(evidence)
        other["owner"]["semantic_id"] = "two"
        self.pack["evidence_links"] = [evidence, other]
        parse_draft_pack(self.pack)
        self.pack["evidence_links"].append(evidence)
        self.rejects(self.pack, "duplicate_identity")

    def test_all_authored_row_types_round_trip(self) -> None:
        text = {"semantic_id": "synthetic", "text_ar": "تجريبي", "text_en": "Synthetic"}
        rule = {"op": "exists", "fact": "synthetic_ready"}
        self.pack["catalog"]["authorities"] = [
            {"semantic_id": "synthetic", "name_ar": "تجريبي", "name_en": "Synthetic"}
        ]
        self.pack["catalog"]["document_types"] = self.pack["catalog"]["authorities"]
        self.pack["catalog"]["sources"] = [
            {
                "semantic_id": "synthetic",
                "authority": "synthetic",
                "title": "Synthetic",
                "locator": "urn:synthetic",
                "classification": "secondary",
                "retrieved_on": "2026-01-01",
            }
        ]
        self.pack["bases"] = [{**text, "qualification": rule}]
        self.pack["checklist_items"] = [{**text, "classification": "candidate"}]
        self.pack["steps"] = [{**text, "phase": "synthetic"}]
        self.pack["warnings"] = [{**text, "kind": "product"}]
        self.pack["fees"] = [{**text, "value_state": "unknown", "currency": "EGP"}]
        self.pack["dependencies"] = [{**text, "target_procedure": "other", "satisfied_when": rule}]
        self.pack["routing_associations"] = [
            {
                "semantic_id": "synthetic",
                "service_point_version": "existing",
                "applicability": rule,
            }
        ]
        self.pack["evidence_links"] = [
            {
                "semantic_id": "synthetic",
                "owner": {"kind": "step", "semantic_id": "synthetic"},
                "passage": "Synthetic",
                "sources": ["synthetic"],
            }
        ]
        self.pack["service_setup"]["contradictions"] = [
            {
                "semantic_id": "synthetic",
                "facts": ["synthetic_ready", "other"],
                "condition": {"op": "all", "children": [rule, {"op": "exists", "fact": "other"}]},
            }
        ]
        dumped = parse_draft_pack(self.pack).model_dump(mode="json")
        self.assertEqual(parse_draft_pack(json.dumps(dumped)).model_dump(mode="json"), dumped)
        self.assertIsNone(dumped["fees"][0]["amount"])
        self.assertEqual(dumped["catalog"]["sources"][0]["retrieved_on"], "2026-01-01")

    def test_invalid_scenario_values_are_preserved_for_domain_validation(self) -> None:
        self.pack["scenarios"] = [
            {
                "name": "Deliberately invalid synthetic value",
                "kind": "negative",
                "evaluation_context": {"evaluation_date": "2026-01-01", "locale": "en"},
                "source_facts": {"synthetic_ready": None},
                "expected_result_family": "invalid",
                "expected_diagnostics": ["invalid_fact_value:synthetic_ready"],
            }
        ]
        self.assertIsNone(parse_draft_pack(self.pack).scenarios[0].source_facts["synthetic_ready"])

    def test_large_integer_token_is_a_structured_error(self) -> None:
        self.rejects(b'{"value":' + b"9" * 5000 + b"}", "invalid_json")
        self.rejects({"value": 10**5000}, "invalid_json")

    def test_required_rules_cannot_be_omitted_or_empty(self) -> None:
        for collection, field, extra in (
            ("bases", "qualification", {}),
            ("dependencies", "satisfied_when", {"target_procedure": "other"}),
        ):
            row: dict[str, Any] = {
                "semantic_id": "one",
                "text_ar": "نص",
                "text_en": "Text",
                **extra,
            }
            self.pack[collection] = [row]
            self.rejects(self.pack)
            row[field] = {}
            self.rejects(self.pack)
            row[field] = {"op": "exists", "fact": "synthetic_ready"}
            parse_draft_pack(self.pack)

    def test_synthetic_nested_json_is_not_an_authored_collection(self) -> None:
        scenario = {
            "name": "Synthetic",
            "kind": "negative",
            "evaluation_context": {"evaluation_date": "2026-01-01", "locale": "en"},
            "expected_result_family": "invalid",
        }
        synthetic = {
            "nested": [{"owner": {}}, {"semantic_id": []}, {"name": "same"}, {"name": "same"}],
            "sources": ["same", "same"],
            "facts": [{"key": "same"}, {"key": "same"}],
        }
        self.pack["scenarios"] = [
            {**scenario, "source_facts": synthetic, "expected_identifiers": synthetic}
        ]
        count = sum(len(rows) for rows in self.pack["catalog"].values())
        count += sum(
            len(self.pack["service_setup"][key])
            for key in ("questions", "candidates", "contradictions")
        )
        count += 1  # scenario; all other root collections in the example are empty
        with patch("knowledge.draft_packs.schema.MAX_RECORDS", count):
            parsed = parse_draft_pack(json.dumps(self.pack).encode())
            self.assertEqual(parsed.scenarios[0].source_facts, synthetic)
            self.assertEqual(parsed.scenarios[0].expected_identifiers, synthetic)
        with patch("knowledge.draft_packs.schema.MAX_RECORDS", count - 1):
            self.rejects(self.pack, "record_limit")

    def test_designated_reference_arrays_reject_duplicates(self) -> None:
        self.pack["catalog"]["facts"][0]["enum_values"] = ["same", "same"]
        self.rejects(self.pack, "duplicate_identity")
        self.pack["catalog"]["facts"][0]["enum_values"] = []
        self.pack["service_setup"]["questions"][0]["resolves_facts"] = ["same", "same"]
        self.rejects(self.pack, "duplicate_identity")

    def test_schema_nonblank_constraints_match_parser(self) -> None:
        definitions = DraftPack.model_json_schema()["$defs"]
        whitespace = "".join(chr(i) for i in range(0x110000) if chr(i).isspace())
        for model, field, path in (
            ("Version", "semantic_id", ("version",)),
            ("Service", "text_en", ("catalog", "services", 0)),
            ("Question", "text_ar", ("service_setup", "questions", 0)),
        ):
            constraints = definitions[model]["properties"][field]
            self.assertGreaterEqual(constraints["minLength"], 1)
            for value in ("", " ", "\t\n", whitespace, "Text", "نص", whitespace + "x"):
                value = value[:128]  # keep within identifier maximum
                accepted = bool(value.strip())
                self.assertEqual(bool(re.search(constraints["pattern"], value)), accepted)
                pack = copy.deepcopy(self.pack)
                node: Any = pack
                for part in path:
                    node = node[part]
                node[field] = value
                if accepted:
                    parse_draft_pack(pack)
                else:
                    self.rejects(pack)
        for field in ("text_ar", "text_en"):
            self.assertNotIn("pattern", definitions["Version"]["properties"][field])
            self.pack["version"][field] = whitespace
        parse_draft_pack(self.pack)

    def test_schema_fact_key_constraints_match_parser(self) -> None:
        properties = DraftPack.model_json_schema()["$defs"]["Scenario"]["properties"]
        constraints = properties["source_facts"]["propertyNames"]
        self.assertEqual(constraints["minLength"], 1)
        self.assertEqual(constraints["maxLength"], 128)
        self.pack["scenarios"] = [
            {
                "name": "Synthetic invalid values",
                "kind": "contradictory",
                "evaluation_context": {"evaluation_date": "2026-01-01", "locale": "en"},
                "source_facts": {},
                "expected_result_family": "invalid",
                "expected_diagnostics": ["invalid_fact_value"],
            }
        ]
        for key in ("", " ", "\t\n", "\u00a0\u2003\u3000", "synthetic_ready", "حالة", "x" * 129):
            with self.subTest(key=key):
                accepted = bool(key.strip()) and len(key) <= 128
                valid_length = constraints["minLength"] <= len(key) <= constraints["maxLength"]
                schema_accepts = valid_length and bool(re.search(constraints["pattern"], key))
                self.assertEqual(schema_accepts, accepted)
                self.pack["scenarios"][0]["source_facts"] = {key: [{"owner": {}}]}
                if accepted:
                    parse_draft_pack(self.pack)
                else:
                    self.rejects(self.pack)

    def test_diagnostics_are_stable_json_safe_and_do_not_echo_input(self) -> None:
        diagnostic = Diagnostic("test", ("fees", 0, "amount"), "Invalid amount.")
        self.assertEqual(
            DraftPackError([diagnostic]).as_dict(), {"diagnostics": [diagnostic.as_dict()]}
        )
        self.pack["risks"]["legal"] = "SECRET"
        self.assertNotIn("SECRET", json.dumps(self.rejects(self.pack).as_dict()))
