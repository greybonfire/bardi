# Knowledge publication and review

**Status:** Authoritative  
**Effective:** 2026-09-01

Publication turns researched/editable knowledge into an immutable Procedure Version that the public planner may select. Publication workflow state is intentionally separate from calculated evidence/trust state.

## Implementation status: issue #36

The Procedure-Version persistence, inclusive effective-date resolver, database immutability
triggers, and canonical atomic publish/withdraw services are implemented. Publication runs a
non-replaceable set of core structural gates and then every gate in the application-level
`PROCEDURE_VERSION_PUBLICATION_GATES` registry. Missing, duplicate, malformed, or raising
configured gates fail closed. Ordinary model and Admin writes cannot perform lifecycle
transitions or alter published semantics; successful transitions record the actor and an
immutable audit event in the same transaction.

Production registers the evidence/discrepancy, scenario, mode-aware review, and
specialist-review gates through this canonical publication path. Procedure-selection Question
coverage is checked before scenario and review gates. Publication locks the selected candidate,
Service Questions and their resolved-Fact links so gate results and review signatures cannot
race editorial changes. Procedure selection remains independent of date and version
applicability; orchestration resolves the selected Procedure separately.

Issue #37's full request snapshot materializes all Fact definitions, Services (including inactive
ones), candidates, Questions, contradictions, and published/withdrawn Procedure Versions in
one coherent read-only transaction. Draft versions remain excluded. Public DTO projection is
a separate whitelist boundary: availability in the internal snapshot does not make rule ASTs,
raw Facts, traces, Evidence Links, discrepancy rationale, or publication actors public.

The public planning operation uses a separate service-scoped repeatable-read loader. It retains
the complete Fact-definition registry and runs the existing global request-time integrity
ledger as scalar validation-only reads, but materializes only the requested Service, its
Questions/candidates/contradictions, published or withdrawn versions, transitive blocking
Procedure dependencies, version-owned guidance, evidence, and routing graph. Dependency
closure is discovered in batched Procedure frontiers and cycles terminate without changing
planner recursion policy. Temporal discrepancy transitions and semantic-preserving
re-verification events are filtered to evidence owners in that graph while preserving all
historical events needed for as-of reconstruction, including the same owner-resolution
failure checks for visible workflow history as the full loader. The scoped loader is wired only
to `execute_planning`; full loaders remain the API for callers that require the complete
catalog. The validation/materialization boundary is intentional: the complete Fact registry,
published rule decoding, evidence/source presence, basis/dependency/routing integrity,
contradiction and question Fact reachability, and visible workflow owner resolution remain
global validation-only reads; Service DTOs, graph features, and as-of workflow overlays are
scoped. Both consistent loaders reject an already-open transaction and establish an outermost
PostgreSQL `REPEATABLE READ, READ ONLY` transaction before any discovery or materialization.

### Shared request-time validation policy

`knowledge.snapshot_policy` owns the request-time decisions for the four existing stages:
core material, Eligibility Bases, Procedure Dependencies, and Service Point routing. Its
validators accept captured, typed plain rows, explicit Fact definitions, and lightweight
Evidence Link summaries. They return decoded rules keyed by structural identity or raise
`KnowledgeSnapshotLoadError`, still available from `knowledge.domain`. Diagnostic owner text
is not an identity key; owner sorting and same-owner diagnostic order remain unchanged.

The full materializers validate their existing captured rows before constructing each stage's
claim DTOs. `knowledge.snapshot_validation` retains global scalar acquisition for scoped
loads, calling the same policy. This shares decision trees, not read strategies: scoped loads
intentionally repeat selected checks after global validation. Neither path adds a global
preflight to full loading or changes transaction policy. Stage order remains core → Bases →
Dependencies → routing, with failure in one stage preventing later stages from running.

Core and routing Evidence Link owner precedence remain distinct; Basis and dependency reverse
relations remain independent. Workflow owner resolution and temporal overlays stay outside
this policy, as do publication-only gates. Preserved legacy edge cases are tracked separately
in [`../operations/snapshot-validation-follow-ups.md`](../operations/snapshot-validation-follow-ups.md).

