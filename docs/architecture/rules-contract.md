# Rules and planning contract

**Status:** Authoritative  
**Initial contract version:** `v1`  
**Effective:** 2026-09-01

The production evaluator must preserve the externally observable semantics proven by the prototype without depending on prototype code.

## Facts

Every Fact key has an immutable definition: source/derived role, type, and allowed values or constraints.

Version 1 Fact kinds are boolean, enum, integer, date, and string where explicitly defined.

Rules are exact and deterministic:

- omitted Fact => UNKNOWN for value comparisons;
- explicit `null` => invalid input;
- wrong types/enum values => invalid input;
- no string-to-number, truthy/falsy, date-string, locale, or fuzzy coercion;
- administrative dates are calendar dates, not timezone-shifted timestamps.

Derived Facts are calculated before rule evaluation by the pinned rules-contract implementation. Rules consume Derived Facts but never define arbitrary formulas. Editors may publish only definitions compatible with this registry; formulas and dependency metadata are not persisted or scripted.

The exact `v1` derivations are:

- `age_years_on_evaluation_date` from `birth_date`: completed Gregorian calendar years. The year increments when the evaluation month/day reaches the birth month/day; consequently a February 29 birth reaches its next year on March 1 in a non-leap year. A birth date after the evaluation date is invalid at `facts.birth_date`.
- `card_expired_before_evaluation_date` from `national_id_expiry_date`: `evaluation_date > national_id_expiry_date`.
- `renewal_deadline_date` from `national_id_expiry_date`: add three calendar months, clamping the day to the destination month's last day (for example January 31 becomes April 30).
- `renewal_deadline_passed` from `national_id_expiry_date`: `evaluation_date > renewal_deadline_date`.
- `only_son_candidate` from `father_alive` and `other_living_sons_of_father_count`: true exactly when the father is alive and the other-living-sons count is zero.

All operands are already validated Python calendar `date`, exact booleans, or exact integers. Derivation does no parsing, timestamp/timezone conversion, or implicit coercion. Equality at expiry and deadline boundaries is false because both comparisons are strict. Calendar overflow is safely reported against `facts.national_id_expiry_date`, without leaking an exception. If a derivation is unavailable, its prepared dependency set contains only omitted source keys; derived keys never enter the original `submitted_keys` set and Questions may resolve only those source dependencies.

## Typed predicate AST

Authored rules are data, not code. The `v1` operator vocabulary is:

- leaf: `eq`, `in`, `lt`, `lte`, `gt`, `gte`, `exists`;
- boolean: `all`, `any`, `not`.

The serialized JSON/JSONB contract is sparse and operator-specific. No other fields are allowed:

```text
{"op": "eq|lt|lte|gt|gte", "fact": "<key>", "value": <literal>}
{"op": "in", "fact": "<key>", "value": [<literal>, ...]}
{"op": "exists", "fact": "<key>"}
{"op": "all|any|not", "children": [<node>, ...]}
```

Every node is an object and every child collection and `in` collection is a JSON array. Explicit nulls, missing required fields, unknown or irrelevant fields, executable forms, callbacks, named-rule references, and query objects are invalid. `lt/lte/gt/gte` support only integer and date Facts. `in`, `all`, and `any` require non-empty arrays; `not` requires exactly one child.

A date literal in a serialized rule has exactly the tagged shape `{"$date": "YYYY-MM-DD"}`. The value must be a valid, canonical, zero-padded Gregorian date and is decoded only for a date Fact. This storage-boundary decoding does not permit date-string coercion in submitted Facts: Fact input requires an actual typed calendar `date`.

`exists` tests whether a **source Fact key was submitted**. It does not test truthiness, non-empty value, or real-world existence inferred from another Fact.

Version 1 accepts at most **128 predicate nodes**, including the root, and at most **128 operands** in an `in` array. The 129th node produces `rule_too_large`; an oversized `in` produces an invalid-operand diagnostic without decoding entries beyond the limit. These are fixed non-semantic resource guards.

Validation diagnostics have the structured shape `{"code": <string>, "path": <segments>}`. In Python the path is an immutable tuple of string or integer segments. Fact paths begin `("facts", key)`. Rule paths begin `("rule",)`, child paths append `("children", index)`, and field or operand paths append the field name and, for an individual `in` value, its index. Diagnostics are deterministic, retain equal codes at distinct paths, and are deduplicated only when both code and path are identical.

Malformed serialized ASTs never produce a typed `Predicate`. Validation remains a distinct, mandatory stage; successful rule and Fact validation may feed the pure production evaluator. `None` is malformed serialized rule input. It never produces a predicate and is never interpreted by the evaluator as an always-true rule.

## Three-valued evaluation

The framework-independent production seam is exactly:

```python
def evaluate(
    predicate: Predicate,
    facts: Mapping[str, FactValue],
    *,
    submitted_keys: frozenset[str],
) -> Evaluation: ...
```

`predicate` is a non-optional result of successful `validate_rule_v1`; `facts` is a typed immutable mapping produced by successful Fact validation and any later derivation. Callers must explicitly capture `submitted_keys` from validated source Facts before derivation. It is not inferred from `facts`, because that mapping may contain derived Facts. Malformed rules and invalid Fact values produce structured validation diagnostics outside the truth-value domain and must not be evaluated.

Valid predicates evaluate under Strong Kleene logic to exactly `TRUE`, `FALSE`, or `UNKNOWN`. Comparisons against omitted Facts are `UNKNOWN`; `exists` is `TRUE` exactly when its source key is in `submitted_keys` and is otherwise `FALSE`.

`all` has the following exhaustive binary table (rows are left operands):

