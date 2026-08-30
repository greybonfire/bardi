# Temporary family exemption from military service evidence pack

Issue: #4  
Parent spec: #1  
Research snapshot: 2026-08-26  
Status: research-complete draft; **specialist legal/military-status review and independent bilingual/source review required before authoritative prototype use**

This pack pressure-tests temporary family-exemption modeling under Egyptian military-service law. It deliberately does not tell a user that they are legally exempt. It identifies researched statutory grounds, the Facts and evidence needed to evaluate them safely, the current authority/routing structure, and the points at which the planner must remain inconclusive or defer to the Recruitment and Mobilization Administration.

A consequential 2026 amendment is incorporated: Law No. 2 of 2026, published 2026-03-24 and effective the following day, amended the missing-person temporary-exemption ground to include terrorist operations in addition to war operations. Pre-2026 wording must not be used as current law for that basis.

## 1. Goal and Procedure identity

- **Goal ID:** `handle_military_service_paperwork`
- **Goal (Arabic):** إجراءات التجنيد والخدمة العسكرية
- **Goal (English):** Handle military-service paperwork
- **Procedure ID:** `temporary_family_exemption_from_military_service`
- **Procedure (Arabic):** طلب الإعفاء المؤقت من الخدمة العسكرية لأسباب عائلية
- **Procedure (English):** Apply for temporary exemption from military service on a family ground
- **Primary Authority:** Egyptian Armed Forces — Recruitment and Mobilization Administration
- **Administrative output:** an authority-determined temporary exemption status and, when approved/available, an exemption certificate
- **Research version ID:** `temporary_family_exemption_from_military_service.research-2026-08-26`
- **Specialist review:** required for every published legal-eligibility conclusion in this fixture

The Goal can later contain other military-paperwork Procedures such as final exemption, postponement, travel permission, status regularization, and certificate replacement. This Procedure is only the family-ground **temporary exemption** path.

## 2. Supported boundary

The research fixture is intended for a person whose military-service file is handled by the Egyptian Recruitment and Mobilization system and who seeks a temporary family exemption on one or more Article 7 family grounds.

The pack can describe candidate statutory grounds and route a person to the competent authority. It must not autonomously resolve disputed kinship, earning incapacity, legal-support status, missing-person status, or another legal interpretation that the recovered sources leave to official or specialist determination.

### Supported research cases

- ordinary family circumstances corresponding to Article 7 temporary-exemption clauses identified below;
- one or more candidate Eligibility Bases can be evaluated from typed Facts where their meaning is sufficiently clear;
- official or authority-recorded statuses can be used as Facts when the legal rule depends on a determination such as inability to earn;
- current domestic routing to the appropriate Recruitment and Mobilization region can be attempted from governorate context;
- current exemption-certificate service behavior can be described without assuming it substitutes for first-time legal adjudication.

### Recognized unsupported or escalated cases

- final/permanent exemption grounds;
- medical fitness decisions;
- student postponement;
- dual-nationality/exception rules;
- evasion/status-regularization cases;
- disputed paternity, sibling status, custody, maintenance, or family-record accuracy;
- deciding medical or economic “inability to earn” from lay descriptions rather than an accepted authority status/document;
- deciding who is the “largest/eldest eligible for conscription” where eligibility of relatives is legally disputed or incomplete;
- missing-person cases outside the statutory war/terrorism context;
- representation/power-of-attorney workflows;
- overseas/consular military-service workflows;
- any basis whose specialist-review gate has not been completed for publication.

## 3. Eligibility Bases

The Procedure is intentionally modeled with additive Eligibility Bases. More than one researched basis may be factually suggested; the planner must not silently prioritize one or claim that matching a fixture rule is an authoritative legal decision.

