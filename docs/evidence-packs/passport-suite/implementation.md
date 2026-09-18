# Bounded passport implementation handoff

This documentation-only PR does not implement the proposed Facts, activate candidates, run
production imports or approve publication. Each later PR must name its catalog rows, claim IDs,
scenario IDs, evidence date and remaining unknowns. Complete prerequisites before implementation;
use the [editorial lifecycle](../../editorial-process.md), not direct database state assignment.
The retired prototype is not a target. Keep authored content in draft pending independent review.

Task names are family-scoped: P-Ixx and N-Ixx retain the original handoff numbers where applicable.
The only shared task is [I02](../catalog-compatibility.md), implemented once. A shared Fact likewise
has one compatible registry definition, not competing family-specific migrations.

## P-I01

### Repair passport provenance in one successor renewal draft

**Input:** S01–S04/S23, D01, current passport renewal baseline/importer.
**Bound:** One successor passport-renewal draft with corrected claim-level provenance; no new
Procedure, shared Fact changes or broader representation/military semantics.

Map every SRC-MOI-PASSPORT-REQ assertion to actual inspected material: S01 for Form 29/fees/process,
S02 for documents, S03/S04 only for included claims. Mark unsupported claims separately. Reopen
volatile sources before importing; create new Sources/Evidence Links and a successor via the
supported lifecycle. Preserve existing database versions, provenance and seals; do not label
meaning/passage/applicability changes as semantic-preserving re-verification. Mutable research
Markdown is governed separately by the [retention decision](../README.md).

If the current lifecycle cannot create that successor without breaking old reproducibility,
record the specific I02 requirement rather than bypassing checks. **Acceptance:** Original import
still reproduces its aggregate; successor citations are claim-specific; no guidance is published
or unsupported source marked current. Add PostgreSQL importer/lifecycle tests and successor
SC02/03/20/22–24 coverage. Do not add later suite Facts merely for this task.

## P-I03

### Vocabulary for domestic first issuance and loss only

**Prerequisite:** Shared I02 accepted/implemented and reviewed Fact meanings.
**Bound:** P01/P03/P04 selection; only required history/loss Facts, no consular/data-change/
representation expansion or deadline derivations.

Confirm none semantics; add passport_ever_issued and passport_loss_location if the accepted
contract requires them. Use existing Fact registration/publication patterns and bilingual
Service Questions, preserving old enum values and old renewal behavior unless an approved
successor rollout explicitly replaces it. Do not activate candidates for unavailable/unresearched
versions that interfere with the current interview.

**Acceptance:** SC01/04–06/13/60/63/64/70; pure/ORM typed-registration and deterministic-priority
tests, invalid keys before registration and correct types afterward; baseline imports reproducible.

## P-I04

### One domestic first-issue or loss importer per PR

**Prerequisites:** P-I01, P-I03 and shared I02; named author, reviewed relevant documentary/
military/representation conditions and recorded G01/G05/G06 disposition.
**Bound:** Separate PRs for P01, P03 and P04. Start with self-submitted ordinary adult cases;
no unreviewed minors, agents or combined data changes.

For each scope, import version-owned checklist, steps, fee components, warnings and routing
with claim evidence. One explicit atomic public entry calls a private builder then final
verification exactly once. P03 retains domestic loss-report distinctions; P04 retains its
separate department/document context. Unknown money/routes are not zero or a guessed office.

**Acceptance:** Publisher-required scenario kinds plus applicable SC01/04–07/14–24/59/61/66/68/69;
late-failure rollback, repeat imports, strict drift rejection, source coverage and no automatic
approval/publication. Full evidence gates still apply to a bounded subset.

## P-I06

### Passport damage, data changes and combined cases

**Prerequisites:** Shared I02 and G04/G07/G08 closure for the exact subcase.
**Bound:** One reviewed transaction decision table before adding candidates. Start with P05,
then the P06/P02 overlap. National ID N09 is separate N-I06, not part of this task.

Specify document-state/change-kind combinations including UNKNOWN. Establish whether the
transaction is one replacement, renewal with conditional evidence or ordered operations. No
double charging, generic other catch-all or edit-in-place booklet claim. Changes to existing
selection follow the accepted successor/catalog rollout.

**Acceptance:** Applicable SC08–10/28/50/51/59/67; pairwise non-overlap, valid combined facts,
inconclusive unresearched combinations and no first-match priority. Consular damage/data changes
also need P-I07's mission gates; a domestic decision does not establish overseas handling.

## P-I07

### One passport or return-document mission/output per PR

**Prerequisites:** Shared I02, applicable D04–D06 and G06/G08 resolutions; adult first-passport
checklist research when relevant. D07/G09 belong to the separate ID workstream.
**Bound:** One mission and one output family. MFA baseline is not all-countries coverage.

Verify territory, transaction, proof alternatives, approvals, charge/currency/payment, collection
and dates. Resolve age/photo/validity discrepancies. Country/region Facts feed evidenced rules;
applicants do not decide legal competence. Temporary/newborn return documents remain separate
outputs, and no unverified mission receives live data.

**Acceptance:** Applicable SC45–SC54/60/61/68, cross-mission negatives and currency isolation;
no universal photo/short-validity rule or assumed airline/transit acceptance. Other missions and
unresearched adult-first-issue paths remain unsupported.

## P-I08

### Publish only the reviewed passport subset

**Prerequisites:** Exact included rows' research, implementation and review gates closed.
**Bound:** Coherent passport Procedure Versions through the staff lifecycle, independently of
National ID suite completion. Do not self-approve or deploy in a code PR.

Assign author, independent bilingual reviewer and applicable specialists. Check every active
candidate has its intended usable version and every consequential Fact an active Question.
Reverify volatile evidence, resolve discrepancies, run required Planning Scenarios, inspect
actual Arabic/English plans and obtain independent approvals. Run PostgreSQL publication/
importer/API and pure-planner tests plus CI lint/type/migration checks.

**Acceptance:** Applicable SC59–SC70, honest local unknowns, unsupported-case coverage, preserved
required database histories and import seals. Update this catalog with exact version/PR and
remaining gaps; do not claim complete support for blocked families. Retire baseline Markdown
only via the separate [exit criteria](../README.md#when-the-old-markdown-can-leave-the-active-tree).

## Done for this documentation reorganization

Passport research is independent from the ID suite. Its evidence date, material claims,
transaction boundaries and review blockers remain explicit; no gate was closed by the split.
The source registry retains original aliases and narrow cross-family references. Scenario
specifications are future requirements, not newly executed tests or human approvals.