| `all` | TRUE | FALSE | UNKNOWN |
|---|---|---|---|
| **TRUE** | TRUE | FALSE | UNKNOWN |
| **FALSE** | FALSE | FALSE | FALSE |
| **UNKNOWN** | UNKNOWN | FALSE | UNKNOWN |

`any` has the following exhaustive binary table:

| `any` | TRUE | FALSE | UNKNOWN |
|---|---|---|---|
| **TRUE** | TRUE | TRUE | TRUE |
| **FALSE** | TRUE | FALSE | UNKNOWN |
| **UNKNOWN** | TRUE | UNKNOWN | UNKNOWN |

`not` maps TRUE to FALSE, FALSE to TRUE, and UNKNOWN to UNKNOWN. N-ary `all` is FALSE if any child is FALSE, TRUE if all are TRUE, and UNKNOWN otherwise. N-ary `any` is TRUE if any child is TRUE, FALSE if all are FALSE, and UNKNOWN otherwise.

Every authored boolean child is evaluated in tuple order without short-circuiting. Parent missing-Fact sets contain only missing Facts from UNKNOWN children that determine an UNKNOWN parent: `FALSE AND UNKNOWN` and `TRUE OR UNKNOWN` have empty parent sets, while `TRUE AND UNKNOWN` and `FALSE OR UNKNOWN` retain the consequential UNKNOWN sets. Sets are immutable and ordering is never derived from them.

Transient editor/test traces preserve every evaluated subtree, including dominated UNKNOWN nodes and their local missing sets and values. `affected_result=True` on an UNKNOWN marks a consequential unresolved branch; `False` marks an evaluated branch dominated by the enclosing result, and applies recursively to that entire subtree. Traces are not persisted, logged, sent to observability, or included in public planning/API DTOs. Evaluation itself performs no decoding, validation, derivation, orchestration, selection, persistence, framework, database, network, or filesystem work.

## Procedure selection

Planning begins from a Service and current Facts.

1. Evaluate the Service's curated stable Procedure-candidate predicates.
2. If a missing source Fact is consequential to choosing among candidate Procedures, ask its Service-owned Question.
3. Resolve one concrete Procedure or return an explicit unsupported/inconclusive result; never choose a closest match.
4. Resolve the published Procedure Version applicable on the evaluation date.
5. Evaluate that version's own applicability and rules.

Service-level selection predicates are version-independent. A current Procedure Version's applicability must not be copied into the stable Service selector.

## Procedure Version selection

- Effective intervals are inclusive.
- At most one published Procedure Version may apply to a Procedure on an evaluation date; overlap is invalid configuration.
- Future published versions may be exposed as upcoming but are not selected early.
- Drafts are never selected publicly.
- Withdrawn versions are excluded from new plans and may be addressed only by explicit historical evaluation.
- Published semantics are pinned to a rules-contract version.

## Eligibility Basis evaluation

Each Basis has reachability and qualification stages.

```text
evaluate reachability
    FALSE   -> Basis unreachable; do not inspect qualification for missing Facts
    UNKNOWN -> only reachability Facts may become consequential Questions
    TRUE    -> evaluate qualification
                  TRUE    -> matched Basis
                  FALSE   -> reachable but not matched
                  UNKNOWN -> qualification Facts may become consequential Questions
```

Every Basis has explicit qualification. A missing reachability predicate means always reachable.

All authored Bases are considered so multiple matches remain visible. The planner does not rank/recommend a legal Basis.

Trust is applied after factual matching: an untrusted matched Basis can be shown as a candidate/inconclusive alternative but cannot unlock Basis-scoped current guidance.

## Missing-Fact Picker

The system asks only source Facts that are consequential to a still-resolvable planning decision.

A Question is selected deterministically by authored priority and then stable Question identifier. If a consequential missing source Fact has no authored Question for the Service, knowledge is defective; the evaluator must not invent wording or silently assume a value.

Non-consequential UNKNOWNs remain unresolved. Routing UNKNOWN is explicitly local and does not block unrelated reliable plan material.

## Contradictions

Authored cross-Fact invariants may classify a submitted case as contradictory. Contradiction is invalid input, not UNKNOWN. Public diagnostics identify the conflicting source-Fact keys needed for correction without exposing an internal trace tree.

## Claim/step/fee applicability

Version-owned plan material is included only when its applicability is TRUE and its trust/evidence state allows that use.

A stale/disputed/unverified consequential item affects only dependent decisions. Reliable unrelated guidance remains available.

Established stale material may be shown only as dated historical context with the current value explicitly unknown. `needs_reverification`, `disputed`, and `unknown` material is not automatically relabeled as historical.

## Dependencies and routing

Version 1 supports one-level direct `blocking_prerequisite` Procedure dependencies. The evaluator identifies the target Procedure/Version when researched but does not recursively plan it. Blocking dependency cycles are invalid publication configuration.

Procedure-specific Service Point associations are evaluated independently from the rest of the plan. All applicable points may be returned. Unresolved routing remains local; no nearest-office/hidden recommendation is inferred.

## Public result family

One planning call returns exactly one discriminated result family:

- `next_question` — one deterministic source-Fact Question;
- `plan` — reliable personalized guidance plus explicit local uncertainty/current unknowns;
- `inconclusive` — safe reason when the requested route cannot be reliably completed;
- `invalid` — malformed knowledge/request or contradictory/invalid Facts.

Public results do not expose raw rule ASTs, raw Facts, full Evaluation Traces, Evidence Links, or editorial Evidence Discrepancy rationale.

## Compatibility rule

A published Procedure Version pins a rules-contract version. A future software release may add a new contract version, but it must retain compatible implementations required to reproduce published historical semantics. Changing a Fact's meaning requires a new Fact key rather than reinterpretation of old data.
