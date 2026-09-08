# ADR 0015: Ask consequential source Questions for Procedure Version applicability

**Status:** Accepted  
**Date:** 2026-09-07

## Context

ADR 0013 makes Service Questions available before and after Procedure selection. The planner
nevertheless stopped at UNKNOWN Procedure Version applicability, even when an authored Question
could collect its missing source Facts. Treating that omission as permanent inconclusiveness
prevents a supported case from progressing. Questions must not substitute user answers for
research, evidence, or the planner's applicability decision.

## Decision

After Procedure selection and temporal version resolution, UNKNOWN version applicability uses
the existing consequential Question selector. Only the evaluator's consequential missing Facts
participate. Derived Facts expand through the pinned source-dependency registry; the user is
never asked to supply a derived value, select a route, or certify evidence quality.

The shared Question policy is one `next_question` per stateless response, ordered by authored
priority then semantic identifier. Every answer key must exist and be non-derived. A partially
answered multi-Fact Question may recur while it covers a consequential missing source Fact; a
fully answered Question must not loop. Unknown Facts, unsupported/missing derivation dependencies,
or absent same-Service coverage produce the existing sanitized invalid knowledge-configuration
response. UNKNOWN with no actionable missing Facts retains the phase's inconclusive reason.
TRUE/FALSE behavior and the order of planning phases do not change.

Publication structurally requires same-Service source-Question coverage for version applicability,
using the existing dependency expansion and canonical publication locks. Coverage is independent
of today's date and research freshness; future-effective versions are not exempt. Every answer
key in a multi-Fact Question is checked, not just the key that happens to be consequential.
There is no bypass setting for this requirement.

Answers resolve factual applicability only. They cannot promote trust, assert an unavailable
amount, or resolve an Evidence Discrepancy. This decision introduces no new questioning behavior
for checklist items, steps, fees, Bases, dependencies, routing, or Procedure selection. Future
phase extensions must document their consequential/trust policy separately and preserve this
shared Question and configuration-defect policy.

## Compatibility and consequences

This extends ADR 0013 (using ADR 0014's Service terminology), without superseding ADR 0001's
pinned evaluator/derivation semantics or ADR 0003's publication immutability. It is an explicit
application-orchestration correction for existing `v1` contracts: predicates, Fact meanings,
derivations, truth values, version selection, and trust calculations are unchanged. No new
rules-contract version or data migration is introduced. Existing published versions use the
corrected Question policy too, including evaluations at historical dates. Thus the *response*
for an incomplete case may change from inconclusive to `next_question`; this is not a promise
to reproduce the former missing-Question behavior. Actual evaluator or derivation changes
still require the compatibility treatment in ADR 0001.

Existing published content lacking coverage now fails closed when the missing Fact becomes
consequential. Do not rewrite published or withdrawn rows to make it pass. Editorial remediation
must respect existing Service Question/answer-map protections and use a future draft/version
where protected semantics need changing. New publication attempts must pass coverage. Authored
production scenarios and importer integrity checks must remain coherent; any necessary upgrades
accept exact known draft states only, after other integrity checks, atomically, retaining review
invalidation and prior supported upgrade paths. Arbitrary drift and published-content rewrites
remain forbidden.

Keeping the unconditional inconclusive response was rejected because it defeats available
source Questions. Introducing new evaluator semantics was rejected because no evaluator behavior
changes. These choices intentionally distinguish application progression from pinned rule
meaning while making the externally observable compatibility change explicit.
