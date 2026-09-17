# Knowledge publication and review

**Status:** Authoritative  
**Effective:** 2026-09-01

Publication turns researched/editable knowledge into an immutable Procedure Version that the
public planner may select. Publication workflow is separate from calculated evidence/trust state.
This document owns lifecycle and publication gates; [review roles](procedure-version-review-roles.md)
and [safe Admin lifecycle](django-admin-lifecycle.md) define the detailed review and adapter contracts.
[Backend architecture](production-backend.md#snapshot-composition) owns request-time snapshot loading.

## Lifecycle

- `draft` — editable and never selected by the public planner;
- `published` — immutable public semantic snapshot, subject to effective dates and trust evaluation;
- `withdrawn` — unavailable for new plans but retained for explicit historical inspection/audit.

Future-effective published versions are permitted. At most one published version may be applicable
to one Procedure on any evaluation date. Inclusive date resolution, model guards and database
immutability triggers enforce the lifecycle; ordinary model/Admin writes cannot transition state
or alter published semantics.

## Draft editing

Editors use Django Admin, deterministic research importers, or the versioned draft-pack services.
A draft may be created from scratch or cloned from a published version into new editable records;
cloning never reopens published material. Stable Service, Procedure, Fact, Document Type, Authority,
Service Point and Source identities remain shared where semantically appropriate.

Import, verification, review, publication and Service activation are separate operations. See
[draft-pack instructions](../draft-packs/README.md) for authoring and
[Admin successor cloning](django-admin-lifecycle.md#draft-authoring-and-successor-cloning) for
copied content and history boundaries.

## Publication is an explicit service operation

Publishing runs through the canonical transactional service, never direct model-field assignment.
It must:

1. lock the draft aggregate and relevant Procedure publication state;
2. run structural/rule/domain and evidence/trust/public-readiness validation;
3. verify required reviews and effective-date non-overlap;
4. persist immutable published state; and
5. atomically record the actor, applied review mode and only the actual eligible approvals consumed.

Failure leaves the draft unpublished. Non-replaceable core gates run before every configured gate
in `PROCEDURE_VERSION_PUBLICATION_GATES`; missing, duplicate, malformed or raising configured gates
fail closed. Production registers evidence/discrepancy, scenario, mode-aware review and specialist
validation through this same path.

Publication locks the selected candidate, Service Questions and resolved-Fact links so coverage
gates and review signatures cannot race editorial changes. Selection-Question coverage precedes
scenario and review gates. Procedure selection remains independent of date/version applicability;
orchestration resolves the selected Procedure's version separately.

Claim aggregates, Evidence Links and Source joins, preserved Sources, Authorities and Document
Types are locked in deterministic order. Shared provenance and published/withdrawn aggregates
remain protected by model guards and database triggers.

## Required publication validation

### Identity and ownership

- valid Service/Procedure ownership and curated Service–Procedure membership;
- stable/unique semantic identifiers within their scopes;
- version-owned material points to its containing Procedure Version;
- Basis-scoped claims/steps point to an existing Basis;
- claim temporal/order metadata is valid, including deterministic Step/Warning ordering;
- Service Point associations point to valid versioned material.

### Rules and Facts

- every authored rule validates against the pinned rules-contract version and existing typed Facts;
- Procedure Version applicability has structural same-Service source-Question coverage, expanding
  Derived Facts through pinned source dependencies, including future-effective versions;
- official checklist, supported Step and Fee predicates in procedure/Basis scopes have the same
  structural coverage (ADRs 0016 and 0017), including future/non-current material; Fee coverage is
  independent of value state, evidence, freshness, current date and runtime Basis matching;
- every Question answer key exists and is non-derived, including every multi-Fact answer;
  applicability coverage remains mandatory when selection coverage is disabled;
- Eligibility Bases have required qualification and valid optional reachability, with authored
  Service Questions for consequential source Facts in both stages;
- blocking dependency cycles, overlapping published versions and conflicting Service Point
  intervals are rejected.

### Evidence

- current administrative assertions have claim-specific Evidence Links with preserved Sources,
  exact passages and sufficient location/applicability context;
- Official Requirements require wholly official supporting links, not Field Reports alone;
- Field Reports require observation date and place/context before supporting Field Guidance;
- current support is checked for contradictions as well as evidence quality;
- unresolved discrepancies have explicit local trust consequences, never silent omission.

### Bilingual/public content

- required Arabic and English text is complete and reviewed as one coherent version;
- public DTOs expose compact Source/freshness metadata, not passages, evidence locations,
  applicability context, support flags, internal discrepancy rationale or editorial structures;
- current Steps and administrative Warnings require current supporting evidence; product Warnings
  prohibit Evidence Links, and every published version has exactly one important product
  regeneration warning.

### Scenarios

Meaningful versions require named acceptance scenarios for consequential positive, negative,
UNKNOWN, contradictory and supported-edge behavior appropriate to the Procedure. High-risk changes
require scenario updates before publication.

## Review requirements

[ADR 0019](../adr/0019-use-explicit-solo-and-independent-publication-review-modes.md) and the
[review role contract](procedure-version-review-roles.md) govern `solo` and `independent` modes,
authorship, fresh signature-bound approvals, permissions and audit capture. There is no production
review-off mode. Both modes require truthful risk flags and independent specialists for configured
risks; high-risk material stays unpublished without a real specialist. Never clear or omit flags
to evade review. All non-review publication gates remain mandatory.

Mode changes affect future publication attempts, never historical snapshots or audit claims.
Compact review/audit records suffice; no generalized workflow engine is required.

## Evidence trust and freshness

Publication state answers “may this version be selected?” Trust answers “may this material be
asserted on the evaluation date?” The shared pure trust decision uses five states:
`current`, `needs_reverification`, `stale`, `disputed`, `unknown`. It yields current guidance,
established dated context, or local inconclusiveness.

Effective and re-verification boundaries are inclusive calendar dates. Future verification or
retrieval cannot support an earlier evaluation. Dated context requires prior item-level verification;
a formerly current item also needs an explicit effective end established no later than the period
it describes. `needs_reverification` or disputed material is not historical merely because it is old.
Risk-based intervals may differ: volatile fees/routing and consequential eligibility deserve more
frequent review than stable background material.

Untrusted consequential claims affect only dependent output. Applicable untrusted Official
Requirements make Checklist output locally inconclusive; unavailable Practical Preparation is
omitted. Steps and Warnings are deterministically ordered, with local temporal/trust/support failures
omitting the affected item, not unrelated reliable guidance. UNKNOWN applicability progression and
blocked uncertainty follow the [rules contract](rules-contract.md) and ADRs 0015–0017; an uncertain
official item or supported Step must not silently become an apparently complete plan.

## Source classifications and discrepancies

Sources retain `official`, `field_report` or `secondary` classification. Official-vs-Field Guidance
disagreement does not demote official authority by relabeling the Source. The discrepancy stays
internal; affected trust/public behavior expresses its consequence. Numeric confidence scores are
not substitutes for verification states and review rationale.

## Withdrawal

Withdrawal stops implicit/public selection but preserves the version and audit/evidence history.
A withdrawn version may be used only through an explicit historical request with a coherent
applicability date. Withdrawal is not deletion.

## Re-verification and successor versions

Semantic-preserving internal verification changes may be recorded as re-verification events,
without rewriting published semantic records. Date-aware snapshots apply only history established
by the evaluation date; see [trust projection](production-backend.md#date-aware-evidence-trust-projection).

Changes to public rules, claim meaning, applicability, amount, requirement status, routing condition,
translation meaning or public evidence interpretation require a successor Procedure Version.

## Admin behavior

The [safe Admin lifecycle](django-admin-lifecycle.md) owns permissions, service-backed actions,
read-only finalized material, cloning, staff-only history/context and item-specific diagnostics.
Readiness is advisory and previews do not approve, publish, activate or reseal. The adapter's
rollback, upload privacy, confirmation and preview failure contracts apply without a second
publication path. A custom CMS is justified only by a demonstrated Admin bottleneck.

## Production import lifecycle

Supported importers author or verify drafts, never manufacture users, approvals, publisher identity
or publication dates. Deterministic research importers return identical drafts or verify finalized
identities and reject semantic conflicts.

### Generic draft-pack import/export

The following contract applies only to generic draft packs, not deterministic research importers.
Packs use ADR 0020's explicit draft-target/revision contract;
[operator instructions](../draft-packs/README.md) own the how-to.

Owned arrays are complete desired snapshots with explicit deletion consent. Shared records are
create-or-exact-compare; initial Service setup is allowed only for a Service created in that same
transaction, never an existing Service even inactive. New Services/Facts remain inactive/unpublished.

Unchanged rows, authors and approval/audit history are preserved. Claim/evidence changes reset
related trust, including Basis-scoped dependents; version semantic changes conservatively reset
owned aggregate trust. Owners with discrepancy/re-verification history cannot be edited or deleted:
old temporal overlays must not be applied to new meaning. Use a successor or supported manual path.
Imports cannot clear existing risks or manufacture verification/approval. Unchanged scenarios retain
seals that may become stale; explicit human review/resave in Admin is required, not identical reimport.

Coherent imports/exports and complete-live-state revisions use short fixed knowledge-table locks;
conflicts are retryable `concurrent_edit`. Hash receipts prove only unchanged exact retries and
store no raw uploaded pack. See [authoring transport](production-backend.md#draft-authoring-transport)
for the architectural concurrency boundary and [Admin lifecycle](django-admin-lifecycle.md) for the
adapter contract. Actual publication always reruns canonical locked validation and audit capture.

### Passport applicability Question compatibility

The passport importer accepts only the current scenario seal and exact legacy, pre-checklist-Question
and pre-Fee-Question seals. After planning-signature, research, trust, evidence and review-policy
checks pass, eligible drafts receive all missing historical routing/student updates and the Fee
scenario atomically through normal saves. Both direct and sequential upgrades end at the current
seal: `passport.student.unknown` expects `next_question` for `q.is_student`, and
`passport.fee.service_level_unknown` expects `next_question` for bilingual `q.service_level`.

Changed scenarios invalidate review signatures; fresh mode-required approvals remain necessary.
Exact prior published/withdrawn seals are verifiable but never rewritten. Missing, partial or
arbitrary drift is rejected without partial upgrades. Fresh imports use current expectations.
This compatibility path changes no claims, Fee predicates/values, evidence, lifecycle state,
publication history or pinned rules-contract semantics.

## Migrating the researched fixtures

The three evidence packs remain research/reference inputs; the retired prototype exists only in
Git history, not as a runtime dependency. Production importers create real records validated by
production publication gates. Stable semantic IDs support acceptance parity, without importing
prototype-only aliases or test-only synthetic structures into production knowledge.

## Routing publication gate

Publication locks associations, stable points, material versions, both evidence-owner sets, Source
joins, Sources and Authorities deterministically. The gate rejects implicit ownership, malformed
published-Fact rules, incomplete bilingual identity/address, unsupported availability,
unordered/overlapping current material, invalid verification metadata, incomplete support,
current contradictions and malformed Field Report provenance. Routing Facts need not have Service
Questions: routing uncertainty remains local and non-consequential.