| Basis ID | Statutory research ground | State | Specialist review |
| --- | --- | --- | --- |
| `family.only_son_living_father` | only son of a living father | current-as-researched | required |
| `family.support_father_or_incapable_brothers` | family-support ground involving a father unable to earn and the related incapable-brother wording in Article 7/Second(b) | current-as-researched; exact sub-branch semantics need review | required |
| `family.support_mother` | sole family-support ground for a mother who meets one of the statutory family-status conditions | current-as-researched | required |
| `family.support_unmarried_sisters` | sole family-support ground for unmarried sister(s) | current-as-researched | required |
| `family.missing_war_or_terror_relative` | largest eligible conscription relative among the named family relationships where the relevant person is missing due to war or terrorist operations | current from 2026-03-25 | required |
| `family.sibling_current_service` | sibling/eldest-remaining-brother temporary exemption while another brother is in compulsory service or qualifying reserve recall, subject to statutory exclusions | current-as-researched | required |

### Important modeling limitation for Article 7/Second(b)

The recovered 1980 Gazette wording couples support of a father unable to earn with wording concerning an incapable brother or brothers. This pack does not freeze whether those phrases should become one Eligibility Basis with alternatives, two Basis records, or one Basis plus a nested condition until a specialist reviews the current consolidated statute and implementing practice. The table uses one research Basis to avoid pretending the semantic split is settled.

## 4. Facts

Facts below are candidate inputs. Where a statutory term is itself a legal/medical determination, the fixture prefers an authority-recorded status rather than asking the user to make that conclusion.

| Fact key | Type | Example values | Purpose / review note |
| --- | --- | --- | --- |
| `application_location` | enum | `inside_egypt`, `outside_egypt` | domestic boundary |
| `residence_governorate` | stable enum/key | `giza`, `sharqia` | Recruitment-region routing |
| `father_alive` | boolean | `true`, `false` | only-son and family-support branches |
| `other_living_sons_of_father_count` | integer >= 0 | `0`, `2` | derive only-son candidate; kinship semantics require review |
| `father_unable_to_earn_status` | enum | `authority_documented_unable`, `not_documented_unable` | do not infer earning incapacity from free text |
| `other_capable_family_support_for_father` | enum | `none_known`, `present`, `unknown` | provisional sole-support input; legal meaning requires review |
| `mother_family_status` | enum | `widowed`, `irrevocably_divorced`, `husband_authority_documented_unable`, `other` | Article 7/Second(c) branch |
| `other_capable_family_support_for_mother` | enum | `none_known`, `present`, `unknown` | provisional sole-support input; legal meaning requires review |
| `unmarried_sisters_requiring_support_count` | integer >= 0 | `1` | sister-support branch |
| `other_capable_family_support_for_sisters` | enum | `none_known`, `present`, `unknown` | provisional sole-support input |
| `missing_relative_category` | enum | `officer`, `volunteer`, `conscript`, `citizen`, `none` | 2026 missing-person basis |
| `missing_relative_cause` | enum | `war_operations`, `terrorist_operations`, `other` | amended temporal rule |
| `missing_relative_alive_status` | enum | `missing`, `returned_or_proven_alive`, `unknown` | exemption-lapse branch |
| `applicant_largest_eligible_relative_status` | enum | `authority_documented_yes`, `authority_documented_no` | avoid locally adjudicating relatives' conscription eligibility |
| `sibling_service_status` | enum | `compulsory_service`, `reserve_recall`, `none` | Article 7/Third branch |
| `applicant_eldest_remaining_brother_status` | enum | `authority_documented_yes`, `authority_documented_no` | needed where Article 7/Third selects eldest remaining brother |
| `article7_third_exclusion_status` | enum | `none_documented`, `exclusion_present`, `unknown` | captures statutory sibling exclusions without hiding them in code |

`unknown` as a domain enum is used only where it is a meaningful authority/research status; generic missing input remains omission.

### Derived Facts

- `only_son_candidate = father_alive && other_living_sons_of_father_count == 0`.
- The pre-amendment Procedure Version applies through 2026-03-24 and the published amended version applies from 2026-03-25 (inclusive).
- The amended version's missing-relative Basis directly contains the terrorist-operations predicate; no runtime date-derived legal wording flag is used.

