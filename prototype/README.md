# Throwaway planning prototype

This directory implements the research prototype from issues #5 onward. It is intentionally framework-independent and must not be treated as production backend code or imported into a future Django application.

## Application seams

The public seam remains stateless and trace-free:

```python
run_scenario(
    knowledge=...,
    goal_id=...,
    facts=...,
    locale=...,
    evaluation_date=...,
    generated_on=...,  # optional; defaults deterministically to evaluation_date
)
```

`inspect_scenario()` runs the same pipeline and adds ephemeral editor/research Evaluation Traces. Raw Facts and trace trees remain outside the public `PlanningResult`.

Issues #5–#8 established the first plan, cross-fixture Procedure selection, typed TRUE/FALSE/UNKNOWN rules, Missing-Fact selection, contradictions, and editor traces. Issue #9 makes the successful result a complete bilingual evidence-backed Personalized Plan while leaving Eligibility-Basis selection, dependencies, richer routing, and temporal trust/version selection to later tickets.

## Personalized Plan contract

A `PersonalizedPlan` now carries:

- stable Goal, Procedure, and Procedure Version identities;
- a flat checklist plus deterministic presentation groups;
- claim classification labels for Official Requirement vs Practical Preparation;
- per-item quantity, original quantity, copy quantity, Document Type grouping identity, shared/Basis scope, and optional Eligibility Basis ID;
- compact claim-derived Source summaries without exposing internal Evidence Link records;
- deterministically ordered steps using explicit `phase_order`, `slot`, and stable ID;
- structured fee states (`known`, `range`, `unknown`, `unverified`) without synthesized values;
- Service Points, warnings, and unresolved non-fee information;
- evaluation date, explicit generation date, Procedure Version verification date, and a dedicated regeneration warning.

Checklist grouping is presentation-only. Items are never unioned into a new semantic claim: grouped entries retain their own IDs, classifications, quantities, Basis scope, and evidence-derived sources.

## Evidence and publication safety

Fixture validation now rejects a current evidence-bearing checklist claim, material step, or current Service Point when its claim-specific Evidence Link is absent or broken. Known/range fees require evidence; unknown fees carry no invented amount. Unverified fees may preserve an evidenced historical/provisional value only when explicitly marked `needs_reverification`.

Administrative warnings require evidence. Product warnings—such as “regenerate before acting” and “this is guidance, not an authority decision”—do not require government evidence and never control plan flow.

Every fixture must provide complete Arabic and English text for public content. Both locales are part of one fixture/version structure and must preserve the same claim IDs, rule outcomes, quantities, fee states, ordering, and provenance identities. This structural check does not replace the independent human bilingual-review gate recorded in the evidence packs.

## Fixture-specific behavior

The passport fixture has current official checklist evidence, structured photo quantity, and the official “originals plus a copy” instruction represented as separate original/copy quantities. `passport.requirement.previous_passport` remains `needs_reverification` and is excluded from current guidance. The standard turnaround remains unknown.

The National ID fixture now represents the unresolved ordinary fee as a structured `unknown` fee rather than burying it in generic prose. The previous-card requirement, turnaround, and exact routing remain unresolved where the evidence pack did not establish them.

The military fixture likewise exposes its unresolved certificate fee as `unknown`. The shared supporting-document claim is current; the only-son legal Basis candidate is tagged as Basis-scoped metadata but remains `needs_reverification`, so it is still excluded from current authoritative checklist output pending specialist review.

No researched fixture currently has publishable Practical Preparation. Tests use synthetic fixture variants only to prove that Practical Preparation and shared/Basis-specific claims can be grouped without losing semantic identity or evidence; those test variants are not fixture guidance.

## Typed evaluation and diagnostics

Source Facts remain strictly typed; omission is UNKNOWN and null is invalid. Strong-Kleene rules, deterministic Missing-Fact selection, fixture-authored contradictions, and complete editor-facing Evaluation Traces remain unchanged from issues #7–#8. Local Service Point UNKNOWNs remain non-blocking.

## Prototype boundary

There is no Django, PostgreSQL, ORM, HTTP server, Next.js client, persistence layer, network access, implicit system clock, random identifier generation, or raw-Fact logging. Issue #9 does not implement Eligibility-Basis matching, Procedure Dependencies, version-selection history, or a production provenance/publication workflow.

## Run the tests

From the repository root:

```bash
python -m unittest discover -s prototype/tests -v
```

The suite includes the earlier #5–#8 behavior plus issue #9 coverage for evidence gates, checklist grouping and quantities, fee states, deterministic phase/slot ordering, bilingual semantic parity, explicit generation/verification dates, and the required regeneration warning.
