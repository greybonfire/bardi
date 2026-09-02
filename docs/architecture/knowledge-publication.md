# Knowledge publication and review

**Status:** Authoritative  
**Effective:** 2026-09-01

Publication turns researched/editable knowledge into an immutable Procedure Version that the public planner may select. Publication workflow state is intentionally separate from calculated evidence/trust state.

## Lifecycle

The initial Procedure-Version publication states are:

- `draft` — editable and never selected by the public planner;
- `published` — immutable public semantic snapshot, subject to effective dates and trust evaluation;
- `withdrawn` — unavailable for new plans but retained for explicit historical inspection/audit.

Future-effective published versions are permitted. At most one published version may be applicable to one Procedure on any evaluation date.

## Draft editing

Editors work on drafts through Django Admin initially.

A draft may be created from scratch or cloned from an existing published version. Cloning copies the coherent version-owned records into new editable draft records; it does not reopen the published version for mutation.

Stable identities such as Service, Procedure, Fact key, Document Type, Authority, Service Point, and Source remain shared where semantically appropriate.

## Publication is an explicit service operation

Publishing must execute through a transactional publication service. Setting a model field directly is not sufficient.

The service must:

1. lock/identify the draft being published and the relevant Procedure publication state;
2. run structural/rule/domain validation;
3. run evidence/trust/public-readiness validation;
4. verify required review/approval records;
5. validate effective-date non-overlap with other published versions;
6. persist the immutable published state atomically; and
7. record an audit event identifying the published version and approving actors.

A failed validation leaves the draft unpublished.

## Required publication validation

The production validator must cover at least the invariants proven or required by the prototype:

### Identity and ownership

- valid Service/Procedure ownership and curated Service–Procedure membership;
- stable/unique semantic identifiers within their scopes;
- Procedure-Version-owned material points to the containing version;
- basis-scoped claims/steps point to an existing Basis;
- Service Point associations point to valid versioned Service Point material.

### Rules and Facts

- every authored rule validates against the pinned rules-contract version;
- referenced Fact keys exist and have valid literal types;
- Eligibility Bases have explicit qualification and valid reachability rules;
- every consequential source Fact required by a Basis stage has an authored Service Question;
- blocking dependency cycles are rejected;
- overlapping published Procedure-Version or conflicting Service Point intervals are rejected.

### Evidence

- every current evidence-bearing administrative assertion has claim-specific Evidence Links;
- Evidence Links reference preserved Sources and carry sufficient passage/context metadata for review;
- Official Requirements rely on official-authority evidence rather than Field Reports alone;
- Field Reports require observation date and place/context before they may support Field Guidance;
- unresolved evidence discrepancies produce the configured local trust consequence rather than being silently ignored.

### Bilingual/public content

- required Arabic and English public text is complete;
- translations are reviewed as one coherent Procedure Version;
- public material does not expose internal discrepancy rationale or raw Evidence Link/editorial structures.

### Scenarios

Meaningful Procedure Versions must have named acceptance scenarios for consequential positive, negative, UNKNOWN, contradictory, and supported-edge behavior appropriate to that Procedure. High-risk changes require scenario updates before publication.

## Review requirements

Version 1 should record distinct review dimensions rather than one undifferentiated "approved" flag:

- evidence/source review;
- rule/logic review;
- scenario/behavior review;
- Arabic/English semantic review;
- discrepancy review when applicable.

A second person must approve meaning-changing publication. Specialist review is required for consequential legal eligibility, military status, custody/guardianship, contested identity, and similarly high-risk material.

The production schema may implement these as compact review/audit records; it does not require a generalized workflow engine.

## Evidence trust and freshness

Publication state answers "may this version be selected?" Trust answers "may this specific material be asserted now?"

The supported trust vocabulary remains:

- `current`;
- `needs_reverification`;
- `stale`;
- `disputed`;
- `unknown`.

Re-verification due dates and effective intervals are explicit calendar dates. Risk-based review intervals may differ by claim type; volatile fees/routing and consequential eligibility claims should be reviewed more aggressively than stable background material.

An untrusted consequential claim makes only dependent output inconclusive. It does not automatically suppress unrelated reliable content.

A `needs_reverification` or disputed value is not historical simply because it is old. Historical context requires evidence that the value was previously established, plus an item-level verification/effective date. Evidence retrieved after a historical evaluation date cannot be back-projected into that date's guidance.

## Source classifications and discrepancies

Sources retain classification such as `official`, `field_report`, or `secondary`.

Official-vs-Field Guidance disagreement does not demote official authority by relabeling the source. The discrepancy remains an internal record, and the affected claim's trust/public behavior expresses the consequence.

Do not introduce numeric confidence scores as a substitute for verification states and review rationale.

## Withdrawal

Withdrawal stops implicit/public selection for new plans but preserves the Procedure Version and its audit/evidence history. A withdrawn version may be used only when an explicit historical evaluation requests it and the evaluation date is coherent with its applicability.

Withdrawal is not deletion.

## Re-verification and successor versions

Research may update evidence without changing public meaning. If only internal verification metadata changes and the published semantic snapshot remains identical, the production design may record a re-verification event without rewriting the published semantic records.

Any change to public rules, claim meaning, applicability, amount, requirement status, routing condition, translation meaning, or public evidence interpretation creates a successor Procedure Version.

## Admin behavior

Django Admin is the initial editorial surface. It should make unsafe states difficult:

- published semantic records are read-only;
- "clone to draft" is explicit;
- validation errors point to the affected semantic item;
- source/evidence/discrepancy context is reviewable without appearing in public DTOs;
- publication/withdrawal actions are permission-controlled service operations;
- review and publication history is visible to staff.

A custom CMS may be introduced later only if Django Admin becomes a demonstrated bottleneck.

## Migrating the researched fixtures

The three evidence packs and frozen prototype fixtures are migration/reference inputs, not production runtime dependencies.

Production seeding should create real production records through supported import/fixture services and then validate them using the production publication validator. The migration should preserve stable semantic IDs where useful for acceptance parity, but should not preserve prototype-only compatibility aliases or test-only synthetic structures.
