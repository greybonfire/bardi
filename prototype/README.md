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

Issue #5 established the first complete passport-renewal plan. Issue #6 adds a `KnowledgeCatalog` in front of the same seam so a broad stable Goal can resolve to one concrete Procedure before that Procedure's existing plan assembler runs.

The catalog currently loads the three researched fixtures:

- ordinary domestic passport renewal;
- ordinary domestic National ID renewal;
- temporary family exemption from military service.

It may also name related but unresearched Procedure candidates, such as first passport issuance or lost/damaged replacement. If one of those is selected, the result is explicitly inconclusive with `procedure_not_researched`; the prototype never substitutes a researched neighbor's requirements.

## Procedure selection in issue #6

Procedure selection is generic and fixture-agnostic. Each Goal supplies candidate Procedure predicates plus authored one-Fact Questions. The temporary selector classifies each candidate as:

- `match` — all required selection Facts currently establish the candidate;
- `no_match` — at least one supplied Fact eliminates it;
- `possible` — omitted Facts still prevent a deterministic decision.

When more than one candidate remains possible, the selector chooses the lowest-priority authored Question that resolves one of the consequential missing selection Facts. Ties are broken by stable Question ID. If no authored Question can obtain a required distinguishing Fact, the seam returns `procedure_selection_configuration_defect` with stable diagnostic codes.

This partial matcher is intentionally limited to **Procedure selection**. It is not the final rules engine and is expected to be subsumed by #7's typed strong-Kleene evaluator and general Missing-Fact Picker.

## Fixture-specific safety behavior

The passport fixture continues to retain `passport.requirement.previous_passport` as `needs_reverification`, while public plans project only current claims. Standard-service turnaround remains unknown.

The National ID fixture keeps the current ordinary fee, previous-card requirement, ordinary turnaround, and exact office routing unresolved where the evidence pack did not establish them. It adds deterministic three-calendar-month derivation for the statutory renewal deadline rather than converting the rule to a fixed number of days.

The military fixture is intentionally conservative: the scenario seam can identify the researched temporary-family-exemption Procedure, but the legal Basis candidate itself is not published as authoritative guidance before specialist review. The plan exposes shared operational guidance and explicitly states that matching a researched route is not a binding exemption decision.

## Deliberately deferred

Issue #7 remains responsible for the final typed rule contract, general TRUE/FALSE/UNKNOWN semantics, `exists`, input/rule validation, and the Missing-Fact Picker. Issue #8 remains responsible for full invalid/contradictory diagnostics and editor-facing Evaluation Traces.

There is no Django, PostgreSQL, ORM, HTTP server, Next.js client, persistence layer, network access, system-clock dependency, random identifier generation, or raw-Fact logging.

## Run the tests

From the repository root:

```bash
python -m unittest discover -s prototype/tests -v
```

The suite preserves the issue #5 passport known-case tests and adds cross-fixture coverage for National ID and military planning, deterministic authored Question selection, bilingual Question projection, stable Goal identity across related Procedures, explicit unsupported-Procedure handling, and the missing-Question configuration defect.
