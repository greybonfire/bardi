# Use a versioned draft-pack authoring contract

## Status

Accepted — 2026-09-16.

## Context

Researchers need a generic, inspectable handoff from external research tools, including LLMs,
without a custom deterministic importer for every Procedure. An ORM dump would expose lifecycle,
trust and audit fields as apparent authoring inputs. A patch keyed only by an uploaded version ID
could overwrite concurrent editorial work or silently change shared Service configuration.

Ordinary Admin/model writers do not universally lock the owning Procedure Version before
inserting or editing children. Import-only row/advisory locks cannot exclude those phantoms.
Evidence workflow overlays can also restore historical trust onto changed claims if an importer
rewrites meaning beneath their history.

## Decision

Extend [ADR 0007](0007-store-claims-relationally-and-rules-as-json.md) with a separate, versioned
JSON **authoring transport**, not opaque JSON persistence. `bardi.draft-pack`, integer
`format_version: 1`, has an explicit strict schema, bounded input, stable scoped identities,
shared create-or-exact-compare catalog definitions and one complete desired version-owned
snapshot. Rules still pin their independent `rules_contract_version`; this does not reinterpret
published Fact meaning or evaluator behavior under [ADR 0001](0001-preserve-published-evaluation-semantics.md).

Import is a staff-authorized domain service with thin CLI adapters. Require a real active staff
actor, existing version add/change permissions, and corresponding add permissions for new shared
catalog/setup records; exports require version view permission. The operator is out of band and
becomes author only for a new Review Policy. Input cannot assign lifecycle, authors, approvals,
verification, workflow history or scenario seals. Exports are coherent; read-only vocabulary
context has a distinct non-importable format. Raw packs are not retained in the database.

Permit initial Questions, candidates and contradictions only for a Service created in the same
transaction. Existing Service setup is compare-only, even when inactive. This extends the
Service-owned authoring boundary of [ADR 0013](0013-own-planning-questions-at-goal-level.md) with
current terminology from [ADR 0014](0014-use-service-as-production-procedure-grouping.md), not
Procedure-Version ownership of Questions. New Services remain inactive; new source Facts remain
unpublished. Derived definitions/formulas and shared Service Point material are outside v1.

Updates require an explicitly selected draft, exact version/Procedure identity, and an exported
opaque complete-live-state fingerprint checked inside the write transaction. Owned deletions
require explicit consent; dry-run uses the same path with rollback. Stale state is rejected even
if authored text matches. Only the exact normalized last successful request and an unchanged
post-import fingerprint can be a no-op retry, proven by a small internal per-version hash receipt.
The receipt is not an upload archive, approval, or replacement audit trail.

Use a fixed knowledge-table lock set in `SHARE ROW EXCLUSIVE NOWAIT` mode for import and export,
with a short local timeout for implicit locks retained through outermost commit. Nonblocking
key-share locks on existing knowledge rows and a lock on the freshly authorized actor protect
deferred foreign-key checks. Nested calls restore the caller's timeout, not release those locks:
all locks last until the enclosing transaction ends, so callers must keep it short. Nonblocking
acquisition avoids waiting behind ordinary writers/publishers; ordinary reads continue, while
ordinary writers may wait during the authoring transaction. Return retryable `concurrent_edit`
on conflicting concurrency.
This deliberately conservative low-volume MVP rejects more concurrent work than a comprehensive
fine-grained writer-lock protocol would. The fingerprint likewise conservatively includes shared
registries/global metadata and relevant dependency aggregates, not only semantic review hashes.

Preserve [ADR 0002](0002-use-claim-level-evidence.md)'s claim-level provenance and
[ADR 0003](0003-publish-coherent-procedure-versions.md)'s lifecycle separation. Unchanged rows
retain identity/trust; semantic/evidence changes reset affected owner/evidence trust, including
Basis-scoped dependents and conservative whole-aggregate resets for version semantic changes.
Refuse edits **and deletions** affecting owners with discrepancy/re-verification workflow history:
old overlays cannot safely be rewritten or applied to new meaning. Use a fresh successor or
supported manual workflow instead. Never delete inconvenient history to admit an import.

Approval and audit history remain intact. Unchanged scenarios keep their seals and may become
stale; humans explicitly review and resave them in Admin. Only new/genuinely changed scenarios
receive normal model seals. Existing true risk flags cannot be cleared by import. Publication,
verification and the solo/independent review policy of
[ADR 0019](0019-use-explicit-solo-and-independent-publication-review-modes.md) remain separate
manual services and gates. No historical safety decision is superseded or rewritten.

## Consequences

External-LLM output is a supported **untrusted research input**, never authority or automatic legal
inference. Schema validation and successful dry-run do not establish evidence quality or
publication readiness. Incomplete drafts require manual evidence, Fact publication, Question and
scenario coverage, activation and review followups. Blank legacy Evidence Link IDs require manual
assignment through a lifecycle-safe path before export; exporters do not repair data.

Coarse locks simplify correctness against existing ordinary writes but serialize pack operations
and can briefly block unrelated knowledge writers. NOWAIT and the implicit lock timeout do not
bound total transaction duration; there is no throughput/latency guarantee. Higher-volume editing
would require measured evidence and a coordinated writer protocol, not removal of these locks
while retaining a false claim of coherent revision checks.

PR2 implements generic import/export plus CLI and the
[versioned schema, example and external-LLM guide](../draft-packs/README.md). Manual Admin editing
and deterministic importers remain. PR3 Admin upload/preview and publication-diagnostics UI are
not implemented by this decision's delivery. No public API/frontend, automatic publication,
hosted infrastructure or production migration is introduced by this authoring interface.
