import ast
import unittest
from pathlib import Path

_FORBIDDEN_ROOTS = ("prototype", "bardi_prototype")


def _is_forbidden_module(module: str) -> bool:
    return any(module == root or module.startswith(f"{root}.") for root in _FORBIDDEN_ROOTS)


def _literal_dynamic_import_is_forbidden(call: ast.Call) -> bool:
    if not call.args or not isinstance(call.args[0], ast.Constant):
        return False
    module = call.args[0].value
    if not isinstance(module, str) or not _is_forbidden_module(module):
        return False

    function = call.func
    if isinstance(function, ast.Name):
        return function.id in {"__import__", "import_module"}
    return (
        isinstance(function, ast.Attribute)
        and function.attr == "import_module"
        and isinstance(function.value, ast.Name)
        and function.value.id == "importlib"
    )


def _forbidden_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden_module(alias.name):
                    violations.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and _is_forbidden_module(node.module):
                violations.append(f"line {node.lineno}: from {node.module} import ...")
            elif node.module is None and any(
                _is_forbidden_module(alias.name) for alias in node.names
            ):
                violations.append(f"line {node.lineno}: relative prototype import")
        elif isinstance(node, ast.Call) and _literal_dynamic_import_is_forbidden(node):
            violations.append(f"line {node.lineno}: literal prototype dynamic import")

    return violations


class PrototypeBoundaryTests(unittest.TestCase):
    def test_production_backend_does_not_import_the_frozen_prototype(self) -> None:
        backend = Path(__file__).resolve().parents[2]
        violations = {
            f"{path}: {violation}"
            for path in sorted(backend.rglob("*.py"))
            for violation in _forbidden_imports(path)
        }

        self.assertFalse(violations, "\n".join(sorted(violations)))
