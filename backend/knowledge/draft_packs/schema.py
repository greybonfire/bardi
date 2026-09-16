"""Explicit v1 authoring transport. No ORM imports or database configuration required."""

from __future__ import annotations

import json
import math
from datetime import date
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    field_validator,
    model_validator,
)

from .errors import Diagnostic, DraftPackError

MAX_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 512
MAX_RECORDS = 10_000


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("Must not be blank.")
    return value


def _date(value: str) -> str:
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("Use a canonical YYYY-MM-DD calendar date.")
    return value


# Explicit Python str.strip whitespace set, portable across JSON Schema regex engines.
NONBLANK_PATTERN = (
    r"[^\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680"
    r"\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]"
)
Identifier = Annotated[
    str, Field(min_length=1, max_length=128, pattern=NONBLANK_PATTERN), AfterValidator(_nonblank)
]
Text = Annotated[str, Field(min_length=1, pattern=NONBLANK_PATTERN), AfterValidator(_nonblank)]
DateString = Annotated[
    str,
    Field(pattern=r"^\d{4}-\d{2}-\d{2}$", json_schema_extra={"format": "date"}),
    AfterValidator(_date),
]
Nonnegative = Annotated[int, Field(ge=0)]
Scope = Literal["procedure", "eligibility_basis"]


class TransportModel(BaseModel):
    model_config = ConfigDict(
        strict=True, extra="forbid", allow_inf_nan=False, serialize_by_alias=True
    )


class DateLiteral(TransportModel):
    value: DateString = Field(alias="$date")


RuleLiteral = bool | int | str | DateLiteral


class ComparisonRule(TransportModel):
    op: Literal["eq", "lt", "lte", "gt", "gte"]
    fact: Identifier
    value: RuleLiteral


class InRule(TransportModel):
    op: Literal["in"]
    fact: Identifier
    value: Annotated[list[RuleLiteral], Field(min_length=1, max_length=128)]


class ExistsRule(TransportModel):
    op: Literal["exists"]
    fact: Identifier


class BooleanRule(TransportModel):
    op: Literal["all", "any"]
    children: Annotated[list[Rule], Field(min_length=1, max_length=128)]


class NotRule(TransportModel):
    op: Literal["not"]
    children: Annotated[list[Rule], Field(min_length=1, max_length=1)]


def _rule_size(rule: Any) -> Any:
    stack = [rule]
    count = 0
    while stack:
        node = stack.pop()
        count += 1
        if count > 128:
            raise ValueError("Rule exceeds 128 nodes.")
        stack.extend(getattr(node, "children", ()))
    return rule


Rule = Annotated[
    ComparisonRule | InRule | ExistsRule | BooleanRule | NotRule,
    Field(discriminator="op"),
    AfterValidator(_rule_size),
]
BooleanRule.model_rebuild()
NotRule.model_rebuild()


class EmptyRule(TransportModel):
    pass


OptionalRule = Rule | EmptyRule


class Identity(TransportModel):
    semantic_id: Identifier


class Bilingual(Identity):
    text_ar: Text
    text_en: Text


class Interval(TransportModel):
    effective_from: DateString | None = None
    effective_to: DateString | None = None


class Service(Bilingual):
    pass


class Procedure(Bilingual):
    primary_service: Identifier


class Fact(TransportModel):
    key: Identifier
    kind: Literal["boolean", "enum", "integer", "date", "string"]
    enum_values: list[str] = Field(default_factory=list)
    minimum: int | None = None


class Authority(Identity):
    name_ar: Text
    name_en: Text


class DocumentType(Authority):
    pass


class Source(Identity, Interval):
    authority: Identifier
    title: Text
    locator: Text
    classification: Literal["official", "field_report", "secondary"]
    published_on: DateString | None = None
    retrieved_on: DateString
    observation_date: DateString | None = None
    observation_context: str = ""


class Catalog(TransportModel):
    services: list[Service]
    procedures: list[Procedure]
    facts: list[Fact]
    authorities: list[Authority]
    sources: list[Source]
    document_types: list[DocumentType]


class Version(Identity, Interval):
    procedure: Identifier
    rules_contract_version: Literal["v1"] = "v1"
    text_ar: str = ""
    text_en: str = ""
    applicability: OptionalRule = Field(default_factory=EmptyRule)


class Risks(TransportModel):
    legal: bool
    military: bool
    custody_guardianship: bool
    contested_identity: bool


class Basis(Bilingual, Interval):
    reachability: OptionalRule = Field(default_factory=EmptyRule)
    qualification: Rule
    display_order: Nonnegative = 0


class Claim(Bilingual, Interval):
    applicability: OptionalRule = Field(default_factory=EmptyRule)


