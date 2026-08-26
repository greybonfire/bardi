# Throwaway planning prototype

This directory implements the research prototype requested by issue #5. It is intentionally framework-independent and must not be treated as production backend code or imported into a future Django application.

## Scope of issue #5

The prototype establishes one stateless application seam:

```python
run_scenario(
    knowledge=...,
    goal_id=...,
    facts=...,
    locale=...,
    evaluation_date=...,
)
```

For the first slice it loads the researched passport-renewal fixture and executes one complete known case through deterministic derivation, Procedure applicability, claim/fee/step/Service Point assembly, evidence projection, and Arabic/English presentation.

The fixture deliberately retains the `passport.requirement.previous_passport` research claim as `needs_reverification`, while the planner projects only current claims. Standard-service turnaround remains an explicit unknown. The planner therefore demonstrates that unresolved research can exist in the knowledge bundle without being converted into current guidance.

## Deliberately deferred

Issues #6–#8 remain responsible for cross-Procedure selection, authored clarification Questions, strong-Kleene TRUE/FALSE/UNKNOWN evaluation, the Missing-Fact Picker, full typed input/rule validation, contradictory-case handling, and Evaluation Traces. The evaluator in this directory supports only the complete-input predicate subset needed for the known passport case and is expected to be replaced.

There is no Django, PostgreSQL, ORM, HTTP server, Next.js client, persistence layer, network access, system-clock dependency, random identifier generation, or raw-Fact logging.

## Run the tests

From the repository root:

```bash
python -m unittest discover -s prototype/tests -v
```

The tests cover the authored `passport.positive.adult_expired_standard` behavior, evidence-backed output, exclusion of the unresolved previous-passport claim, explicit unknown standard turnaround, bilingual semantic parity, deterministic replay, and absence of raw Facts from the result object.
