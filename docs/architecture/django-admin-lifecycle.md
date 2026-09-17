# Safe Django Admin lifecycle

**Status:** Authoritative  
**Effective:** 2026-09-06

Django Admin is the initial staff editorial surface. It is a controlled interface over the
existing knowledge-domain services, not an alternate lifecycle implementation.

## Capability boundaries

Django permissions are intentionally separated:

- **research/edit** — standard model `add_*` / `change_*` permissions on draft knowledge;
- **review** — `knowledge.review_procedureversion`;
- **specialist review** — the risk-specific `knowledge.specialist_approve_*` permissions;
- **publish** — `knowledge.publish_procedureversion`;
- **withdraw** — `knowledge.withdraw_procedureversion`;
- **re-verification** — `knowledge.add_evidencereverificationevent` used by the service-backed
  Evidence Link Admin action.

A staff account receives only the capabilities required for its role. Review permission does not
imply publish permission, specialist permission does not imply general review permission, and
research/edit permission does not imply re-verification or lifecycle-transition permission.

### Generic draft-pack service permissions

The [draft-pack CLI/service](../draft-packs/README.md) is a separate authoring entry point, not
an Admin upload or preview screen (PR3 is not implemented). It requires a persisted, currently
active staff actor reloaded from the database. New drafts require
`knowledge.add_procedureversion` **and** `knowledge.change_procedureversion`; updates require
`knowledge.change_procedureversion`. These authorize the version-owned aggregate import without
individual child add/change/delete permissions. Each new shared catalog type still requires its
`knowledge.add_<model>` permission; new-Service setup requires the applicable
`knowledge.add_servicequestion`, `knowledge.add_serviceprocedurecandidate` and
`knowledge.add_servicecontradiction` permissions. Both exports require
`knowledge.view_procedureversion`. This does not broaden the individual Admin model permissions.

The actor is accountable author for a new Review Policy, never a replacement for an existing
author. Initial setup is permitted only for a Service created by that import; existing Service
configuration is protected even inactive. Import cannot grant review, publish, withdrawal or
re-verification capability, assign their metadata, clear existing risks, or rewrite history.
Stale unchanged scenarios must be explicitly reviewed and resaved in Planning Scenario Admin;
reimporting identical data does not reseal them. Manual editing and deterministic importers remain.

## Draft authoring and successor cloning

Staff with ordinary Procedure Version add/change permissions may create a draft from scratch.
Published Procedure Versions never become editable again.

The explicit **clone to successor draft** Admin action calls
`clone_published_procedure_version()`. It copies the coherent editable aggregate into new rows:

- Procedure Version semantic content;
- Eligibility Bases, Checklist Items, Steps, Warnings, Fees and Procedure Dependencies;
- Procedure–Service Point associations while retaining shared Service Point Versions;
- claim-specific Evidence Links and their Source joins while retaining shared Sources,
  Authorities and Document Types;
- named planning scenarios, rewriting the expected Procedure Version identifier to the successor;
- configured high-risk review-policy flags.

The cloning staff member becomes the new accountable author. Prior discrepancies,
re-verification events, review approvals, publication audit events and approval audit rows are
historical records and are not copied to the successor.

## Review and specialist approval

The Procedure Version Admin review action presents the supported review dimensions and specialist
risk approvals. Submitting it calls the #48 approval services. Those services remain responsible
for draft-state hashing, author independence and reviewer/specialist eligibility.

Approval rows stay immutable and are inspectable in their history Admins. Under
[ADR 0019](../adr/0019-use-explicit-solo-and-independent-publication-review-modes.md), `solo` needs
no general review action or self-approval paperwork: an accountable author may publish with the
existing publish permission. Optional independent general approvals are history only in solo.
`independent` requires the applicable general dimensions. Both modes require truthful risk flags
and fresh, eligible specialist approvals distinct from author and publisher for every configured
risk; never clear flags to bypass review.

## Publication and withdrawal

The existing Procedure Version Admin publish/withdraw actions remain permission-controlled calls
to `publish_procedure_version()` and `withdraw_procedure_version()`. Admin never assigns lifecycle
fields directly. The deployment-wide `PROCEDURE_VERSION_REVIEW_MODE` selects `solo` or
`independent` (default); invalid values fail closed. All non-review gates remain mandatory.
New publish audits record the applied mode and only actual eligible independent approvals consumed
by it. Legacy events and withdrawal rows have null/unrecorded mode. Changing mode affects future
attempts, not published snapshots or history.

Published semantic material is read-only. Withdrawn material remains read-only and auditable.
Ordinary planning resolution considers only `published` versions; a withdrawn version can be
resolved only through the explicit historical-version path.

## Re-verification

Authorized staff use the Evidence Link Admin re-verification action. The form requires an explicit
verification state, verification date, optional next re-verification date and rationale. One
selected Evidence Link identifies a semantic subject; the action automatically submits that
subject's complete current evidence set to `record_evidence_reverification()`.

The action is semantic-preserving only. Meaning-changing research must use a successor Procedure
Version rather than mutating published semantic records.

## Inspection and validation

Sources, Evidence Links, Evidence Discrepancies, review policy/approval history, re-verification
history and publication audit history remain separate staff-only Admin surfaces. Search fields use
stable Procedure Version or semantic-item identifiers where applicable.

Admin lifecycle actions prefix validation failures with the affected Procedure Version or evidence
owner, while publication diagnostics retain their gate/code/detail tuple. This keeps failures
traceable to the semantic item without exposing editorial context through public planning DTOs.