class ChecklistItem(Claim):
    classification: Literal["official_requirement", "practical_preparation", "candidate"]
    document_type: Identifier | None = None
    quantity: Nonnegative = 1
    original_quantity: Nonnegative = 0
    copy_quantity: Nonnegative = 0
    display_order: Nonnegative = 0
    scope: Scope = "procedure"
    scope_reference: Annotated[str, Field(max_length=128)] = ""


class Step(Claim):
    phase: Identifier
    phase_order: Nonnegative = 0
    slot: Nonnegative = 0
    scope: Scope = "procedure"
    eligibility_basis: Identifier | None = None


class Warning(Claim):
    severity: Literal["info", "important"] = "info"
    kind: Literal["administrative", "product"]
    role: Literal["general", "regeneration", "limitation"] = "general"
    display_order: Nonnegative = 0


class Fee(Claim):
    value_state: Literal["known", "range", "unknown", "unverified"]
    amount: Nonnegative | None = None
    minimum_amount: Nonnegative | None = None
    maximum_amount: Nonnegative | None = None
    currency: Annotated[Text, Field(max_length=16)]
    fee_type: Annotated[Text, Field(max_length=64)] = "service_fee"
    display_order: Nonnegative = 0
    scope: Scope = "procedure"
    eligibility_basis: Identifier | None = None


class Dependency(Claim):
    target_procedure: Identifier
    relation: Literal["blocking_prerequisite"] = "blocking_prerequisite"
    satisfied_when: Rule
    display_order: Nonnegative = 0


class RoutingAssociation(Identity, Interval):
    service_point_version: Identifier
    applicability: Rule


class EvidenceOwner(Identity):
    kind: Literal[
        "checklist_item",
        "step",
        "warning",
        "fee",
        "eligibility_basis",
        "procedure_dependency",
        "procedure_service_point_association",
    ]


class EvidenceLink(Identity, Interval):
    owner: EvidenceOwner
    passage: Text
    location: str = ""
    applicability_context: str = ""
    retrieved_on: DateString | None = None
    support_status: Literal["supports", "context", "contradicts"] = "supports"
    sources: list[Identifier]


class EvaluationContext(TransportModel):
    evaluation_date: DateString
    locale: Literal["ar", "en"]


class Scenario(TransportModel):
    name: Annotated[Text, Field(max_length=160)]
    kind: Literal["positive", "negative", "unknown", "contradictory", "supported_edge"]
    evaluation_context: EvaluationContext
    source_facts: dict[Identifier, JsonValue] = Field(
        default_factory=dict,
        json_schema_extra={
            "propertyNames": {"minLength": 1, "maxLength": 128, "pattern": NONBLANK_PATTERN}
        },
    )
    expected_result_family: Literal["plan", "next_question", "inconclusive", "invalid"]
    expected_identifiers: dict[str, JsonValue] = Field(default_factory=dict)
    expected_diagnostics: list[str] = Field(default_factory=list)


class Question(Bilingual):
    fact: Identifier
    priority: Nonnegative
    resolves_facts: list[Identifier] = Field(default_factory=list)


class Candidate(TransportModel):
    procedure: Identifier
    selection_predicate: Rule


class Contradiction(Identity):
    condition: Rule
    facts: Annotated[list[Identifier], Field(min_length=2)]


class ServiceSetup(TransportModel):
    service: Identifier
    questions: list[Question]
    candidates: list[Candidate]
    contradictions: list[Contradiction]


class DraftPack(TransportModel):
    format: Literal["bardi.draft-pack"]
    format_version: Literal[1]
    base_revision: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None
    catalog: Catalog
    version: Version
    risks: Risks
    service_setup: ServiceSetup | None
    bases: list[Basis]
    checklist_items: list[ChecklistItem]
    steps: list[Step]
    warnings: list[Warning]
    fees: list[Fee]
    dependencies: list[Dependency]
    routing_associations: list[RoutingAssociation]
    evidence_links: list[EvidenceLink]
    scenarios: list[Scenario]

    @field_validator("format_version", mode="before")
    @classmethod
    def strict_version(cls, value: Any) -> Any:
        if type(value) is not int:
            raise ValueError("format_version must be integer 1.")
        return value

    @model_validator(mode="after")
    def identities(self) -> Self:
        _check_identities(self.model_dump(mode="json", by_alias=True))
        return self


def _fail(code: str, path: tuple[str | int, ...], message: str) -> None:
    raise DraftPackError((Diagnostic(code, path, message),))