The policy interfaces have database-free tests:

```bash
(cd backend && uv run python -m unittest \
  knowledge.tests.test_snapshot_policy knowledge.tests.test_snapshot_feature_policy -v)
```

Loader tests continue to cover PostgreSQL acquisition, global fail-closed behavior, scoped
graphs, detached DTOs, transaction isolation, historical overlays, and exact diagnostics.

### Date-aware evidence trust projection

`knowledge.evidence_trust_projection.project_evidence_trust(snapshot, ordered_history)` owns
pure temporal replay and detached-snapshot rewriting. Plain discrepancy-transition and
re-verification records carry structural owner identities, not ORM objects or editorial
rationale. Private overlay state, open-discrepancy precedence, verification-date handling,
and all eight claim/material projections have one implementation. Authored values, rules,
text, and provenance content remain unchanged.

`knowledge.evidence_workflow_temporal` retains the PostgreSQL adapter and existing public
loaders. It filters history by evaluation date and optional Evidence Link scope, eagerly reads
transitions then reviews, and orders the combined timeline by timestamp, discrepancy before
review, then within-kind primary key. Date admission retains PostgreSQL's active-timezone
calendar semantics; the pure function does not repeat this filtering in Python.

After both reads finish, the adapter resolves each preloaded workflow owner and yields its
record for immediate replay before resolving the next owner. Consuming the returned history
eagerly would change that failure sequence. The pure function consumes it once, without
sorting again or discarding owners absent from the snapshot. Workflow ownership precedence,
global visible-owner validation, transaction policy, models, signals, and editorial writes
remain unchanged. Generic semantic loaders still apply no workflow projection; there is no
alternative latest-state projection path.

Pure snapshot-outcome tests replace private-overlay tests and run without Django settings or
a database:

```bash
(cd backend && uv run python -m unittest knowledge.tests.test_evidence_trust_projection -v)
```

PostgreSQL tests retain persisted historical outcomes, scoped acquisition, publication/privacy
checks, and lock/transaction behavior. Characterization also pins timestamp ties, active-timezone
cutoffs, and history-read/owner-resolution order. Preserved compatibility observations are
tracked separately in
[`../operations/evidence-projection-follow-ups.md`](../operations/evidence-projection-follow-ups.md).

## Implementation status: issue #40

Checklist provenance is implemented relationally: Authorities, Document Types, and preserved
Sources are reusable identities, while Checklist Items and their claim-specific Evidence Links
remain owned by exactly one Procedure Version. The canonical publisher now locks and validates
the complete evidence aggregate. Current claims require passage/context and Sources; Official
Requirements require wholly official supporting links, and Field Guidance rejects incomplete
Field Report observation provenance.

Detached planning snapshots retain that ownership boundary. Planning evaluates claim rules with
three-valued semantics and consumes the shared trust/freshness assessment, asserting only TRUE,
current public classifications. Inconclusive trust on an applicable Official Requirement makes
only Checklist output inconclusive; unavailable Practical Preparation is omitted. Public
responses use an explicit compact Source/freshness projection and never expose passages,
evidence locations, applicability context, support flags, or other editorial Evidence Link
structures. The retired research prototype is preserved only in Git history and is not a
production dependency.

## Implementation status: issue #55

The framework-independent planning domain exposes one pure trust decision API and the five-state
vocabulary below. Its explicit-date calculation returns one of three planner-facing decisions:
assert as current guidance, retain only as established dated context, or make dependent output
locally inconclusive. Effective and re-verification boundaries are inclusive. Future verification
or retrieval cannot support an earlier evaluation. Dated context requires prior item-level
verification; a formerly current item must also have an explicit effective end established no
later than the period it describes.

## Lifecycle

The initial Procedure-Version publication states are:

- `draft` — editable and never selected by the public planner;
- `published` — immutable public semantic snapshot, subject to effective dates and trust evaluation;
- `withdrawn` — unavailable for new plans but retained for explicit historical inspection/audit.

Future-effective published versions are permitted. At most one published version may be applicable to one Procedure on any evaluation date.

## Draft editing

