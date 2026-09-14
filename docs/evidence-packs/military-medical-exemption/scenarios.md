# Production acceptance scenario specifications

These are future requirements, **not newly executed tests or imported PlanningScenario rows**.
Pin evaluation date `2026-09-12`, rules contract and evidence freshness in each eventual fixture.
Government pages are never fetched during tests. Only implemented, reviewed scope may supply a
positive or `supported_edge` publication scenario; unresolved research cannot substitute for one.

`M` means: existing military Service; citizen `egyptian`; application `inside_egypt`; proposed
subject `own_health_assessment`; service history `never_started`; assessment `no_record`;
exemption record `no_decision_communicated`; current review instruction `false`.
Certificate state/history and accessibility are omitted unless consequential. If an implemented
version adds an age/sex predicate, its fixture must supply exact values or expect a Question;
this baseline establishes no legal age window.

`R` means: M with subject `existing_medical_exemption_document`, assessment `recorded_unfit`,
exemption record `granted`, certificate ever issued `true`, certificate state `lost`.
Use the exact keys in [workflow-and-facts.md](workflow-and-facts.md). “Omit” removes a key; it does
not send `null`. A plan assertion must include exact authored stage, Procedure/version, claims,
included/excluded items, fee state and routing uncertainty, rather than only HTTP 200.

## Administrative and health boundaries

| ID / kind | Setup | Required behavior after the relevant increment |
| --- | --- | --- |
| MS01 positive | M with a fully evidenced/reviewed A01 fixture | Plan only the administrative assessment process, if the accepted model supports it; no matched disease rule or exemption outcome. Until G02 closes, retain an inconclusive research specification. |
| MS02 positive | M; assessment `referred_or_pending`, reviewed A02 instructions | Present the applicable referral steps; pending is not granted. |
| MS03 supported edge | M; assessment `recorded_unfit`, exemption record `no_decision_communicated` | A03 distinguishes the medical communication from the remaining authority paperwork; no fabricated certificate. |
| MS04 positive | M; exemption `granted`, certificate ever issued `false`, state `not_issued`; reviewed A04 | First issuance/collection path, not replacement. Scope must have actual first-certificate evidence. |
| MS05 positive | R; current A05 replacement evidence and review | Certificate replacement after the recorded exemption, without a new automatic diagnostic assessment. Include only current verified charge components. |
| MS06 supported edge | R but certificate `held`; another copy requested | Use the separately verified repeated-issue subcase; do not require the applicant to declare a fictitious loss. |
| MS07 negative | R but certificate `damaged`; only loss instructions available | A06 stays unsupported until damage is evidenced; no loss report inferred. |
| MS08 unknown | M; omit assessment record where stage selection depends on it | `next_question` for the source record, not “are you medically unfit?”. |
| MS09 unknown | M; assessment `recorded_unfit`, omit exemption record | Ask about the separate communicated decision if consequential; do not default to granted. |
| MS10 negative | M; assessment/exemption `unclear` supplied explicitly | No repeat of the same answered Question; local clarification/inconclusive path, no coercion to fit/refused. |
| MS11 negative | Civilian psychiatric letter only; military assessment `no_record` | Does not qualify a military exemption. No automatic hospitalization/Council-certificate requirement. |
| MS12 negative | Civilian physical-health report only; military assessment `no_record` | Same authority boundary as MS11; no symptom, height, weight, vision or other measurement classifier. |
| MS13 negative | User has a disability card but no military decision | Card is not substituted for the decision; no universal exemption or home-visit entitlement. Do not introduce an unneeded card-number field. |
| MS14 negative | Only S02's first psychiatric entry loaded, G06 open | No blanket C06 requirement for every psychiatric/neurological case; blocked evidence must not trigger requests for sensitive medical history. |
| MS15 supported edge | Reviewed C06 documentary subcase and an expressly distinct later psychiatric subcase | Apply the item only to the exact reviewed administrative condition; separate inclusion/exclusion assertions. Do not require an applicant to classify their diagnosis into statutory terminology. |
| MS16 negative | Assessment `recorded_fit` or exemption `refused`; review remedy unresearched | A07; no guarantee of appeal success, automatic repeat examination, or deadline calculation. |
| MS17 supported edge | R plus current review instruction `true` | Do not ignore the new instruction because the old certificate exists. Apply only reviewed A07 sequencing; otherwise inconclusive. Coherent input, not a contradiction. |
| MS18 supported edge | Reviewed A08 fixture; needs assistance `true` | Show only the scoped supported contact/arrangement; no guaranteed home appointment or universal zero fee. |
| MS19 unknown | A usable A08 condition needs assistance Fact, omitted | Ask the non-clinical attendance question. If only untrusted/unavailable content depends on it, do not ask. |
| MS20 negative | Subject health, service history `currently_serving` or `previously_served` | No pre-service exemption plan silently applied to discharge/reserve/compensation. Scope gap is not legal ineligibility. |
| MS21 negative | Application `outside_egypt`, or nationality/age scope not researched | No domestic or London family-exemption fallback; no copied fee/checklist. |
| MS22 contradictory | For the same exemption, certificate ever issued `false` with state `held`, `lost` or `damaged`, or `true` with `not_issued` | After the reviewed invariant is authored, `invalid` with its declared diagnostic; omitted issuance history must not trigger it. A pending replacement retains the old certificate's state. |
| MS23 invalid | Unknown enum, clinical free text, explicit `null`, malformed date or submitted derived age | Existing typed API validation; no coercion or new diagnostic classifier. |