No derived Fact may convert `none_known` into a legal conclusion that the applicant is the statutory sole breadwinner. That mapping remains specialist-sensitive.

## 5. Questions

Questions are bilingual and write one Fact. The later picker should ask only those that can resolve a consequential candidate Basis or routing branch.

| Priority | Question ID | Writes | Arabic | English |
| ---: | --- | --- | --- | --- |
| 10 | `q.mil.application_location` | `application_location` | هل ستتعامل مع موقفك التجنيدي من داخل مصر أم من خارجها؟ | Will you handle your military-service status from inside or outside Egypt? |
| 20 | `q.mil.father_alive` | `father_alive` | هل والدك على قيد الحياة؟ | Is your father alive? |
| 30 | `q.mil.other_sons_count` | `other_living_sons_of_father_count` | كم عدد الأبناء الذكور الآخرين الأحياء لوالدك وفق بيانات الأسرة التي تعتمد عليها؟ | According to the family records you rely on, how many other living sons does your father have? |
| 40 | `q.mil.father_capacity` | `father_unable_to_earn_status` | هل لديك مستند أو حالة معتمدة تثبت أن والدك غير قادر على الكسب؟ | Do you have an accepted document/status establishing that your father is unable to earn? |
| 50 | `q.mil.mother_status` | `mother_family_status` | ما الحالة العائلية ذات الصلة لوالدتك؟ | What is your mother's relevant family status? |
| 60 | `q.mil.unmarried_sisters` | `unmarried_sisters_requiring_support_count` | كم عدد أخواتك غير المتزوجات اللاتي تدخل حالتهن في طلب الإعفاء؟ | How many unmarried sisters are relevant to the exemption request? |
| 70 | `q.mil.missing_cause` | `missing_relative_cause` | إذا كان الطلب مرتبطاً بشخص مفقود، فما سبب الفقد المسجل؟ | If the request concerns a missing person, what recorded cause of disappearance applies? |
| 80 | `q.mil.sibling_service` | `sibling_service_status` | هل أحد إخوتك حالياً في الخدمة الإلزامية أو مستدعى للخدمة في الاحتياط؟ | Is one of your brothers currently in compulsory service or called for qualifying reserve service? |
| 90 | `q.mil.governorate` | `residence_governorate` | ما محافظة محل الإقامة المستخدمة في معاملتك التجنيدية؟ | Which governorate of residence is used for your recruitment transaction? |

Questions that would ask the user to decide a contested legal term such as “Are you legally the sole breadwinner?” are deliberately avoided. The fixture instead records the underlying circumstance/status where possible and leaves legal classification to reviewed rules or the authority.

## 6. Applicability and Basis rules

The notation is research pseudocode, not a final JSON contract.

### Procedure boundary

```text
application_location == inside_egypt
and at least one temporary-family Basis is potentially reachable
```

The fixture does not encode a universal “military-service eligible” boolean from user assertions. A production route may require additional shared recruitment Facts once the specialist review and the other military Procedures define that boundary.

### Only-son candidate

```text
father_alive == true
and other_living_sons_of_father_count == 0
```

This is a **candidate** match pending reviewed kinship semantics and authority confirmation.

### Father/incapable-brother support ground

```text
father_unable_to_earn_status == authority_documented_unable
and support circumstances satisfy the reviewed Article 7/Second(b) interpretation
```

The second predicate is intentionally not frozen until specialist review resolves the exact sole-support semantics and the brother wording.

### Mother support ground

```text
mother_family_status in {
  widowed,
  irrevocably_divorced,
  husband_authority_documented_unable
}
and support circumstances satisfy the reviewed sole-support interpretation
```

### Unmarried-sister support ground

```text
unmarried_sisters_requiring_support_count > 0
and support circumstances satisfy the reviewed sole-support interpretation
```

