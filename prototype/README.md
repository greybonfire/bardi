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

Issues #5–#9 established Procedure selection, typed three-valued evaluation, deterministic missing-Fact questions, contradictions/traces, and bilingual evidence-backed Personalized Plans. Issue #10 completes the administrative route around a selected Procedure with Eligibility Basis alternatives, direct blocking dependencies, and Procedure-specific Service Point routing.

## Eligibility Bases

A Procedure may define zero or more `EligibilityBasisDefinition` records. When Bases exist, the planner evaluates every authored Basis so it can return all matching alternatives rather than stopping at the first TRUE rule. Consequential UNKNOWN Basis branches continue through the existing Missing-Fact Picker.

Matched Bases are ordered only for deterministic presentation; the planner does not recommend or rank one legal ground over another. Shared claims remain shared, while Basis-scoped claims and steps are added only for matched Basis IDs and retain their own semantic identities.

If all authored Bases are FALSE, the top-level result is `no_applicable_basis` with bilingual explanation and an evidence-backed official verification path. The planner does not substitute a closest-match Basis.

The military fixture encodes the six researched family-exemption candidate Bases from its evidence pack. Their `needs_reverification` state remains visible and the product warning still states that a planner match is not an exemption decision. Basis-specific candidate legal claims are not promoted to current authoritative checklist guidance before specialist review.

## Direct Procedure Dependencies

`ProcedureDependencyDefinition` currently supports only the researched contract shape `blocking_prerequisite`. A dependency has its own applicability rule, a `satisfied_when` rule, claim-specific evidence, and a safe verification path.

The planner evaluates only the direct dependency edge. If the target Procedure exists in the current research catalog, the plan can identify its Procedure Version without recursively planning the target. If the target is unresearched, the dependency is returned as `unsupported_target` with its stable target ID, user-facing name, and verification path rather than inventing a plan.

Current researched fixtures assert no real direct blocking dependency, matching the evidence packs. Synthetic tests exercise supported and unsupported targets and verify that blocking dependency cycles are invalid catalog configuration.

## Procedure-specific Service Point routing

A Service Point is now a stable identity. Material details such as address and availability live on `ServicePointVersionDefinition`, while case-dependent routing lives on sourced `ProcedureServicePointAssociationDefinition` records owned by the Procedure Version.

Associations and material detail versions can carry applicability intervals. Fixture validation rejects invalid intervals, overlapping current detail versions for the same Service Point, missing evidence, broken references, or association ownership that does not match the containing Procedure Version.

Routing evaluates all applicable associations and returns all matches; there is no nearest-office or hidden recommendation. The routing section is explicitly local:

- `resolved`: one or more points resolved and no current association remains UNKNOWN;
- `partially_resolved`: points resolved while another current association remains locally UNKNOWN;
- `unresolved`: no point resolves.

An unresolved route does not remove reliable checklist items, fees, warnings, or steps. It carries the unresolved association IDs/Facts and an evidence-backed verification path. The legacy flat `plan.service_points` projection remains for compatibility and mirrors the resolved points in `plan.routing`.

The passport fixture moves its Giza jurisdiction rule from the Service Point itself onto a sourced passport-renewal association. The National ID fixture keeps exact routing unresolved and supplies a Civil Status directory verification path. The military fixture models researched Giza, Mansoura, and Zagazig recruitment-region associations from the official region directory.

## Personalized Plan and evidence contract

The issue #9 plan behavior remains intact: checklist grouping never merges semantic claims; Official Requirements and Practical Preparation remain visibly distinct; fee values use explicit known/range/unknown/unverified states; steps use deterministic phase/slot order; and public provenance is compact Source metadata derived from internal claim-specific Evidence Links.

Source Facts remain strictly typed; omission is UNKNOWN and null is invalid. Strong-Kleene rules, deterministic Missing-Fact selection, fixture-authored contradictions, and complete editor-facing Evaluation Traces remain unchanged. Routing UNKNOWNs are deliberately non-consequential while Basis and dependency UNKNOWNs can still drive Questions.

## Prototype boundary

There is no Django, PostgreSQL, ORM, HTTP server, Next.js client, persistence layer, network access, implicit system clock, random identifier generation, or raw-Fact logging.

Issue #10 does not implement the generalized Procedure-Version freshness/trust behavior in #11. Service Point detail/association dates exist only because routing itself requires date-applicable material details. Future/withdrawn Procedure Versions, stale/disputed claims, and publication-state versus calculated-trust behavior remain deferred.

## Run the tests

From the repository root:

```bash
python -m unittest discover -s prototype/tests -v
```

The suite includes the earlier #5–#9 behavior plus issue #10 scenarios for exhaustive Basis alternatives, no-applicable-basis handling, additive Basis claims, one-level dependency resolution, unsupported dependency targets, blocking-cycle rejection, multiple Service Point matches, local routing uncertainty, and date-specific Service Point details.
