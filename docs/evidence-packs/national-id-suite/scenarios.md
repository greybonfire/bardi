# National ID acceptance scenario specifications

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


`N`: citizenship egyptian, application inside_egypt, card possession held, data change none,
national_id_expiry_date 2026-06-01, birth_date 1990-06-01, is_student false. Proposed:
national_id_ever_issued true, national_id_record_discrepancy_kind none, marital_status single.
Domestic fees and exact routing remain unknown unless the increment provides evidence.
Exact keys are in [Facts](facts-and-questions.md).


## Domestic cases

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

After G03 closes, add separate positive and negative proof-alternative tests for N05/N06/N07;
SC35–SC37 preserve gaps but cannot replace positive publication coverage. SC47 is the same
mission-scope guard applied to ID, independently of the passport version. SC59 links only the
cross-document dependency to [passport scenarios](../passport-suite/scenarios.md).

## Consular and output cases

| ID / kind | Input or setup | Required future behavior |
| --- | --- | --- |
| SC47 unknown | Overseas renewal; omit country/region needed by verified mission predicates | Ask the relevant source location Fact; never default to London. |
| SC55 negative | Sydney first ID; no verified live committee date | N11 has no fabricated appointment or permanent-counter availability; D04/G09 remain open. |
| SC56 positive | Reviewed Dubai ID renewal fixture | N12 uses Dubai-only evidence, currency, and approximate timing. London or domestic claims do not enter this version. |
| SC57 negative | London ID data changes; current tariff unresolved | N13 can only use reviewed conditional evidence; D07 prevents an assumed current amount or calculated price increase. |
| SC58 negative | Overseas ID lost or damaged; only N12 renewal sources present | N14/N15 remain unsupported; do not require an old original in a loss case or assume renewal covers every replacement. |

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
