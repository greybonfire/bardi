"""Public framework-independent planning validation domain."""

from .diagnostics import DiagnosticPath, DiagnosticPathSegment, ValidationDiagnostic
from .evaluator import Evaluation, EvaluationTrace, TruthValue, evaluate
from .facts import (
    FACT_DEFINITIONS,
    FactDefinition,
    FactKind,
    FactValidationResult,
    FactValue,
    validate_submitted_facts,
    value_matches_definition,
)
from .rules import (
    BOOLEAN_OPERATORS,
    LEAF_OPERATORS,
    MAX_IN_OPERANDS,
    MAX_RULE_NODES,
    SUPPORTED_OPERATORS,
    BooleanOperator,
    LeafOperator,
    Predicate,
    RuleOperator,
    RuleValidationResult,
    serialize_rule_v1,
    validate_rule_v1,
)

__all__ = (
    "BOOLEAN_OPERATORS",
    "FACT_DEFINITIONS",
    "LEAF_OPERATORS",
    "MAX_IN_OPERANDS",
    "MAX_RULE_NODES",
    "SUPPORTED_OPERATORS",
    "BooleanOperator",
    "DiagnosticPath",
    "DiagnosticPathSegment",
    "Evaluation",
    "EvaluationTrace",
    "FactDefinition",
    "FactKind",
    "FactValidationResult",
    "FactValue",
    "LeafOperator",
    "Predicate",
    "RuleOperator",
    "RuleValidationResult",
    "TruthValue",
    "ValidationDiagnostic",
    "evaluate",
    "serialize_rule_v1",
    "validate_rule_v1",
    "validate_submitted_facts",
    "value_matches_definition",
)