### Missing-person ground

```text
applicant_largest_eligible_relative_status == authority_documented_yes
and missing_relative_category in {officer, volunteer, conscript, citizen}
and missing_relative_alive_status == missing
and (
  missing_relative_cause == war_operations
  or (
    evaluation_date >= 2026-03-25
    and missing_relative_cause == terrorist_operations
  )
)
```

The amendment boundary is explicit: terrorist operations are not backfilled into an earlier Procedure Version merely because the planner runs in 2026.

### Sibling-in-service ground

```text
sibling_service_status in {compulsory_service, reserve_recall}
and applicant/remaining-brother ordering satisfies reviewed Article 7/Third semantics
and article7_third_exclusion_status == none_documented
```

Again, eligibility ordering is not inferred from prose if the necessary authority-recognized family/service facts are unavailable.

## 7. Shared and Basis-specific claims

Shared Procedure claims and Basis-specific legal claims remain separate identities.

### Shared claims

| Claim ID | Type | English | State | Evidence | Specialist review |
| --- | --- | --- | --- | --- | --- |
| `mil.shared.supporting_documents` | Official Requirement | A person claiming exemption/postponement/exception should present documents supporting entitlement | current operational instruction | `EL-MOD-SUPPORTING-DOCS` | yes for basis-specific sufficiency |
| `mil.shared.temporary_cause_lapse` | Official Requirement / warning | Temporary exemption ends when its cause ends | current-as-researched statute | `EL-LAW127-TEMPORARY-LAPSE` | yes |
| `mil.shared.report_after_cause_lapse` | Official Requirement / warning | When the temporary-exemption cause ends, the person must present to the competent recruitment region within 30 days | current-as-researched statute | `EL-LAW127-TEMPORARY-LAPSE` | yes |

### Basis-specific legal claims

| Claim ID | Basis | State | Evidence | Specialist review |
| --- | --- | --- | --- | --- |
| `mil.basis.only_son_living_father` | `family.only_son_living_father` | current-as-researched | `EL-LAW127-ART7-II-A` | required |
| `mil.basis.support_father_or_brothers` | `family.support_father_or_incapable_brothers` | current-as-researched; semantics pending | `EL-LAW127-ART7-II-B` | required |
| `mil.basis.support_mother` | `family.support_mother` | current-as-researched | `EL-LAW127-ART7-II-C` | required |
| `mil.basis.support_unmarried_sisters` | `family.support_unmarried_sisters` | current-as-researched | `EL-LAW127-ART7-II-D` | required |
| `mil.basis.missing_war_or_terror_relative` | `family.missing_war_or_terror_relative` | current from 2026-03-25 | `EL-LAW2-2026-ART7-II-E` | required |
| `mil.basis.sibling_current_service` | `family.sibling_current_service` | current-as-researched | `EL-LAW127-ART7-III` | required |

No public claim above should be marked authoritative until the specialist gate is complete, even where the statutory text itself is current.

## 8. Documentary checklist findings

The current Ministry of Defense 2026 recruitment announcement publishes a general recruitment-document list and separately instructs people entitled to exemption/postponement/exception to present supporting documents. The research pass did **not** recover a current first-party basis-by-basis documentary checklist for each family exemption ground.

Therefore:

- the shared claim “bring documents supporting the claimed entitlement” is publishable only after review;
- the generic recruitment list is not copied wholesale into every exemption checklist;
- no invented quantities, family-register form numbers, medical certificates, or proof-of-support documents are asserted as universal family-exemption requirements;
- basis-specific documentary sufficiency remains unresolved and is an explicit specialist/source-review item.

This is a deliberate test of the claim model: a Procedure can know the legal ground without pretending the research has established every operational document.

## 9. Procedure steps

