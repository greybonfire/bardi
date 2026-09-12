# Production acceptance scenarios for the suite

These are **research scenario specifications**, not executed tests or live PlanningScenario rows.
The PR containing this pack does not implement the proposed Facts or candidate Procedures.
Convert only the scenarios for a reviewed content increment to the existing production scenario
model. Do not add a second research engine or resurrect the retired prototype.

Use evaluation date **2026-09-12** unless the row gives another date. Pin the rules contract and
all evidence freshness in the eventual fixtures. Government availability is never a test-time
network lookup. Public result families below are the existing `plan`, `next_question`,
`inconclusive`, and `invalid`; claim IDs refer to [claims.md](claims.md).

## Fixture conventions

`P` means the proposed domestic passport fixture: citizen `egyptian`, location `inside_egypt`,
class `ordinary`, state `expired`, birth date `1990-06-01`, sex `female`, student `false`,
National ID status `valid_current_data`, service level `standard`. Its proposed additional
Facts are: passport ever issued `true`, data change `none`, record discrepancy `none`, marital
status `single`, marital status recorded in ID `true`, submitter `self`. Use a verified fixture
service point or explicitly unresolved routing; do not invent a real office association.

`N` means the proposed domestic ID fixture: citizen `egyptian`, location `inside_egypt`, possession
`held`, data change `none`, expiry `2026-06-01`, birth date `1990-06-01`, student `false`.
Proposed additional Facts: ID ever issued `true`, record discrepancy `none`, marital status
`single`. Domestic fees and precise routing remain explicitly unknown unless the increment
provides new evidence.

These baselines use the exact Fact keys in [facts-and-questions.md](facts-and-questions.md).
Shorthand changes below replace baseline values; “omit” removes the key, never supplies `null`.
The row's channel/mission is a **knowledge-fixture scope**, not an arbitrary hidden case Fact.
Every other consequential condition in a future fixture must either be answered explicitly or
appear as the expected next Question; no test may silently default omitted Facts to false.

For `plan`, assert the selected Procedure/version and inclusion/exclusion of named claims,
fee components, and unresolved sections. After implementing a new row, bind these research IDs
to explicit imported semantic IDs. Do not assert only that the request returns HTTP 200.

## Passport cases

| ID / kind | Input or setup | Required future behavior |
| --- | --- | --- |
| SC01 positive | P; state `none`, ever issued `false` | Select P01 after its publication gates; no previous-passport original requirement; C-P-01/05/06 apply. |
| SC02 positive | P unchanged | Select P02 successor fixture; only the ordinary issuance fee branch, not replacement fee. |
| SC03 supported edge | P; state `pages_full`, passport otherwise unexpired | Same P02 transaction; do not require an expired passport in addition to full pages. |
| SC04 positive | P; state `lost`, loss location `inside_egypt` | Select P03; include C-P-12 and C-P-17; exclude a mandatory police-station report. |
| SC05 positive | P; state `lost`, loss location `outside_egypt`; listed arrival/identity evidence available | Select P04; include C-P-13's department-specific step, not P03's loss process. |
| SC06 unknown | SC04 but omit loss location | `next_question` resolving `passport_loss_location`; no chosen loss procedure yet. |
| SC07 negative | SC05 with lost-passport/arrival proof unavailable and G05 unresolved | `inconclusive` where the submission path cannot be established; do not invent a substitute or direct the case into P03. |
| SC08 negative | P; state `damaged`, G04 still unresolved | P05 is blocked; no complete damage-specific plan fabricated from P03. After G04 closes, add a positive surrender/inspection scenario. |
| SC09 negative | P; state `valid_with_pages`, data change `profession` | Investigate P06; with G04/G07 unresolved, `inconclusive`; never say the existing booklet can be edited. |
| SC10 negative | P; state `valid_with_pages`, data change `none` | P07 remains unsupported until an early-renewal window is evidenced. |
| SC11 supported edge | SC01; birth date `2011-09-13`, National ID status `not_held` | Under-15 identity branch C-P-02; exclude C-P-01; representation uncertainty must not become an invented permission. |
| SC12 supported edge | SC01; birth date `2011-09-12` | Exactly 15: C-P-01; no under-15 birth-certificate-only branch. |
| SC13 unknown | P; omit birth date while both age branches are usable | `next_question` resolving `birth_date`, not a request to submit a derived age. |
| SC14 supported edge | P; sex `male`, birth date `2007-09-13`; previous military notation absent | C-P-04 age threshold not reached. Do not ask for military proof solely from sex. |
| SC15 supported edge | P; sex `male`, birth date `2007-09-12`; previous notation `no_notation` | C-P-04 age threshold reached; correct documentary branch after military review. |
| SC16 supported edge | P; male; birth date `1941-03-17`, then `1941-03-18`; no exempt notation | Assert the birth-cohort boundary independently of age. |
| SC17 positive | P; male, relevant military age; previous notation `not_required` | C-P-11 exception suppresses duplicate military proof; do not suppress it for `other_notation`. |
| SC18 unknown | SC17 but omit previous notation | A Question only if the reviewed exception materially changes the checklist; no assumed exemption or duplicated mandatory proof. |
| SC19 positive | P; male student, current enrollment explicitly records postponement | Include the reviewed student-specific condition separately from an authority's military-status determination. |
| SC20 unknown | P; omit `is_student` | Usable C-P-03 condition asks the student Question; resubmitting `false` removes that item, `true` retains it. |
| SC21 supported edge | P in Khadamat Misr fixture; female, married, status absent from ID | Include C-P-09 and C-P-08 only with their channel/evidence scope; neither unknown fee nor unverified total becomes zero. |
| SC22 positive | P; `service_level=urgent`, then `premium` | Select exactly the corresponding optional component; never both. Assert C-P-20's different jurisdiction behavior. |
| SC23 unknown | P; omit `service_level`, current trusted fee applicability depends on it | `next_question` for service level; after answering, select the fee deterministically. |
| SC24 negative | SC22 but accelerated fee evidence expired/unsupported | Do not use stale evidence to claim a current amount or ask a fact that can only resolve that unusable fee. Keep monetary uncertainty. |
| SC25 unknown | P; birth date `2011-09-12`, minor submitter reported only as `other`, proof not researched | No automatic authorization. Route/representation remains inconclusive as necessary; do not interpret `other` as guardian. |
| SC26 supported edge | Reviewed C-P-10 fixture: adult sibling for minor; separately paternal uncle with both parents abroad | Each allowed branch requires its own researched circumstances/proof; changing the relevant circumstance removes that branch. |
| SC27 negative | Reviewed agent fixture; authorization permits collection only, action is application | No inferred authority to apply. Generic presence of a power of attorney is insufficient. |
| SC28 negative | P; expired passport plus profession or multiple data changes | Coherent case. Before a reviewed P02/P06 boundary rollout, do not claim the new suite resolves it; after rollout, never select two candidates or ignore changes. |

