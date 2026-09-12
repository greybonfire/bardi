# Bounded production implementation handoff

This research PR changes documentation only. The tasks below define subsequent work; they do
not claim that a full live suite can be safely generated from the existing renewal importers.
Complete a task's prerequisites before implementing it. Each implementation PR should identify
the exact catalog rows, claim IDs, scenario IDs, evidence snapshot and remaining local unknowns.

The existing [editorial process](../../editorial-process.md) governs draft/review/publication.
Tests are required for consequential behavior. The retired prototype is not an implementation
target. New content must stay in draft; a code PR does not provide independent human approval.

## I01 — Repair passport provenance through successor research

**Input:** S01–S04/S23, D01, current passport renewal pack and production importer.\
**Bound:** One successor passport-renewal draft with corrected claim-specific provenance;
no new Procedure family, shared Fact changes, or broader representation/military semantics.

1. Map every old `SRC-MOI-PASSPORT-REQ` assertion to its actual inspected source. Use S01 for
   Form 29/fees/process, S02 for ordinary documents, and S03/S04 only where the successor includes
   those claims. Record unsupported claims separately rather than claiming the privacy page supports them.
2. Create new Source/Evidence Link records and a successor draft using the supported lifecycle.
   Preserve all original research IDs, historical Source rows, published/withdrawn versions and seals.
3. Recheck volatile fee text and Source scope; do not call this semantic-preserving re-verification
   if the meaning, supporting passage or applicability changed.
4. If current code cannot create the successor without changing old reproducibility contracts,
   document that as the specific I02 input; do not patch through the invariant.

**Acceptance:** The old public import still reproduces its original aggregate; the new draft uses
the correct per-claim locators; no new guidance is public; no unsupported source is marked current.
Add focused PostgreSQL importer/lifecycle tests and successor scenario coverage for SC02/03/20/22–24.
No need to add every later suite Fact for this task.

## I02 — Resolve shared catalog growth before adding new Questions

**Input:** `backend/knowledge/planning_scenarios.py::planning_behavior_signature`, current renewal
importers and their integrity verifiers, ADRs 0001/0003/0013–0018.\
**Bound:** First produce a reviewed design/ADR and regression test that defines historical
scenario/import compatibility when Service Questions or selection semantics grow. Implement that
approved design in its own PR; do not combine it with the whole suite.

At the baseline, the behavior signature includes **all Questions, resolved-Fact links and
contradictions under the Service**, plus candidates for the version's own Procedure. Both renewal
integrity paths check stored scenario signatures against the current signature. Adding another
candidate alone is not the same mutation as adding a Service Question or editing the old candidate.

The design must explicitly decide how current catalog content and preserved evaluation context
coexist, how successor drafts obtain their context, and which importer combinations are supported.
It must preserve strict tamper detection and make a supported additive content import repeatable.
Do not merely refresh historical signatures, drop questions from hashing without a contract, relax
the digest verifier, or catch-and-ignore conflicts. Publication approval invalidation must remain
correct for genuinely changed draft behavior.

**Acceptance:** SC65–SC67, including both import orders, repeat import, unrelated additive content,
material mutation, published and draft versions, and a stored signature mismatch. Existing
regressions still pass. The selected design has exact model/service/migration boundaries and is
approved before a smaller implementation task is assigned. This is a design prerequisite, not an
invitation for a small model to invent a compatibility exception while authoring content.

## I03 — Add only vocabulary needed for domestic passport first issue/loss

**Prerequisite:** I02 accepted/implemented; reviewed Fact meanings.\
**Bound:** P01/P03/P04 selection and their needed history/loss source Facts. No consular,
data-change, representation expansion, or deadline derivation work.

- Reuse existing registry definitions. Confirm `none` semantics; introduce
  `passport_ever_issued` and `passport_loss_location` as proposed if required by the accepted contract.
- Add compatible database Fact definitions through the established migration/publication pattern
  and Service-scoped bilingual Questions. Do not extend old enum values or redefine old keys.
- Explicitly distinguish location of loss from location of application; preserve the old renewal
  candidate's original behavior unless the approved rollout requires a reviewed successor boundary.
- Keep draft-only/unresearched cases from appearing as supported public services. Do not add live
  candidates whose unavailable version merely interferes with an existing interview.

**Acceptance:** Focused pure/ORM tests for SC01/04–06/13/60/63/64/70; deterministic Question priority;
new keys rejected before registration and correctly typed afterward; old packs remain reproducible.

## I04 — Import the bounded domestic passport first-issue and loss content

**Prerequisites:** I01–I03; named author; review of applicable documentary, military and representation
conditions; G01/G05/G06 disposition recorded for each included scope.\
**Bound:** Separate small PRs for P01, P03, and P04. Start with self-submitted ordinary adult cases;
do not claim unreviewed minors, agents or combined data changes are covered.

For each PR, import the reviewed version-owned checklist, steps, fee components, warnings and routing
associations with claim-level evidence. Use one explicit atomic public import entry calling a private
builder followed by final verification exactly once, following the current importer convention.
Keep missing exact fees/routes explicit where the publication contract allows; do not convert them
to zero or a guessed office. P03 must include the domestic report distinction; P04 must use its
separate department/document context.