Editors work on drafts through Django Admin, deterministic research importers, or the
[versioned draft-pack CLI](../draft-packs/README.md). Generic pack import is authoring only,
not publication preview or verification; PR3 Admin pack-upload/preview is not implemented.

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
7. record an audit event identifying the published version, applied review mode, and only the
   actual eligible approvals consumed by that mode (see review requirements below).

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
- Procedure Version applicability has structural same-Service Question coverage, expanding
  derived Facts through pinned source dependencies, including future-effective versions;
- official checklist, supported step, and Fee applicability predicates in procedure/basis scopes
  have the same structural source-Question coverage, including future/non-current material
  (ADRs 0016 and 0017); Fee coverage is independent of monetary value state, evidence, freshness,
  current date, and runtime Basis matching;
- every Question answer key exists and is non-derived, including all multi-Fact answers;
  version-applicability coverage is mandatory even when selection coverage is disabled;
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

[ADR 0019](../adr/0019-use-explicit-solo-and-independent-publication-review-modes.md) replaces the
blanket second-person requirement with deployment-wide `PROCEDURE_VERSION_REVIEW_MODE`: exactly
`solo` or `independent`, default `independent`, invalid values fail closed. The old
`PROCEDURE_VERSION_REVIEWS_REQUIRED` toggle is no longer supported.

Both modes require a Review Policy with an accountable author and truthful configured high-risk
flags. In `solo`, general dimension approvals are not mandatory or consumed: one person may author
and publish with existing permissions, without self-approval or account switching. Optional
independent general approvals may remain history. In `independent`, all dimensions above require
fresh, permission-eligible, signature-bound approvals distinct from both author and publisher;
the author may be the publisher.

In **both modes**, every configured `legal`, `military`, `custody_guardianship`, or
`contested_identity` flag requires a fresh, eligible specialist approval distinct from author and
publisher. High-risk material stays unpublished without a real specialist. Never clear or omit
risk flags to evade policy. All other publication gates and immutable snapshots remain unchanged;
there are no new lifecycle states.

New publish events record the applied `review_mode` and only actual fresh eligible independent
approvals consumed by that mode. Legacy events and withdrawal rows retain null/unrecorded mode,
not inferred review claims. Mode changes affect future publication attempts only, never history.
See [review role rules](procedure-version-review-roles.md) for signatures and permissions.

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

## Trusted Steps and Warnings (#41)

Publication now locks Bases, Checklist Items, Steps, Warnings, all claim Evidence Links and source links, then Sources, Authorities, and Document Types in stable primary-key order. Core gates validate ownership, bilingual completeness, applicability against published Facts, temporal/order metadata, Basis ownership, evidence quality, contradictions and Field Report context. Current Steps and administrative Warnings require current supporting evidence. Product Warnings prohibit evidence, and each published version has exactly one important product regeneration warning.

Snapshots detach these records and planners sort them deterministically. Step and Warning applicability, temporal, trust, contradiction, and support failures omit only that item so unrelated reliable guidance remains available. Existing Checklist Item policy still reports untrusted or applicability-unknown Official Requirements as a local inconclusive result. Database triggers and model guards preserve published and withdrawn claim aggregates and shared provenance.

## Admin behavior

Django Admin is the initial editorial surface. It should make unsafe states difficult:

- published semantic records are read-only;
- "clone to draft" is explicit;
- validation errors point to the affected semantic item;
- source/evidence/discrepancy context is reviewable without appearing in public DTOs;
- publication/withdrawal actions are permission-controlled service operations;
- review and publication history is visible to staff.

A custom CMS may be introduced later only if Django Admin becomes a demonstrated bottleneck.

## Production import lifecycle

Supported importers create or verify drafts only. Staff run the importer with an existing
accountable author, complete general dimension approvals in `independent` and applicable specialist
approvals in both modes in Admin, and publish only with the canonical Procedure Version Admin action.
Manual Admin authoring and the existing deterministic importers remain supported. Those
deterministic importers return an identical draft (or verify an already finalized identity)
and reject semantic conflicts; they never manufacture users, approvals, publisher identity,
or publication dates.

