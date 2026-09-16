# Use explicit solo and independent publication review modes

## Status

Accepted — 2026-09-16.

## Context

A solo operator needs to author and publish ordinary guidance without pretending that account
switching or self-approval is independent review. When a team joins, independent review must be
restorable without rewriting publication history. A blanket review-disable switch would also
remove safeguards for high-risk material.

## Decision

Extend [ADR 0003](0003-publish-coherent-procedure-versions.md) with a deployment-wide environment
variable and Django setting, `PROCEDURE_VERSION_REVIEW_MODE`. Its only values are `solo` and
`independent`; the default is `independent`, invalid values fail closed, and local `.env.example`
explicitly opts into `solo`. It replaces `PROCEDURE_VERSION_REVIEWS_REQUIRED`; the old flag is no
longer supported. There is no production review-off mode. Tests may explicitly omit the review
gate for isolation in test-only settings.

Both modes require a Review Policy naming the accountable author and truthfully configuring
`legal`, `military`, `custody_guardianship`, and `contested_identity` risks. Never omit or clear a
real risk to evade policy.

- **Solo:** skip mandatory general dimension approvals entirely. The same person may author and
  publish with existing permissions, without account switching or self-approval paperwork.
  Optional genuinely independent general approvals may remain history but are not consumed.
- **Independent:** require fresh, permission-eligible approvals for evidence/source, rule/logic,
  scenario/behavior, bilingual semantics, and discrepancy where applicable. Consumed reviewers
  must be distinct from both author and publisher; the author may still publish. Existing
  reviewed-state signatures and permissions remain required.
- **Both:** every configured risk requires a fresh, permission-eligible specialist approval,
  distinct from both author and publisher. High-risk content stays unpublished without a real
  specialist. Evidence, trust, scenarios, domain/rule validation, bilingual completeness,
  effective dates, and immutable snapshots remain mandatory.

Each new publish audit event records the applied `review_mode` (`solo` or `independent`) and only
actual fresh, eligible, independent approvals consumed by that mode. Never manufacture
self-approvals. Legacy audit events and withdrawal rows retain null/unrecorded mode; do not infer
or backfill a historical review claim. Mode changes govern future publication attempts only.

This explicitly replaces the blanket mandatory second-person requirement in authoritative
publication/review documentation, not ADRs 0001/0002 or ADR 0003's snapshot, evidence, trust, and
lifecycle guarantees. No publication states are added.

## Consequences

Ordinary content can be published honestly by one accountable operator; solo is not a claim of
independent general review. Specialist availability still limits high-risk publication. Operators
switch the deployment to `independent` when the team joins and obtain the required fresh approvals
for future attempts; existing publications and audits remain unchanged.

PR1 is limited to this publication policy and honest audit history. Manual Admin authoring and
existing deterministic draft importers remain the entry routes. Generic importers, LLM ingestion,
and Admin upload tooling are not implemented by this decision or this PR.