**Acceptance:** Positive/negative/UNKNOWN/contradictory/edge scenarios required by the publisher;
applicable SC01/04–07/14–24/59/61/66/68/69. Verify rollback after late failure, repeat imports,
strict drift rejection, source coverage, and no publication/approval side effects.

## I05 — Close and encode domestic National ID documentary gaps

**Prerequisites:** D02/D03/D09 and G02/G03 evidence work; I02 for shared catalog changes.\
**Bound:** Research/implement one family per PR: N01, N02 successor, N04, N05, N06, then N07.
N03 cannot be treated as ready until the old-card contradiction is resolved. N08/N09 are excluded.

For the selected family, obtain current competent instructions for identity/document alternatives,
forms, appearance/capture requirements, submission/collection, fee state, and exact channel scope.
Record what is required versus optional preparation, and whether proofs are alternatives. Do not
use consular proof menus domestically. Keep first issuance separate from physical possession.

Then add only the required typed Facts/Questions and one reviewed draft importer/command. Preserve
the existing expiry and renewal-deadline derivations. Add event-date derivations only in a separate
bounded follow-up after the amended legal rule has been reviewed.

**Acceptance:** Appropriate SC29–SC44/71 plus a real positive and negative case for every newly
supported documentary alternative; conditional marriage proof never inferred from vague wording;
strict idempotence, source completeness, lifecycle and coexistence tests. No invented domestic
fee, early-renewal window, fine, or online-completion promise.

## I06 — Resolve passport data changes, damage and combined transactions

**Prerequisites:** G04/G07/G08 closed for the exact subcase; I02.\
**Bound:** One transaction decision table before any new candidate is added. Start with P05,
then P06/P02 overlap; later N09. Do not create a generic “other” catch-all.

Specify the result for every combination of document state and change kind, including UNKNOWN.
Identify whether the authority processes one replacement, a renewal with conditional evidence,
or ordered transactions. Record fee consequences without double charging. For an issued passport,
preserve the distinction between reissuance and changing the underlying record.

**Acceptance:** SC08–10/28/35–39/50/51/59/67 for the selected increment; pairwise non-overlap for
supported candidates; combined facts remain valid input; unresolved combinations remain
inconclusive; no silent first-match priority. Any change to existing selected behavior goes through
the accepted successor/catalog rollout and its regression tests.

## I07 — Add one verified consular mission at a time

**Prerequisites:** Mission-specific D04–D07 and G06/G08/G09 resolutions; I02.\
**Bound:** One mission and one output family per PR. General MFA guidance is common research,
not an all-countries routing rule. Do not attempt London, Dubai and Sydney in one importer.

Record the current mission's jurisdiction, supported transaction, documentary alternatives,
approval steps, charges/currency/payment method, collection process, and applicable dates.
Resolve conflicting age/photo/validity statements. Separate temporary return documents from
ordinary passports and first-ID committees from permanent renewal counters.

Use country/region facts and evidence-backed jurisdiction rules; do not ask the user to decide
which office is legally competent. Add no data for an unverified mission or expired committee event.

**Acceptance:** The applicable subset of SC45–SC58/60/61/68; cross-mission negative scenarios;
currency isolation; no universal short-validity or photo-count rule; no assumed airline acceptance.
Other overseas cases remain explicitly unsupported until individually researched.

## I08 — Publication and suite acceptance

**Prerequisites:** Only the exact included rows' evidence, implementation and review gates have
closed. A partially completed suite may publish a bounded supported subset.\
**Bound:** Review/publish the coherent Procedure Versions through the existing staff lifecycle.
No direct database state assignment, automated self-approval, or deployment as part of a code PR.

- Assign the accountable human author and independent bilingual reviewer. Configure applicable
  legal, military, custody/guardianship and contested-identity specialist requirements.
- Verify every active candidate has the intended usable version, every consequential source Fact
  has an active Service Question, and negative/UNKNOWN combinations do not gain guidance by accident.
- Reverify volatile material, resolve applicable discrepancies, run every required PlanningScenario,
  inspect the actual Arabic and English public plans, then obtain independent approvals.
- Run the relevant PostgreSQL publication/importer/API tests and the pure planner suite. Use CI's
  production checks for lint, formatting, typing, migrations and database integration.
- Update this inventory's per-row status with the exact version/PR and remaining gaps. Do not mark
  “full suite complete” while any claimed supported family still depends on a blocked G/D item.

**Acceptance:** Reviewed source-backed plans, scoped honest unknowns, passing scenario/publication
gates, preserved histories and import seals, and explicit coverage for unsupported adjacent cases.
SC59–SC70 remain regression requirements for the relevant production increments.

## Done for this research PR

- Every ordinary passport/ID transaction family has a catalog disposition, including combined,
  consular, emergency and adjacent boundaries.
- Material claims point to inspected official material or are visibly marked as leads/review gaps.
- New/current Facts, bilingual Questions, future scenarios and integration hazards are explicit.
- Existing evidence packs link to this successor research without rewriting their historical claims.
- Repository-local links and claim/source/scenario references are checked. CI verifies the
  documentation branch against the production repository; it does not certify administrative truth.
