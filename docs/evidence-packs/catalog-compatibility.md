# I02 — Shared catalog-growth compatibility prerequisite

This is one technical prerequisite for the separate [passport](passport-suite/implementation.md)
and [National ID](national-id-suite/implementation.md) workstreams, not a shared administrative
research pack. Implement it once and link the accepted design/PR from both handoffs. Do not
create competing compatibility patches or require both content suites to ship together.

**Input:** [planning_behavior_signature](../../backend/knowledge/planning_scenarios.py),
[passport importer](../../backend/knowledge/importers/passport_renewal.py),
[National ID importer](../../backend/knowledge/importers/national_id_renewal.py), their strict
integrity verifiers, and accepted ADRs 0001/0003/0013–0018. The research baseline is
`e79bd4e5c3ca67fdc2785d00013ae86681f8e1be`; recheck current implementation before designing changes.

**Bound:** First produce a reviewed design/ADR and regression test defining scenario/import
compatibility when Service Questions or selection semantics grow. Implement that approved design
in its own PR with exact model/service/migration boundaries, not together with either whole suite.
This research PR does not select a new compatibility design or grant an exception.

At the research baseline the signature includes all Questions, resolved-Fact links and
contradictions under a Service, plus candidates for the version's own Procedure. Both renewal
integrity paths compare stored scenario signatures to the current signature. Adding another
candidate alone differs from adding a Service Question or editing the original candidate.

Decide how preserved evaluation context coexists with the current catalog, how successors obtain
their context, and which importer combinations are supported. Preserve tamper detection and make
supported additive imports repeatable. Do not refresh historical signatures, drop Questions
from hashing without an explicit contract, relax digest checks, or ignore conflicts. Genuinely
changed draft behavior must still invalidate publication approvals.

**Acceptance:** Exercise SC65–SC67 in each affected Service: both supported import orders,
repeat import, unrelated additive content, material mutation, published/draft versions and a
stored signature mismatch. Retain existing regressions and late-verification rollback. Exact
acceptance templates are in [passport scenarios](passport-suite/scenarios.md) and
[National ID scenarios](national-id-suite/scenarios.md).

Markdown retention is independent of these invariants. See the [retention decision](README.md):
Git preserves obsolete documentation, but cannot replace published database audit history.
A smaller implementation task starts only after this design is accepted, not by inventing
exceptions during content authoring. No deployment or production migration is authorized here.
