# Passport acceptance scenario specifications

These are **future research scenario specifications**, not executed tests or live
PlanningScenario rows. Convert only a reviewed increment using the existing production model;
no second engine or retired prototype. The default evaluation date is **2026-09-12**. Pin the
rules contract and evidence freshness; no test-time government lookup. Result families remain
plan, next_question, inconclusive and invalid. Claims refer to [this ledger](claims.md).

Shorthand replaces baseline values; omit removes a key, never sends null. Mission/channel is
knowledge-fixture scope, not a hidden case Fact. Explicitly answer all other consequential facts
or assert the next Question: no default false. For plans, assert Procedure/version, included and
excluded claims, fee components and unresolved sections, not merely HTTP 200. Bind research IDs
to imported semantic IDs when implementing.


## Fixture convention


`P`: citizenship egyptian, application inside_egypt, passport class ordinary, state expired,
birth_date 1990-06-01, sex female, is_student false, national_id_status valid_current_data,
service_level standard. Proposed: passport_ever_issued true, passport_data_change_kind none,
passport_record_discrepancy_kind none, marital_status single, marital_status_recorded_in_national_id
true, passport_presenting_person_relationship self. Use a verified fixture point or explicit
routing uncertainty, not an invented real office. Exact keys are in [Facts](facts-and-questions.md).


## Domestic cases

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

SC11/SC12 require reviewed minor representation before they count as supported-edge plans;
until then they are blocked specifications. The same gate applies to any positive scenario.
SC47 applies to this suite's verified passport mission predicates. SC59 retains the narrow
cross-document dependency with the [National ID suite](../national-id-suite/scenarios.md).

## Consular and output cases

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

## Integration, trust and privacy

Shared IDs SC59–SC70 identify guard templates exercised for the Service under review, not one
joint administrative fixture. A passing passport scenario is not ID coverage, or vice versa.
SC60 tests non-Egyptian input for either Service and non-ordinary/refugee output boundaries for
passport selection. See the single technical [I02 task](../catalog-compatibility.md).

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

Use required_scenario_kinds and the existing publisher for mandatory coverage. Intent labels
do not bypass validation. A blocked negative case cannot substitute for a positive scenario
needed to publish a supposedly supported version. No gate was closed by the documentation split.