[ADR 0020](../adr/0020-use-versioned-draft-pack-authoring-contract.md) adds generic draft-pack
import/export plus CLI, including untrusted external-LLM research preparation. Its explicit
selected-target/fingerprint update contract differs from deterministic fixture verification:
only drafts may be updated, owned arrays are full desired snapshots, and deletions require
consent. Shared catalog records are create-or-exact-compare. Initial Service Questions,
candidates and contradictions may be created only with a brand-new Service in the same
transaction; existing setup is protected even inactive. New Services remain inactive and new
source Facts unpublished, with manual readiness followups rather than automatic activation.

Import preserves unchanged rows, existing authors and approval/audit history. Claim/evidence
changes reset affected trust, including Basis-scoped dependents; version semantic changes
conservatively reset owned aggregate trust. Owners with discrepancy/re-verification history
cannot be edited or deleted: temporal overlays cannot safely be rewritten for new meaning.
Use a fresh successor or supported manual workflow. Unchanged scenarios retain seals and may
become stale; humans must explicitly review and resave through Admin. Imports cannot clear
existing risks or manufacture approvals/verification. All publication gates remain separate.

Import and export take short fixed knowledge-table locks with nonblocking acquisition for
coherent reads and revision checks against ordinary writers, returning retryable
`concurrent_edit` conflicts. A complete-live-state fingerprint includes protected trust and
history, not just authored text. A small internal last-request/post-revision hash receipt
permits only proven unchanged exact retries; no raw uploaded pack is stored. See the
[operator guide](../draft-packs/README.md) for stale revisions, deletion consent and permissions.
PR3 Admin upload/preview and publication-diagnostics UI are not included.

The passport importer recognizes only its exact legacy, pre-checklist-Question, and
pre-Fee-Question scenario seals. After all other integrity checks pass, rerunning it upgrades an
eligible draft atomically through normal scenario saves: legacy routing corrections are retained,
the student Question correction is retained where needed, and the missing Fee applicability
scenario is created for every prior seal. Changed scenario content invalidates prior review
signatures; publication still requires fresh approvals for the applied mode. Exact legacy published or withdrawn
imports remain verifiable without rewriting their scenarios. Any other scenario drift is rejected,
including missing or partial upgrades. Fresh imports use the current expectations. This
compatibility path does not change claims, evidence, lifecycle state, or publication history.

## Migrating the researched fixtures

The three evidence packs remain research/reference inputs. Historical prototype fixtures are
preserved in Git history only and are not production runtime dependencies.

Production seeding should create real production records through supported import/fixture services and then validate them using the production publication validator. The migration should preserve stable semantic IDs where useful for acceptance parity, but should not preserve prototype-only compatibility aliases or test-only synthetic structures.

## Routing publication gate

Publication locks routing associations, referenced stable points and material versions, both
evidence owner sets, EvidenceLinkSource rows, Sources, and Authorities in deterministic order.
The routing gate rejects implicit ownership, malformed published-Fact rules, incomplete
bilingual identity/address, unsupported availability, unordered/overlapping current material,
invalid verification metadata, incomplete support, current contradictions, and malformed Field
Report provenance. Routing Facts need not have Service Questions because routing uncertainty is
local and non-consequential.

### Passport applicability Question compatibility

The passport importer authors `passport.student.unknown` as `next_question` for `q.is_student` and
`passport.fee.service_level_unknown` as `next_question` for the existing bilingual
`q.service_level`. Its integrity verifier accepts only the current seal and the exact legacy,
pre-checklist-Question, and pre-Fee-Question seals. Only after planning signature, research, trust,
evidence, and review-policy checks pass, an eligible draft receives all missing historical routing
and student updates plus the Fee scenario in one transaction through normal model saves. Thus
direct upgrades from every prior seal and sequential historical transitions end at the current
seal, while scenario changes invalidate prior review approvals.

Exact published or withdrawn prior seals remain verifiable and are never rewritten. Missing,
partial, or arbitrary scenario drift is rejected without a partial upgrade. This compatibility
path changes no claims, Fee predicates or values, evidence, lifecycle state, publication history,
or immutable rules-contract semantics.
