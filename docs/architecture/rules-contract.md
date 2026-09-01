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

Derived Facts are calculated before rule evaluation by the pinned rules-contract implementation. Rules consume Derived Facts but never define arbitrary formulas.

## Typed predicate AST

Authored rules are data, not code. The `v1` operator vocabulary is:

- leaf: `eq`, `in`, `lt`, `lte`, `gt`, `gte`, `exists`;
- boolean: `all`, `any`, `not`.

`lt/lte/gt/gte` are valid only for ordered Fact kinds supported by the contract, initially integer and date. `in` requires a non-empty collection of valid literals. `all` and `any` must be non-empty. `not` has exactly one child.

`exists` tests whether a **source Fact key was submitted**. It does not test truthiness, non-empty value, or real-world existence inferred from another Fact.

Rules may not contain executable text, callbacks, named-rule references, database queries, network calls, or hidden side effects.

The prototype validated a maximum of 128 nodes per rule; production `v1` must preserve an equivalent or stricter non-semantic resource guard without changing valid rule meaning.

## Three-valued evaluation

Valid predicates evaluate under strong Kleene logic to exactly `TRUE`, `FALSE`, or `UNKNOWN`.

Malformed rules and invalid Fact values are diagnostics outside the truth-value domain.

For editor/test inspection, pure child predicates are evaluated completely so traces can show dominated branches. `affected_result`/equivalent metadata distinguishes an UNKNOWN that mattered from one dominated by another branch.

## Procedure selection

Planning begins from a Goal and current Facts.

1. Evaluate the Goal's curated stable Procedure-candidate predicates.
2. If a missing source Fact is consequential to choosing among candidate Procedures, ask its Goal-owned Question.
3. Resolve one concrete Procedure or return an explicit unsupported/inconclusive result; never choose a closest match.
4. Resolve the published Procedure Version applicable on the evaluation date.
5. Evaluate that version's own applicability and rules.

Goal-level selection predicates are version-independent. A current Procedure Version's applicability must not be copied into the stable Goal selector.

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

A Question is selected deterministically by authored priority and then stable Question identifier. If a consequential missing source Fact has no authored Question for the Goal, knowledge is defective; the evaluator must not invent wording or silently assume a value.

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
