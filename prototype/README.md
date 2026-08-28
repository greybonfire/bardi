# Throwaway planning prototype

This directory implements the research prototype from issues #5 onward. It is intentionally framework-independent and must not be treated as production backend code or imported into a future Django application.

## Application seams

The public prototype seam remains stateless and trace-free:

```python
run_scenario(
    knowledge=...,
    goal_id=...,
    facts=...,
    locale=...,
    evaluation_date=...,
)
```

Issue #8 adds a separate editor/research inspection seam over the same execution path:

```python
inspect_scenario(
    knowledge=...,
    goal_id=...,
    facts=...,
    locale=...,
    evaluation_date=...,
)
```

`inspect_scenario()` returns the exact same safe planning result plus ephemeral `RuleEvaluationRecord` objects. The full predicate tree, relevant Fact values, and editorial trace structure never appear on the public `PlanningResult` returned by `run_scenario()`.

Issue #5 established the first complete passport-renewal plan. Issue #6 added the cross-fixture `KnowledgeCatalog`. Issue #7 introduced the typed strong-Kleene evaluator and Missing-Fact Picker. Issue #8 completes the prototype diagnostic layer with authored cross-Fact contradictions and editor-facing Evaluation Traces.

The catalog loads the three researched fixtures: ordinary domestic passport renewal, ordinary domestic National ID renewal, and temporary family exemption from military service. Related but unresearched Procedures remain explicit `procedure_not_researched` outcomes rather than receiving closest-match guidance.

## Typed rules and Facts

The central `FactDefinition` registry strictly types source Facts as enums, integers, booleans, calendar dates, or strings. Derived Facts are valid rule operands but cannot be submitted by callers. Values are never coerced: numeric strings are not integers, integers are not booleans, date strings or datetimes are not calendar dates, `null`/`None` is invalid, and enum matching is exact.

The supported rule operators are typed equality (`eq`), finite membership (`in`), integer/date ordering (`lt`, `lte`, `gt`, `gte`), submitted-key existence (`exists`), and boolean composition (`all`, `any`, `not`). Rules are validated before evaluation. Unsupported operators/references, unsupported Fact keys, invalid operands, empty boolean compositions, malformed nodes, and rules exceeding the prototype node limit are invalid knowledge rather than FALSE or UNKNOWN.

## TRUE / FALSE / UNKNOWN

Omitted Facts evaluate as `UNKNOWN`; there is no generic null value. Boolean composition follows strong-Kleene semantics. A FALSE child makes `all(...)` FALSE even if another child is UNKNOWN, while a TRUE child makes `any(...)` TRUE even if another child is UNKNOWN. Those dominated UNKNOWN branches therefore do not influence the Missing-Fact Picker.

`exists(fact)` tests whether the source Fact key was submitted by the caller. A value generated later as a Derived Fact does not make `exists` true.

## Contradictory Cases

Type-valid Facts can still conflict with each other. Issue #8 represents those cases with small fixture-authored `ContradictionDefinition` records rather than hiding consistency assumptions in procedural code.

Contradictions are evaluated after strict Fact validation but before Procedure selection. A matched contradiction returns `InvalidResult("contradictory_facts")` with stable contradiction codes and only the conflicting source-Fact keys. It cannot produce a Plan or trigger another clarification Question.

The contradiction catalog is intentionally narrow. Normalized enum Facts already remove avoidable contradiction space; for example, a passport cannot simultaneously be `none` and `expired` because `existing_passport_state` is one enum. Current explicit invariants cover cases such as claiming no current National ID while also supplying that card's expiry date, and saying there is no missing relative while also supplying missing-relative-specific facts.

## Evaluation Traces

Every evaluated rule produces an `EvaluationTrace`. Boolean predicates evaluate **all** pure children, even when one child already determines the strong-Kleene result. The trace records:

- every predicate operator and TRUE/FALSE/UNKNOWN result;
- the relevant Fact key, whether it was present/submitted, and the ephemeral actual/expected values for leaf predicates;
- missing Facts on UNKNOWN branches;
- the complete child tree;
- whether each child branch affected its parent's final result.

For `FALSE AND UNKNOWN`, for example, the UNKNOWN child is still evaluated and visible to an editor, but it is marked `affected_result = False` and contributes no consequential missing Fact.

Scenario-level `RuleEvaluationRecord` objects also state whether a rule is consequential to planning. Claim/step/fee UNKNOWNs can block a Plan and drive the Missing-Fact Picker. Service Point and other deliberately local UNKNOWNs are traced but marked non-consequential, so reliable guidance remains available.

Evaluation Traces are ephemeral diagnostic objects. The prototype does not persist them, does not log raw Facts, and does not expose them through the public planning result.

## Missing-Fact Picker

Both Procedure selection and plan assembly surface only missing Facts that still affect the final result. The picker considers authored Questions for the active Goal, chooses the lowest numeric priority capable of resolving a consequential UNKNOWN, and breaks ties by stable Question ID.

Once a branch is determined by strong-Kleene dominance, omitted Facts on that branch stop being askable. For example, a passport applicant known to be under 19 does not need to answer the sex question merely because the military-document rule also references sex: the age predicate has already made that rule FALSE. The editor trace still shows that the sex predicate was evaluated as UNKNOWN and dominated by the age result.

If a consequential missing Fact has no authored Question, the result is inconclusive with a stable knowledge-configuration diagnostic rather than guessing. Unresolved Service Point applicability remains local and does not block otherwise-supported guidance.

## Fixture-specific safety behavior

The passport fixture continues to retain `passport.requirement.previous_passport` as `needs_reverification`, while public plans project only current claims. Standard-service turnaround remains unknown.

The National ID fixture keeps the current ordinary fee, previous-card requirement, ordinary turnaround, and exact office routing unresolved where the evidence pack did not establish them. It uses real calendar-month derivation for the statutory renewal deadline.

The military fixture remains conservative: the seam can identify the researched temporary-family-exemption Procedure, but the legal Basis candidate itself is not published as authoritative guidance before specialist review. Matching a researched route is not treated as a binding exemption decision.

## Prototype boundary

There is still no Django, PostgreSQL, ORM, HTTP server, Next.js client, persistence layer, network access, system-clock dependency, random identifier generation, or raw-Fact logging. The trace and contradiction structures exist to pressure-test the rules model; they are not a production observability architecture.

## Run the tests

From the repository root:

```bash
python -m unittest discover -s prototype/tests -v
```

The suite preserves the issue #5–#7 behavior and adds issue #8 coverage for type-invalid vs contradictory cases, conflict-key reporting, malformed-rule rejection, complete child traces, relevant inputs, dominated UNKNOWN branches, consequential Missing-Fact behavior, locally inconclusive Service Points, and the public/editor trace boundary.
