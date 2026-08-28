# Throwaway planning prototype

This directory implements the research prototype from issues #5 onward. It is intentionally framework-independent and must not be treated as production backend code or imported into a future Django application.

## Application seam

The prototype exposes one stateless application seam:

```python
run_scenario(
    knowledge=...,
    goal_id=...,
    facts=...,
    locale=...,
    evaluation_date=...,
)
```

Issue #5 established the first complete passport-renewal plan. Issue #6 added the cross-fixture `KnowledgeCatalog`. Issue #7 replaces the temporary selection matcher with one typed three-valued rule evaluator used for both Procedure selection and Procedure-owned plan applicability.

The catalog loads the three researched fixtures: ordinary domestic passport renewal, ordinary domestic National ID renewal, and temporary family exemption from military service. Related but unresearched Procedures remain explicit `procedure_not_researched` outcomes rather than receiving closest-match guidance.

## Typed rules and Facts

The #7 contract has a central `FactDefinition` registry. Source Facts are strictly typed as enums, integers, booleans, calendar dates, or strings; derived Facts are valid rule operands but cannot be submitted by callers. Values are never coerced: numeric strings are not integers, integers are not booleans, date strings are not calendar dates, `null`/`None` is invalid, and enum matching is exact.

The supported rule operators are:

- typed equality: `eq`;
- finite membership: `in`;
- integer/date ordering: `lt`, `lte`, `gt`, `gte`;
- submitted-key existence: `exists`;
- boolean composition: `all`, `any`, `not`.

Rules are validated before evaluation. Unsupported operators/references, unsupported Fact keys, invalid operands, empty `all`/`any`, malformed `not`, and rules exceeding the prototype node limit are rejected as invalid knowledge rather than becoming FALSE or UNKNOWN.

## TRUE / FALSE / UNKNOWN

Omitted Facts evaluate as `UNKNOWN`; there is no generic null value. Boolean composition follows strong-Kleene semantics. A FALSE child makes `all(...)` FALSE even if another child is UNKNOWN, while a TRUE child makes `any(...)` TRUE even if another child is UNKNOWN. Those dominated UNKNOWN branches are therefore non-consequential and do not trigger questions.

`exists(fact)` is deliberately different: it tests whether the source Fact key was submitted by the caller. A value generated later as a Derived Fact does not make `exists` true.

## Missing-Fact Picker

Both Procedure selection and plan assembly surface the missing Facts that still affect the final result. The picker considers authored Questions for the active Goal, chooses the lowest numeric priority that can resolve a consequential UNKNOWN, and breaks ties by stable Question ID.

Once a branch is already determined by strong-Kleene dominance, omitted Facts on that branch stop being askable. For example, a passport applicant known to be under 19 does not need to answer the sex question merely because the military-document rule also references sex: the age predicate has already made that rule FALSE.

If a consequential missing Fact has no authored Question, the result is inconclusive with a stable knowledge-configuration diagnostic rather than guessing. Unresolved Service Point applicability remains local and does not block otherwise-supported guidance.

## Fixture-specific safety behavior

The passport fixture continues to retain `passport.requirement.previous_passport` as `needs_reverification`, while public plans project only current claims. Standard-service turnaround remains unknown.

The National ID fixture keeps the current ordinary fee, previous-card requirement, ordinary turnaround, and exact office routing unresolved where the evidence pack did not establish them. It uses real calendar-month derivation for the statutory renewal deadline.

The military fixture remains conservative: the seam can identify the researched temporary-family-exemption Procedure, but the legal Basis candidate itself is not published as authoritative guidance before specialist review. Matching a researched route is not treated as a binding exemption decision.

## Deliberately deferred

Issue #8 remains responsible for richer invalid/contradictory-case diagnostics and editor-facing Evaluation Traces. The #7 evaluator already keeps invalid rules/values separate from TRUE/FALSE/UNKNOWN, but it does not expose a public or editor-facing predicate tree.

There is no Django, PostgreSQL, ORM, HTTP server, Next.js client, persistence layer, network access, system-clock dependency, random identifier generation, or raw-Fact logging.

## Run the tests

From the repository root:

```bash
python -m unittest discover -s prototype/tests -v
```

The suite preserves the issue #5/#6 behavior and adds coverage for typed input rejection, rule validation, `exists`, strong-Kleene dominance, consequential Missing-Fact selection, deterministic priority/ID tie-breaking, and plan generation once all consequential branches are resolved.
