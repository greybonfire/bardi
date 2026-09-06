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

Approval rows stay immutable and are inspectable in their history Admins.

## Publication and withdrawal

The existing Procedure Version Admin publish/withdraw actions remain permission-controlled calls
to `publish_procedure_version()` and `withdraw_procedure_version()`. Admin never assigns lifecycle
fields directly.

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
