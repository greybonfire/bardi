# Procedure Version review role rules

**Status:** Authoritative  
**Effective:** 2026-09-06

This document defines the version-1 independence and specialist-eligibility rules used by the
Procedure Version publication gate. It extends `knowledge-publication.md`; it does not introduce
a second publication path or a generalized workflow engine.

## Deployment review mode

[ADR 0019](../adr/0019-use-explicit-solo-and-independent-publication-review-modes.md) replaces the
blanket second-person publication requirement. `PROCEDURE_VERSION_REVIEW_MODE` is a deployment-wide
environment variable/Django setting accepting exactly `solo` or `independent`, defaulting to
`independent`; invalid values fail closed. The old `PROCEDURE_VERSION_REVIEWS_REQUIRED` flag is
unsupported, not a fallback. There is no production off mode.

In `solo`, mandatory general dimension approvals are skipped entirely. One person may author and
publish with existing permissions; no account switching or self-approval paperwork is required.
Optional genuinely independent general approvals remain history but are not consumed. In
`independent`, all applicable general dimensions below are required. Both modes require the
accountable author, truthful risk flags, and all applicable specialist approvals. All evidence,
trust, scenario, domain, bilingual, effective-date and immutable-snapshot gates remain in force.

## Meaning-changing publication

A new Procedure Version is the semantic publication boundary. In version 1, publishing a draft
Procedure Version is therefore treated as meaning-establishing/meaning-changing for review
purposes. Pure evidence re-verification that does not change public meaning uses the separate
re-verification workflow and does not create a replacement Procedure Version merely to avoid
review.

## Accountable author

Every publishable draft has exactly one `ProcedureVersionReviewPolicy` naming its accountable
author. The author is the person responsible for the coherent draft state presented for review.
Changing the accountable author changes the reviewed-state signature and invalidates prior
approvals.

The author may later be the publisher, but the author may never satisfy an independent review or
specialist approval for that draft.

## General reviewer

A general reviewer must hold Django permission `knowledge.review_procedureversion` both when the
approval is recorded and when that approval is used to satisfy publication. General approvals are
recorded separately for these dimensions:

- `evidence_source` — evidence and preserved-source adequacy;
- `rule_logic` — rule and decision-logic semantics;
- `scenario_behavior` — named acceptance-scenario behavior;
- `bilingual_semantic` — Arabic/English semantic parity;
- `discrepancy` — discrepancy disposition when the draft has affected evidence.

In `independent`, one eligible reviewer may approve more than one dimension. Each required dimension must have at
least one fresh approval independent of both the accountable author and the eventual publisher.
An approval by the eventual publisher is preserved as review history but does not satisfy the
publication gate.

## Specialist reviewer

High-risk review is configured on the draft review policy with independent flags for:

- `legal`;
- `military`;
- `custody_guardianship`;
- `contested_identity`.

In **both modes**, each configured risk requires a fresh specialist approval independent of both
accountable author and publisher. High-risk content remains unpublished without a real specialist;
flags must not be omitted or cleared to evade policy. The reviewer must hold the
matching Django permission both when recording the approval and when the approval is used for
publication:

- `knowledge.specialist_approve_legal`;
- `knowledge.specialist_approve_military`;
- `knowledge.specialist_approve_custody_guardianship`;
- `knowledge.specialist_approve_contested_identity`.

A specialist may also act as a general reviewer only when they separately hold the general review
permission and record the corresponding dimension approval. Specialist approval does not replace
ordinary evidence, logic, scenario, bilingual, or discrepancy approvals required in `independent`.

## Reviewed draft state

All approvals for a Procedure Version bind to one SHA-256 signature of the coherent consequential
draft state. The signature includes authored planning semantics, named scenarios, evidence links,
preserved sources/authorities, relevant document types, discrepancy state, and the review policy.
Approval rows themselves are excluded from the signature so multiple reviewers can approve the
same exact state.

Any later change to reviewed semantic/evidence/scenario/discrepancy/risk/authorship content produces
a different signature. Existing approvals remain immutable history but become stale and cannot
satisfy publication.

## Publication and audit

The publication gate reports missing, stale, ineligible, or non-independent approvals by review
dimension or specialist risk. When all requirements pass, it returns an in-memory decision binding
the mode, coherent draft-state signature, accepted approval IDs, version, and publisher. The
canonical publisher validates that decision before the lifecycle transition. Each new publish
audit event records the applied `review_mode` and atomically
captures only fresh, permission-eligible approvals independent of author and publisher actually
consumed by that mode into `ProcedureVersionAuditApproval`. Solo captures applicable specialist
approvals only, never optional general approvals or fake self-approvals.

Legacy audit events and withdrawal rows have null/unrecorded mode: no retrospective inference or
backfill of review claims. Changing mode affects future publication attempts only, never existing
publications or audit history. Failed publication rolls back lifecycle changes and audit capture.