SC11/SC12 require a fully reviewed minor representation fixture before they can count as
`supported_edge` PlanningScenario rows producing a plan. Until then, retain them as blocked
research specifications. Apply the same rule to any positive row whose catalog gate is still open.

## National ID cases

| ID / kind | Input or setup | Required future behavior |
| --- | --- | --- |
| SC29 positive | N; birth date `2011-09-12`, possession `none`, ever issued `false`, omit expiry, student `true`; reviewed S07 channel | Select N01 only after first-issuance gates; no old-card requirement. Use the exact supported channel proof, not a nationwide generalized guarantor rule. |
| SC30 negative | SC29 but not a student; G03 unresolved | No copied student checklist; `inconclusive` for unresearched first-issuance evidence. |
| SC31 positive | N unchanged; reviewed renewal fixture | Select N02. Include supported previous-card evidence; keep unknown fee/routing explicit. |
| SC32 supported edge | N; expiry equals evaluation date, then previous day | Preserve existing `card_expired_before_evaluation_date` semantics: equality is not “expired before”; N10's unverified window is not invented. |
| SC33 negative | N; possession `lost`; old-original discrepancy unresolved | N03 cannot require the unavailable original or an invented substitute. Remains blocked by D02. |
| SC34 unknown | N; possession `damaged`; D03/G02 unresolved | N04's damaged-card evidence can be retained in draft; a complete public plan must not invent the rest. |
| SC35 negative | N; change `residence`, expiry future or past | Investigate N05 in either case; with G03 unresolved, no guessed utility-bill/lease menu and no unchanged renewal fallback. |
| SC36 negative | N; change `profession` | N06 needs domestic proof evidence. Do not transplant a London/Dubai employment checklist. |
| SC37 negative | N; change `marital_status`, separately marriage/divorce/widowhood | N07 needs the applicable evidence/registration branch. Do not require marriage proof for every marital-status change. |
| SC38 negative | N; change `other`, record discrepancy `contested` | N08 specialist boundary; no ordinary counter-correction promise. |
| SC39 negative | N; change `multiple`, or loss/damage plus one change | N09/G07; coherent input, `inconclusive` until transaction/charge sequencing is researched. |
| SC40 unknown | N; omit change kind | Ask the consequential change Question before asserting unchanged renewal. |
| SC41 unknown | N; omit expiry; possession held and no changes | Ask `national_id_expiry_date`; no current-date guess. |
| SC42 contradictory | N; possession `none` while expiry remains submitted | Existing declared contradiction yields `invalid`; lost-with-known-expiry must not trigger this invariant. |
| SC43 supported edge | Reviewed deadline fixture; expiry `2026-01-31`, evaluate `2026-04-30` and `2026-05-01` | Preserve existing calendar-month deadline and “passed” boundary; no automatic renewal ineligibility or calculated fine. |
| SC44 negative | N; card not expired and no changes | N10 remains unsupported without a verified early-renewal window. |

| SC71 supported edge | SC29 with birth date `2011-09-13`, then `2011-09-12` | Assert the reviewed first-ID age boundary at the 15th birthday; the adult obligation must not apply a day early. Do not infer an absolute ban on voluntary earlier issuance from the obligation alone. |

