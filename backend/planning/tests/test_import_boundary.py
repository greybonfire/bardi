from __future__ import annotations

import ast
import unittest
from pathlib import Path


class PureDomainImportBoundaryTests(unittest.TestCase):
    def test_evaluator_api_is_public(self) -> None:
        from planning import Evaluation, EvaluationTrace, TruthValue, evaluate

        self.assertEqual(TruthValue.UNKNOWN.value, "UNKNOWN")
        self.assertTrue(callable(evaluate))
        self.assertEqual(Evaluation.__module__, "planning.evaluator")
        self.assertEqual(EvaluationTrace.__module__, "planning.evaluator")

    def test_snapshot_selection_api_is_public(self) -> None:
        from planning import (
            KnowledgeSnapshot,
            PreparedFacts,
            ProcedureSelected,
            SelectionOutcome,
            ServiceSnapshot,
            select_procedure,
        )

        self.assertEqual(KnowledgeSnapshot.__module__, "planning.catalog")
        self.assertEqual(ServiceSnapshot.__module__, "planning.catalog")
        self.assertEqual(PreparedFacts.__module__, "planning.facts")
        self.assertEqual(ProcedureSelected.__module__, "planning.selection")
        self.assertIsNotNone(SelectionOutcome)
        self.assertTrue(callable(select_procedure))

    def test_public_stateless_contract_is_framework_independent(self) -> None:
        from planning import PlanningInput, PlanningResult, plan_stateless

        self.assertEqual(PlanningInput.__module__, "planning.public")
        self.assertIsNotNone(PlanningResult)
        self.assertTrue(callable(plan_stateless))

    def test_routing_api_is_public_and_framework_independent(self) -> None:
        from planning import (
            PublicRouting,
            ServicePointSnapshot,
            select_service_point_routing,
        )

        self.assertEqual(ServicePointSnapshot.__module__, "planning.catalog")
        self.assertEqual(PublicRouting.__module__, "planning.public")
        self.assertTrue(callable(select_service_point_routing))

    def test_shared_trust_api_is_public(self) -> None:
        from planning import Freshness, TrustAssessment, assess_trust

        self.assertEqual(Freshness.__module__, "planning.trust")
        self.assertEqual(TrustAssessment.__module__, "planning.trust")
        self.assertTrue(callable(assess_trust))

    def test_production_modules_have_no_framework_or_io_dependencies(self) -> None:
        package = Path(__file__).resolve().parents[1]
        prohibited = {
            "django",
            "core",
            "bardi",
            "prototype",
            "bardi_prototype",
            "requests",
            "httpx",
            "urllib",
            "socket",
            "json",
        }
        io_calls = {"open", "exec", "eval", "compile", "__import__"}
        failures: list[str] = []
        for path in sorted(package.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in prohibited:
                            failures.append(f"{path.name}:{node.lineno}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.split(".")[0] in prohibited:
                        failures.append(f"{path.name}:{node.lineno}: from {node.module}")
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in io_calls:
                        failures.append(f"{path.name}:{node.lineno}: call {node.func.id}")
                    elif (
                        node.func.id == "import_module"
                        and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)
                        and node.args[0].value.split(".")[0] in prohibited
                    ):
                        failures.append(
                            f"{path.name}:{node.lineno}: dynamic import {node.args[0].value}"
                        )
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if (
                        node.func.attr == "import_module"
                        and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)
                        and node.args[0].value.split(".")[0] in prohibited
                    ):
                        failures.append(
                            f"{path.name}:{node.lineno}: dynamic import {node.args[0].value}"
                        )
                    elif node.func.attr in {
                        "read_text",
                        "read_bytes",
                        "write_text",
                        "write_bytes",
                        "connect",
                        "cursor",
                    }:
                        failures.append(f"{path.name}:{node.lineno}: call .{node.func.attr}")
        self.assertEqual(failures, [])
