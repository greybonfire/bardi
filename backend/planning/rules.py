"""Strict decoding and validation for the inert v1 rule AST."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal, cast

from .diagnostics import DiagnosticPath, ValidationDiagnostic
from .facts import FACT_DEFINITIONS, FactDefinition, FactValue, value_matches_definition

MAX_RULE_NODES = 128
MAX_IN_OPERANDS = 128

type LeafOperator = Literal["eq", "in", "lt", "lte", "gt", "gte", "exists"]
type BooleanOperator = Literal["all", "any", "not"]
type RuleOperator = LeafOperator | BooleanOperator

LEAF_OPERATORS = frozenset({"eq", "in", "lt", "lte", "gt", "gte", "exists"})
BOOLEAN_OPERATORS = frozenset({"all", "any", "not"})
SUPPORTED_OPERATORS = LEAF_OPERATORS | BOOLEAN_OPERATORS
_ORDERING_OPERATORS = frozenset({"lt", "lte", "gt", "gte"})


@dataclass(frozen=True, slots=True)
class Predicate:
    op: RuleOperator
    fact: str | None = None
    value: FactValue | tuple[FactValue, ...] | None = None
    children: tuple[Predicate, ...] = ()


def serialize_rule_v1(predicate: Predicate) -> dict[str, object]:
    """Serialize a decoded predicate to the exact JSON-compatible v1 shape."""

    if predicate.op in BOOLEAN_OPERATORS:
        return {
            "op": predicate.op,
            "children": [serialize_rule_v1(child) for child in predicate.children],
        }
    result: dict[str, object] = {"op": predicate.op, "fact": predicate.fact}
    if predicate.op == "exists":
        return result

    def encode(value: FactValue) -> object:
        return {"$date": value.isoformat()} if isinstance(value, date) else value

    if predicate.op == "in":
        values = cast(tuple[FactValue, ...], predicate.value)
        result["value"] = [encode(value) for value in values]
    else:
        result["value"] = encode(cast(FactValue, predicate.value))
    return result


@dataclass(frozen=True, slots=True)
class RuleValidationResult:
    predicate: Predicate | None
    diagnostics: tuple[ValidationDiagnostic, ...]

    @property
    def is_valid(self) -> bool:
        return not self.diagnostics

    @property
    def diagnostic_codes(self) -> tuple[str, ...]:
        return tuple(item.code for item in self.diagnostics)


@dataclass(slots=True)
class _DecodedNode:
    op: RuleOperator
    fact: str | None
    value: FactValue | tuple[FactValue, ...] | None
    child_ids: tuple[int, ...]


def _decode_literal(definition: FactDefinition, raw: object) -> FactValue | None:
    if definition.kind != "date":
        if value_matches_definition(definition, raw):
            return cast(FactValue, raw)
        return None
    if type(raw) is not dict:
        return None
    envelope = cast(dict[object, object], raw)
    if set(envelope) != {"$date"} or type(envelope["$date"]) is not str:
        return None
    text = envelope["$date"]
    try:
        decoded = date.fromisoformat(text)
    except ValueError:
        return None
    return decoded if decoded.isoformat() == text else None


def validate_rule_v1(
    raw: object, definitions: Mapping[str, FactDefinition] = FACT_DEFINITIONS
) -> RuleValidationResult:
    """Decode an already-deserialized v1 AST, returning no predicate on any error."""

    diagnostics: list[ValidationDiagnostic] = []
    seen: set[tuple[str, DiagnosticPath]] = set()
    records: list[_DecodedNode | None] = []
    # raw node, path, record id
    stack: list[tuple[object, DiagnosticPath, int]] = [(raw, ("rule",), 0)]
    node_count = 0
    too_large = False

    def add(code: str, path: DiagnosticPath) -> None:
        pair = (code, path)
        if pair not in seen:
            seen.add(pair)
            diagnostics.append(ValidationDiagnostic(code, path))

    while stack:
        node_raw, path, record_id = stack.pop()
        node_count += 1
        if node_count > MAX_RULE_NODES:
            if not too_large:
                add("rule_too_large", ("rule",))
                too_large = True
            break

        while len(records) <= record_id:
            records.append(None)

        if type(node_raw) is not dict:
            add("malformed_rule:<unknown>", path)
            continue
        node = cast(dict[object, object], node_raw)
        op_raw = node.get("op")
        if type(op_raw) is not str:
            add("malformed_rule:<unknown>", path + ("op",))
            continue
        op = op_raw
        if op not in SUPPORTED_OPERATORS:
            add(f"unsupported_rule_operator:{op}", path + ("op",))
            continue

        typed_op = cast(RuleOperator, op)
        allowed = {"op", "children"} if op in BOOLEAN_OPERATORS else {"op", "fact"}
        if op != "exists" and op not in BOOLEAN_OPERATORS:
            allowed.add("value")
        for field in sorted(
            (key for key in node if type(key) is str and key not in allowed), key=str
        ):
            add(f"malformed_rule:{op}", path + (field,))
        if any(type(key) is not str for key in node):
            add(f"malformed_rule:{op}", path)

        if op in BOOLEAN_OPERATORS:
            children_raw = node.get("children")
            child_ids: tuple[int, ...] = ()
            descend = False
            if type(children_raw) is not list:
                add(f"malformed_rule:{op}", path + ("children",))
            else:
                children = cast(list[object], children_raw)
                if op in {"all", "any"}:
                    if not children:
                        add(f"empty_boolean_composition:{op}", path + ("children",))
                    else:
                        descend = True
                elif len(children) != 1:
                    add("malformed_rule:not", path + ("children",))
                else:
                    descend = True
                if descend:
                    capacity = MAX_RULE_NODES - node_count + 1
                    visit_count = min(len(children), max(0, capacity))
                    ids = tuple(len(records) + index for index in range(visit_count))
                    child_ids = ids
                    records.extend(None for _ in ids)
                    for index in range(visit_count - 1, -1, -1):
                        stack.append((children[index], path + ("children", index), ids[index]))
            records[record_id] = _DecodedNode(typed_op, None, None, child_ids)
            continue

        fact_raw = node.get("fact")
        fact: str | None = None
        definition: FactDefinition | None = None
        if "fact" not in node:
            add(f"missing_rule_fact:{op}", path + ("fact",))
        elif type(fact_raw) is not str:
            add(f"malformed_rule:{op}", path + ("fact",))
        else:
            fact = fact_raw
            definition = definitions.get(fact)
            if definition is None:
                add(f"unsupported_rule_fact:{fact}", path + ("fact",))

        decoded_value: FactValue | tuple[FactValue, ...] | None = None
        if op == "exists":
            if definition is not None and definition.derived:
                add(f"exists_requires_source_fact:{fact}", path + ("fact",))
        elif definition is not None:
            if op in _ORDERING_OPERATORS and definition.kind not in {"integer", "date"}:
                add(f"ordering_not_supported_for_fact:{fact}", path + ("fact",))
            value_raw = node.get("value")
            if op == "in":
                if type(value_raw) is not list:
                    add(f"invalid_rule_operand:{fact}", path + ("value",))
                else:
                    operands = cast(list[object], value_raw)
                    if not operands or len(operands) > MAX_IN_OPERANDS:
                        add(f"invalid_rule_operand:{fact}", path + ("value",))
                    else:
                        decoded_operands: list[FactValue] = []
                        for index, operand in enumerate(operands):
                            decoded = _decode_literal(definition, operand)
                            if decoded is None:
                                add(f"invalid_rule_operand:{fact}", path + ("value", index))
                            else:
                                decoded_operands.append(decoded)
                        if len(decoded_operands) == len(operands):
                            decoded_value = tuple(decoded_operands)
            else:
                decoded = _decode_literal(definition, value_raw)
                if decoded is None:
                    add(f"invalid_rule_operand:{fact}", path + ("value",))
                else:
                    decoded_value = decoded
        records[record_id] = _DecodedNode(typed_op, fact, decoded_value, ())

    if diagnostics:
        return RuleValidationResult(None, tuple(diagnostics))

    predicates: list[Predicate | None] = [None] * len(records)
    for index in range(len(records) - 1, -1, -1):
        record = records[index]
        if record is None:  # Defensive: impossible for a valid traversal.
            return RuleValidationResult(
                None, (ValidationDiagnostic("malformed_rule:<unknown>", ("rule",)),)
            )
        decoded_children = tuple(cast(Predicate, predicates[child]) for child in record.child_ids)
        predicates[index] = Predicate(record.op, record.fact, record.value, decoded_children)
    return RuleValidationResult(cast(Predicate, predicates[0]), ())