MS11-MS14 use hypothetical background descriptions, not persisted or newly accepted diagnosis
Facts. Assert that the generated guidance does not infer medical conclusions; invalid-payload
coverage for attempted diagnosis keys belongs in MS23/MS32.

## Evidence, coexistence and publication

| ID / kind | Setup | Required acceptance |
| --- | --- | --- |
| MS24 temporal | Authored S02 historical content versus S03-amended content | Verify the exact amendment boundary if historical versions are implemented; no current old Article 4. Publication and retrieval dates must not replace commencement dates. |
| MS25 negative | Only S04's 2018 service announcement is present | No current first-application, online examination, guaranteed delivery or fee amount inferred. |
| MS26 trust | Matching record Facts but legal Basis/item evidence untrusted, stale or withdrawn | Preserve existing trust behavior; case answers cannot unlock blocked Basis content or make stale fees current. |
| MS27 unknown | Supported process, exact region or payable amount unknown | Keep uncertainty local where permitted; no guessed nearest office, zero price or grand total. |
| MS28 integration | Original family selector plus domestic medical selector | Demonstrate both predicates TRUE for a domestic medical case; never pick the first. Test the approved replacement design and legacy compatibility before enabling the candidate. |
| MS29 integration | Add Service Question, retry family import and preserved scenarios | Demonstrate signature impact; no rewriting stored signatures or weakening integrity checks. Both supported import orders and repeated imports must pass after the design fix. |
| MS30 supported edge | Medical facts and a genuine family circumstance both present | Coherent input; no automatic declaration that the family ground is false. Subject choice affects the requested assistance, not the truth of either ground. |
| MS31 publication | Missing bilingual Question, independent legal/military approval or required positive scenario | Publication rejects the draft through existing gates. No fake approvals or custom bypass. |
| MS32 privacy | Generate/interview medical and certificate paths, including rejected input | No raw Facts, certificate identifiers, medical history, traces or request bodies persisted/logged. No new upload or external case-lookup request. |
| MS33 integration | Late failure during draft import and a second identical import | Atomic rollback, deterministic idempotence, final verification exactly once; all unrelated aggregates preserved. |
| MS34 negative | General military-card loss/fee text or military-academy standard loaded | Neither becomes the medical-exemption certificate procedure or a conscription fitness criterion. |
| MS35 temporal | Adverse decision plus S01's historical Article 18 text only | No automatic 30-day countdown, implied suspension, or current court-route claim before G07. A re-examination instruction is not treated as the same remedy. |
| MS36 unknown | Medical subject but original family Questions are otherwise answerable | After the approved selector rollout, ask only Questions consequential to the requested supported process. No father/sibling interview caused solely by the legacy domestic catch-all. |

Map each implemented row to the existing `PlanningScenario.Kind` and public result family.
Integration/privacy checks may belong in pure/ORM/API tests rather than being forced into a
PlanningScenario enum. Fixtures must show exact conditions for a positive administrative plan;
“there is a health problem” is never sufficient evidence of exemption.
