# Bounded implementation handoff

This research PR does not implement these tasks. Complete the prerequisites for the selected
increment, then use a separate focused PR. The production [editorial process](../../editorial-process.md),
[rules contract](../../architecture/rules-contract.md) and accepted ADRs govern every implementation.
No work targets the retired prototype. Tests are required for consequential behavior.

## I01: Close evidence for one administrative stage

**Input:** [claim ledger](claims.md), [source records](sources.md), A01-A08.

**Bound:** Choose exactly one: an authority-referral preparation stage, first certificate after
grant, or replacement of an already-issued medical-exemption certificate. Record the choice in
the follow-up PR; do not fill all stages with a copied generic checklist.

Obtain the applicable G01 legal review and the selected stage's G02/G03 instructions. Record
documents and alternatives, exact steps, jurisdiction rule, publication/effective dates and current
fee/timing state. Resolve G05 for any accessibility/representation branch included. For C06,
close G06 separately before authoring that item; no clinical classifier is part of this task.

**Acceptance:** A reviewer can trace every proposed consequential item to an inspected passage,
its exact scope and open gaps. A blocked legal/administrative path stays blocked. Named authority
scope, human author and independent legal/military review needs are explicit. No calls, messages,
applications or payments are authorized by this handoff; public documentary research is sufficient
to produce the draft or explain the remaining evidence blocker.

## I02: Decide selector and historical-context compatibility

**Bound:** A reviewed design/ADR plus a focused failing regression that demonstrates the baseline
problem; implement the accepted design in its own PR before adding active medical content.

Inspect:

- `backend/knowledge/importers/temporary_family_exemption.py`, especially the domestic-only
  Service Procedure candidate and shared Question creation;
- `backend/knowledge/planning_scenarios.py::planning_behavior_signature`;
- `backend/knowledge/importers/temporary_family_exemption_integrity.py`;
- ADRs 0001, 0003, 0009 and 0013-0018.

At this baseline, the family selector tests only `application_location=inside_egypt`. A domestic
medical selector overlaps it even when the applicant has no qualifying family circumstance.
The signature hashes the version's Procedure candidates and all Questions/resolved-Fact links
and contradictions under its Service. Shared Question growth can therefore invalidate the existing
family scenarios and strict imports; adding an unrelated candidate alone has a different effect.

The design must specify stable Procedure identities, assessment-process versus exemption-Basis
semantics, the subject/stage selection table, exact Question priorities, and preservation of
published/historical evaluations and importer reproducibility. Define what happens to legacy
requests with no new subject Fact, combined family/medical circumstances, and unavailable versions.
Do not solve this by asking the user which legal exemption they qualify for.

**Acceptance:** MS28-MS30/MS36 demonstrate the issue and the agreed corrected behavior; test both
supported import orders, repeated imports, material drift and published/draft histories. No
arbitrary priority between two TRUE candidates, overwritten historical signature, catch-and-ignore
integrity failure, duplicate public military Service, or broadened untrusted family Basis.

The [passport/ID research PR #138](https://github.com/greybonfire/bardi/pull/138) identifies the same
shared-catalog signature concern. Coordinate one accepted compatibility design; this branch is
based independently on main and does not require that documentation PR to merge first.

## I03: Register only the Facts and Questions needed by the chosen stage

**Prerequisites:** I01's stage specification and I02's accepted compatibility contract.

**Bound:** The exact source-Fact subset from [workflow-and-facts.md](workflow-and-facts.md) needed
for that stage, compatible database definitions, bilingual Service Questions and reviewed
contradictions. Do not register every proposal merely because it appears in this pack.

Use `backend/planning/facts.py` and the established Fact-definition migration/publication pattern.
Keep existing meanings/enum values and derived Facts unchanged. A civilian medical letter is not
an authority decision; a medical finding is not the same Fact as the exemption record; issuance
history is not current physical possession. Do not derive a health/fitness score or add diagnosis,
symptom, medication, hospital-history or document-number inputs.

**Acceptance:** MS08-MS10/MS22-MS23/MS36; tests of omitted versus explicit unclear/no-record values,
enum validation, deterministic Question selection, and non-looping stateless resubmission. All
consequential condition inputs have same-Service Question coverage. Do not add an unready active
candidate whose missing published version disrupts the existing military interview.

## I04: Import one coherent draft and its production scenarios

**Prerequisites:** I01-I03 for the exact included stage; named accountable author.

**Bound:** One importer plus management command, following existing production patterns, for the
reviewed administrative stage. Mental versus physical conditions do not become separate disease
Procedures. A confirmed certificate transaction may use its own stable identity as decided in I02.

Author only reviewed version-owned applicability, Bases if appropriate, checklist, steps, fees,
warnings, dependencies and Service Point associations, with claim-specific Evidence Links.
Keep unknown prices/routing explicit where the contract permits. Do not make a preparation plan
sound like an exemption decision. Untrusted matched Bases retain their existing restrictions.

Use one public atomic entry point, private builder, and final integrity verification exactly once.
Keep the old family aggregate reproducible. No fixture cloning that retains irrelevant family
Questions/documents, fake current source dates, publication calls, approvals or deployment.

**Acceptance:** Exact stage-specific MS01-MS07 plus required negative, UNKNOWN, contradictory and
supported-edge production scenarios. MS24-MS27/MS31-MS34 cover trust, dates, source scope, imports
and privacy. Run focused PostgreSQL importer/API/publication tests and the pure planner suite;
CI covers lint, formatting, typing, migrations and the production integration suites.

## I05: Add accessibility or psychiatric documentation as separate increments

**Prerequisites:** The corresponding G05 or G06 evidence and specialist interpretation closed;
baseline chosen stage supported. These increments may proceed independently after I04.

**Bound:** One conditional feature per PR. For accessibility, a named region/committee arrangement
and its verified request method; for psychiatric paperwork, one precisely reviewed administrative
document subcase. Do not combine these with medical eligibility automation or appeals.

**Acceptance:** MS11-MS15/MS18-MS19, with both inclusion and exclusion cases for each conditional
item. No universal hospital admission, disability-card dependency, Council certificate, proxy
permission, home visit or fee waiver. Blocked evidence cannot provoke extra sensitive Questions.

## I06: Review, publish and record actual coverage

**Prerequisites:** Exact supported stage's evidence and implementation gates completed.

**Bound:** Use the existing staff review/publication lifecycle for that version. Configure
`legal` and `military` review risks (`legal_risk` / `military_risk` fields); assess custody/guardianship or contested
identity only if those scopes are included. Confirm clinical terminology with a qualified reviewer;
do not invent a new permission or mark the author as an independent approver.

Inspect the Arabic/English generated plans and review every required scenario. Reverify volatile
service details and preserve the current supporting passages. Publication rejection must remain
actionable; a code merge is not evidence approval.

**Acceptance:** MS26/MS31/MS32 pass; the pack records the exact implemented version/PR and remaining
gaps. Serving/reserve cases, overseas processing, appeals and unresearched conditions remain explicit
coverage boundaries. Never mark the branch fully supported while the included path relies on an
unresolved gap. Appeal/deadline work remains a separate task after G07, not part of this handoff.