def _check_identities(data: dict[str, Any]) -> None:
    # Only authored collections have identities. Synthetic scenario JSON is opaque.
    collections: list[tuple[tuple[str | int, ...], list[Any], str]] = []
    for name in (
        "bases",
        "checklist_items",
        "steps",
        "warnings",
        "fees",
        "dependencies",
        "routing_associations",
        "evidence_links",
        "scenarios",
    ):
        collections.append(((name,), data[name], "name" if name == "scenarios" else "semantic_id"))
    for name in ("services", "procedures", "facts", "authorities", "sources", "document_types"):
        rows = data["catalog"][name]
        collections.append((("catalog", name), rows, "key" if name == "facts" else "semantic_id"))
    if data["service_setup"] is not None:
        for name in ("questions", "candidates", "contradictions"):
            collections.append(
                (
                    ("service_setup", name),
                    data["service_setup"][name],
                    "procedure" if name == "candidates" else "semantic_id",
                )
            )

    def unique(values: list[Any], path: tuple[str | int, ...]) -> None:
        seen: set[Any] = set()
        for index, identity in enumerate(values):
            if identity in seen:
                _fail("duplicate_identity", (*path, index), "Duplicate scoped identity.")
            seen.add(identity)

    records = 0
    reference_fields: dict[tuple[str | int, ...], str] = {
        ("catalog", "facts"): "enum_values",
        ("service_setup", "questions"): "resolves_facts",
        ("service_setup", "contradictions"): "facts",
        ("evidence_links",): "sources",
    }
    for path, rows, key in collections:
        records += len(rows)
        identities = [row[key] for row in rows]
        if path == ("evidence_links",):
            identities = [
                (row["owner"]["kind"], row["owner"]["semantic_id"], row[key]) for row in rows
            ]
        unique(identities, path)
        if reference := reference_fields.get(path):
            for index, row in enumerate(rows):
                unique(row[reference], (*path, index, reference))
    if records > MAX_RECORDS:
        _fail("record_limit", (), "Draft pack exceeds 10000 records.")


def _precheck(value: Any) -> None:
    stack: list[tuple[Any, int, tuple[str | int, ...]]] = [(value, 0, ())]
    while stack:
        node, depth, path = stack.pop()
        if depth > MAX_DEPTH:
            _fail("depth_limit", path, "JSON exceeds 512 nesting levels.")
        if isinstance(node, float) and not math.isfinite(node):
            _fail("nonfinite_number", path, "Nonfinite numbers are not JSON values.")
        if isinstance(node, dict):
            for key, child in node.items():
                if type(key) is not str:
                    _fail("invalid_json", path, "JSON object keys must be strings.")
                stack.append((child, depth + 1, (*path, key)))
        elif isinstance(node, list):
            stack.extend((child, depth + 1, (*path, i)) for i, child in enumerate(node))
        elif node is not None and type(node) not in (str, int, float, bool):
            _fail("invalid_json", path, "Expected a JSON value.")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate_key", (key,), "Duplicate JSON object key.")
        result[key] = value
    return result


def parse_draft_pack(raw: bytes | str | dict[str, Any]) -> DraftPack:
    """Parse bounded untrusted JSON, without accepting executable or editorial fields."""
    try:
        if isinstance(raw, (bytes, str)):
            size = len(raw) if isinstance(raw, bytes) else len(raw.encode("utf-8"))
            if size > MAX_BYTES:
                _fail("size_limit", (), "Draft pack exceeds 8 MiB.")
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            # Bound nesting before the recursive JSON decoder sees it; ignore quoted brackets.
            depth = 0
            quoted = escaped = False
            for char in text:
                if quoted:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == '"':
                        quoted = False
                elif char == '"':
                    quoted = True
                elif char in "[{":
                    depth += 1
                    if depth > MAX_DEPTH:
                        _fail("depth_limit", (), "JSON exceeds 512 nesting levels.")
                elif char in "]}":
                    depth -= 1
            try:
                value = json.loads(text, object_pairs_hook=_pairs)
            except ValueError:
                # Includes the interpreter's integer-token digit limit.
                _fail("invalid_json", (), "Expected valid bounded JSON.")
        else:
            value = raw
        _precheck(value)
        if not isinstance(value, dict):
            _fail("invalid_json", (), "Draft pack must be a JSON object.")
        if not isinstance(raw, (bytes, str)):
            try:
                size = len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
            except ValueError:
                _fail("invalid_json", (), "Expected valid bounded JSON.")
            if size > MAX_BYTES:
                _fail("size_limit", (), "Draft pack exceeds 8 MiB.")
        return DraftPack.model_validate(value)
    except ValidationError as exc:
        raise DraftPackError(
            Diagnostic("invalid_schema", tuple(error["loc"]), error["msg"])
            for error in exc.errors(include_input=False, include_url=False)
        ) from None
    except UnicodeError, json.JSONDecodeError:
        _fail("invalid_json", (), "Expected valid UTF-8 JSON.")
    except RecursionError:
        _fail("depth_limit", (), "JSON nesting exceeds parser capacity.")
    raise AssertionError("unreachable")