| Step ID | Phase | English | State | Evidence |
| --- | --- | --- | --- | --- |
| `mil.step.resolve_recruitment_region` | route | Resolve the competent Recruitment and Mobilization region from current official jurisdiction data | current as retrieved | `EL-TAGNED-REGIONS` |
| `mil.step.present_supporting_evidence` | submit | Present documents supporting the claimed exemption ground to the competent recruitment authority | current operational instruction | `EL-MOD-SUPPORTING-DOCS` |
| `mil.step.authority_reviews_status` | adjudication | The competent specialists/region review the request and determine entitlement/service status | current for certificate-service workflow; scope caveat applies | `EL-TAGNED-CERT-REVIEW` |
| `mil.step.obtain_certificate_if_approved` | output | Obtain an exemption certificate through an available approved route when the authority confirms the service | current service exists; first-time vs subsequent scope must be respected | `EL-TAGNED-CERT-SERVICE` |

The planner does not replace the authority's adjudication step with a local TRUE result.

## 10. Fees

- **Exemption-certificate service:** the official site states that the result inquiry exposes the fees determined for the service and permits electronic payment.
- **Current amount:** `unknown` in this pack.
- No amount is inferred from unofficial articles.

Fee state therefore proves that “official service with a fee mechanism” and “known current amount” are separate claims.

## 11. Service Points and routing

The official Recruitment and Mobilization site currently lists nine regional areas and their governorate coverage. The fixture needs only enough associations to prove jurisdiction routing; it does not become a general nationwide office directory.

Examples:

### `sp.recruitment_giza_haram`

- location context: Haram / Giza recruitment region
- current source coverage includes Giza, Fayoum and the site's 6 October label
- evidence: `EL-TAGNED-REGIONS`

### `sp.recruitment_mansoura_sandoub`

- location context: Sandoub / Mansoura
- current source coverage includes Dakahlia, Damietta and Kafr El Sheikh
- evidence: `EL-TAGNED-REGIONS`

### `sp.recruitment_zagazig_tel_basta`

- location context: Tel Basta / Zagazig
- current source coverage includes Sharqia, Suez, Ismailia, Port Said, North Sinai and South Sinai
- evidence: `EL-TAGNED-REGIONS`

### `sp.tagned_exemption_certificate_online`

- digital destination: official Recruitment and Mobilization exemption-certificate service
- evidence: `EL-TAGNED-CERT-SERVICE`
- scope: supports a certificate request/review workflow, but this pack does not assume the online form alone adjudicates every first-time family-exemption case

### Routing behavior

1. routing is based on current recruitment-region jurisdiction rather than nearest-office distance;
2. the official regional page contains some historical/administrative geographic labels, so the fixture should preserve the source wording and require editorial normalization review instead of silently rewriting it;
3. if a governorate-to-region association is unavailable or questionable, legal Basis research remains usable while routing is locally inconclusive;
4. certificate pickup destination and the competent region for legal-status review are different concepts and must not be conflated.

## 12. Procedure Dependencies

No direct blocking dependency on another Procedure is asserted by this evidence pack.

A missing supporting civil-status or medical document may make the user's application unready, but the research pass does not establish that a specific Bardi Procedure must always be completed first. The planner must not manufacture dependency edges from generic documentary needs.

## 13. Warnings and limits

### `mil.warning.authority_decides`

- severity: `important`
- Arabic: تحديد استحقاق الإعفاء المؤقت قرار للجهة المختصة، والخطة لا تُعد قرار إعفاء.
- English: Temporary-exemption entitlement is determined by the competent authority; the plan is not an exemption decision.
- basis: product/legal-safety limitation; no government Evidence Link required

### `mil.warning.cause_lapse`

- severity: `important`
- Arabic: الإعفاء المؤقت يزول بزوال سببه، ويجب مراجعة منطقة التجنيد المختصة خلال ثلاثين يوماً من زوال السبب وفق النص محل المراجعة.
- English: A temporary exemption ends when its cause ends; the researched statute requires presentation to the competent recruitment region within 30 days after the cause ends.
- evidence: `EL-LAW127-TEMPORARY-LAPSE`
- specialist review: required