After G03 closes, add **separate positive and negative proof-alternative scenarios** for N05,
N06 and N07 before publication. SC35–SC37 are gap-preservation tests, not a substitute for those
positive scenarios or for required production scenario kinds.

## Consular, output, and scope cases

| ID / kind | Input or setup | Required future behavior |
| --- | --- | --- |
| SC45 negative | Overseas first passport for an adult; only S14's child checklist loaded | P08 remains inconclusive for the adult case; do not ask for parents' documents as a fabricated adult checklist. |
| SC46 positive | Reviewed mission child-first-passport fixture | P08 contains C-O-01 only with the applicable mission and representation scope; not P14 unless the output purpose matches. |
| SC47 unknown | Overseas renewal; omit country/region needed by verified mission predicates | Ask the relevant source location Fact; never default to London. |
| SC48 negative | P09 at a mission with unresolved S14/S18 validity/photo conflict | No asserted full-term/short-term validity or photo count chosen by convenience; D04/D05 governs publication. |
| SC49 positive | Reviewed consular loss fixture | P10 includes approval and the proper loss-report branch; C-P-12's domestic exception must not suppress it. |
| SC50 negative | Consular damage case; source combines loss/damage with loss-only documents | P11 remains blocked until that distinction is reviewed; no fictional requirement to report a loss that did not occur. |
| SC51 negative | Consular renewal plus changed data; standalone transaction/charge unknown | P12 does not create an extra Procedure or fee automatically. |
| SC52 negative | Abroad, urgent onward travel required, passport unavailable | Do not choose P13 just because it appears faster; a return-only document does not satisfy general-travel purpose. |
| SC53 positive | Reviewed London return-only fixture with evidence/approval conditions met | P13 retains its limited output and unresolved transit acceptance where applicable; no travel guarantee. |
| SC54 positive | Reviewed newborn return fixture | P14 uses its own parental/birth evidence; no ordinary passport fee or ordinary passport validity copied into it. |
| SC55 negative | Sydney first ID; no verified live committee date | N11 has no fabricated appointment or permanent-counter availability; D04/G09 remain open. |
| SC56 positive | Reviewed Dubai ID renewal fixture | N12 uses Dubai-only evidence, currency, and approximate timing. London or domestic claims do not enter this version. |
| SC57 negative | London ID data changes; current tariff unresolved | N13 can only use reviewed conditional evidence; D07 prevents an assumed current amount or calculated price increase. |
| SC58 negative | Overseas ID lost or damaged; only N12 renewal sources present | N14/N15 remain unsupported; do not require an old original in a loss case or assume renewal covers every replacement. |

## Integration, trust and privacy checks

| ID / kind | Setup | Acceptance requirement |
| --- | --- | --- |
| SC59 negative | Both passport and ID lost; no evidenced proof alternative | No circular prerequisite plan and no invented accepted identity document. |
| SC60 negative | Non-ordinary passport, refugee travel document, or non-Egyptian citizen | Do not select an ordinary Egyptian-citizen passport/ID Procedure. |
| SC61 unknown | Supported checklist with unverified exact office coverage | Keep supported guidance and local routing uncertainty where the contract permits; no invented nearest office. |
| SC62 negative | Only a portal directory entry is available | No end-to-end online issuance promise or inferred eligibility for first issuance/data changes. |
| SC63 invalid | Submit invalid enum, `null`, impossible date, or a derived Fact directly | Existing typed-validation diagnostics; never silently coerce to omission or a permissive value. |
| SC64 contradictory | Explicit never-issued history plus explicit lost/damaged existing document | After a reviewed contradiction is added, `invalid`; omission of history is not contradictory. |
| SC65 integration | Import old renewal, add the suite's new Question, retry old import and run preserved scenarios | Demonstrate the signature/coexistence behavior in I02. Do not hide failures by rewriting stored scenario signatures or weakening drift checks. |
| SC66 integration | Import old/new packs in each supported order and repeat each public import | Deterministic idempotence; final verification exactly once; any late verification failure rolls back all writes. |
| SC67 integration | Two candidates become TRUE for one combined case, or version scopes overlap | Never pick the first/cheapest/newest arbitrarily; preserve deterministic inconclusive/configuration behavior and fix the authored overlap. |
| SC68 trust | Before version effective date; after evidence reverify date; after withdrawal | Respect version and evidence state. Retrieval date alone never authorizes historical application. |
| SC69 privacy | Interview and generation for any new family | Submitted Facts remain transient; no case-Fact database rows, raw logs, uploads or analytics payloads introduced. |
| SC70 trust | Consequential condition references a source Fact with no Service Question | Publication validation rejects the defective draft; runtime retains existing configuration-invalid fallback. |

For each implemented Procedure Version, use `required_scenario_kinds` and the existing publisher
to determine the mandatory coverage. Table labels describe intent; they do not bypass model
validation. A blocked negative scenario cannot stand in for a positive scenario required to
publish a supposedly supported Procedure Version.