### `mil.warning.recheck`

- severity: `important`
- Arabic: أعد التحقق من النص القانوني والمستندات ومكان المعاملة قبل التوجه.
- English: Re-check the current law, documentary requirements and service location before acting.
- basis: product safety requirement; no government Evidence Link required

## 14. Internal discrepancies and temporal issues

### `DISC-MIL-MISSING-BASIS-2026-AMENDMENT`

- status: `resolved_for_current_version`
- old Article 7/Second(e) wording referred to war operations;
- Law No. 2 of 2026 replaced that clause and added terrorist operations;
- enacted law is dated 2026-03-24 and takes effect the next day;
- consequence: current Procedure Version uses the amended ground from 2026-03-25; historical scenarios before that date use the earlier wording.

### `DISC-MIL-CERTIFICATE-SERVICE-SCOPE`

- status: `needs_reverification`
- the official digital service accepts exemption-certificate requests and has specialists review entitlement to the service;
- the research pass does not prove that submitting this online form alone is the complete first-time legal-adjudication workflow for every family Basis;
- consequence: public guidance distinguishes legal-status review at the competent authority from downstream certificate-request mechanics.

### `DISC-MIL-REGION-LABEL-NORMALIZATION`

- status: `open_editorial`
- the current official regions page includes administrative/geographic labels that may reflect legacy naming;
- consequence: preserve official routing evidence, but require human normalization review before freezing stable governorate keys.

These discrepancy records are internal/admin-only.

## 15. Capability findings

This fixture proves or strongly pressures the following capabilities:

1. **additive Eligibility Bases** under one Procedure, with Basis-specific claims kept distinct from shared claims;
2. **specialist-review metadata** for legally consequential claim publication;
3. **authority-recorded Facts** when a rule depends on a legal/medical status that should not be inferred from free text;
4. **temporal legal overlays**, demonstrated by the 2026 Article 7 amendment effective on a precise date;
5. **local inconclusiveness inside a Basis**, where support/kinship semantics remain unresolved without invalidating other researched grounds;
6. **authority adjudication as an explicit step**, rather than treating the planner's rule match as a binding legal outcome;
7. **jurisdiction routing** to recruitment regions without nearest-office ranking;
8. **known service / unknown fee amount** as a legitimate state;
9. **separation of legal-status review from certificate issuance/pickup**.

A generalized legal-reasoning engine is not justified. The fixture instead exposes exactly where deterministic typed rules stop and specialist/authority review begins.

## 16. Publication and review gate

- [x] Broad military-paperwork Goal and temporary-family-exemption Procedure distinguished.
- [x] Article 7 temporary family grounds represented as candidate Eligibility Bases.
- [x] Shared and Basis-specific claims kept separate.
- [x] 2026 Law No. 2 amendment incorporated with effective-date boundary.
- [x] Current Recruitment and Mobilization routing/service sources captured.
- [x] Basis-specific documentary gaps left unresolved rather than copied from generic recruitment lists.
- [x] Current fee amount left unknown.
- [x] Authority adjudication separated from planner evaluation.
- [x] Internal discrepancies kept concise and non-public.
- [x] Named scenarios recorded in `scenarios.md`.
- [ ] **Specialist legal/military-status review of every Article 7 Basis and current consolidated wording.**
- [ ] Specialist review of the exact meaning and evidentiary treatment of “unable to earn,” “sole breadwinner,” and relative eligibility/order terms.
- [ ] Current first-party basis-specific documentary checklist review.
- [ ] Independent review of recruitment-region stable keys/legacy labels.
- [ ] Independent Arabic wording review.
- [ ] Independent English wording and semantic-parity review.
- [ ] Founder/trusted-peer approval after specialist review.

Until those gates are complete, this pack is a design/research fixture and must not be treated as public legal guidance.
