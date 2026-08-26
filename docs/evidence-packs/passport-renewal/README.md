# Ordinary domestic passport renewal evidence pack

Issue: #2  
Parent spec: #1  
Research snapshot: 2026-08-25  
Status: research-complete draft; independent human bilingual review pending before this can be treated as authoritative fixture data

This pack records the evidence-backed boundary and fixture requirements for ordinary Egyptian passport renewal inside Egypt. It is deliberately human-reviewable rather than a production schema. Later prototype tickets may encode only the claims marked `current` and only after the review gates below are completed.

## 1. Goal and Procedure identity

- **Goal ID:** `get_egyptian_passport`
- **Goal (Arabic):** الحصول على جواز سفر مصري
- **Goal (English):** Get an Egyptian passport
- **Procedure ID:** `ordinary_domestic_passport_renewal`
- **Procedure (Arabic):** استخراج جواز سفر عادي بدل جواز سفر منتهي أو ممتلئ الصفحات داخل مصر
- **Procedure (English):** Obtain an ordinary passport in place of an expired or page-full passport inside Egypt
- **Authority:** Egyptian Ministry of Interior — General Administration of Passports, Immigration and Nationality
- **Administrative output:** a new machine-readable personal passport
- **Research version ID:** `ordinary_domestic_passport_renewal.research-2026-08-25`
- **Evaluation-date assumption:** claims below describe what the cited sources published when retrieved on 2026-08-25. Where the legal or administrative effective-from date could not be established, it is explicitly `unknown` rather than inferred.

The **Goal** is an organizational/user-entry grouping, not an executable government transaction. `get_egyptian_passport` can contain closely related Procedures such as first issuance, ordinary renewal, lost-passport replacement, damaged-passport replacement, and later researched passport Procedures. The person starts from the Goal because they should not need to know which government transaction applies to them.

The **Procedure** is the concrete administrative path selected from that Goal. This pack researches only `ordinary_domestic_passport_renewal`: the current Public Services Guide exposes replacement of an expired or page-full passport as a distinct service, while first issuance and lost/damaged replacement are different Procedures. The Goal itself owns no passport-renewal requirements, fees, steps, routing rules, or evidence; those belong to the applicable Procedure Version.

## 2. Supported boundary

The evidence pack is intended to support this Procedure only when all of the following are true:

1. The person is an Egyptian citizen applying **inside Egypt**.
2. The target is an ordinary personal passport, not a diplomatic, special, service, temporary, or other non-ordinary travel document.
3. The existing passport is expired or its pages are full.
4. The case does not involve a lost or damaged passport.
5. There is no contested identity, custody, guardianship, nationality, or other legal-status dispute.
6. The case can satisfy the applicable identity-document branch described below.
7. Any male military-status requirement that applies can be evidenced by the person’s stated circumstances and an authority-issued military document.
8. The requested Service Point can either be resolved from a current official jurisdiction rule or is allowed to remain locally inconclusive without invalidating otherwise supported requirements.

### Adult and minor branches

The current Ministry of Interior requirements page uses **age 15** as the identity-document boundary:

- age 15 or older: valid National ID, with recorded data updated if changed;
- under 15: machine-readable birth certificate carrying the national number.

This current age boundary supersedes older government guidance that used age 16 for the same distinction. The older material is retained in `sources.md` as stale historical context and must not control current evaluation.

### Recognized unsupported cases

The following cases must be named and escalated rather than forced through this Procedure:

- first passport issuance;
- lost-passport replacement;
- damaged-passport replacement;
- applicants outside Egypt / consular renewal;
- non-ordinary passport classes;
- disputed or uncertain Egyptian nationality;
- contested identity data;
- custody, guardianship, or representation disputes;
- a minor case where authority to submit cannot be established from a current domestic source;
- any case that depends on an unverified or stale consequential claim;
- any request for a passport-data change whose administrative route cannot be distinguished confidently from ordinary renewal;
- any special military-status case requiring legal interpretation rather than a straightforward authority-recorded status.

These cases may still belong to the same broad passport Goal. “Unsupported by this Procedure fixture” therefore does not mean “outside the Goal”; it means the planner must select or research a different Procedure rather than stretching renewal to cover it.

## 3. Facts

These are research-proven candidate Fact keys for later prototype encoding. They are not yet a frozen production contract.

| Fact key | Type | Example values | Why it is needed |
| --- | --- | --- | --- |
| `citizenship` | enum | `egyptian` | procedure boundary |
| `application_location` | enum | `inside_egypt`, `outside_egypt` | domestic vs consular procedure selection |
| `existing_passport_state` | enum | `expired`, `pages_full`, `valid_with_pages`, `lost`, `damaged`, `none` | distinguish related Passport Procedures within the Goal |
| `passport_class` | enum | `ordinary`, `other` | exclude non-ordinary passport Procedures from this fixture |
| `birth_date` | calendar date | `2000-05-20` | derive age; evaluate the military-document rule |
| `sex` | enum | `male`, `female` | military-document applicability |
| `national_id_status` | enum | `valid_current_data`, `invalid_or_expired`, `not_held` | adult identity-document requirement |
| `is_student` | boolean | `true`, `false` | current-year enrollment certificate requirement |
| `has_current_enrollment_certificate` | boolean | `true`, `false` | checklist readiness; do not infer possession from student status |
| `has_military_status_document` | boolean | `true`, `false` | checklist readiness when the military rule applies |
| `has_required_photos` | boolean | `true`, `false` | checklist readiness |
| `service_level` | enum | `standard`, `urgent`, `premium` | service-point and fee routing |
| `residence_police_jurisdiction` | enum/string-key | curated police-district key | standard/urgent geographical routing |
| `minor_presenting_adult_role` | enum | `parent`, `legal_guardian`, `other`, `unknown` | captures the unresolved minor-submission branch without assuming legal authority |

### Derived Facts

- `age_years_on_evaluation_date`: completed years derived from `birth_date` and the explicit evaluation date.
- `is_under_15`: `age_years_on_evaluation_date < 15`.
- `is_15_or_older`: `age_years_on_evaluation_date >= 15`.
- `military_document_required`: male, born on/after 1941-03-18, and age 19 or older, subject to the exact source wording and later fixture validation.

The date derivation is calendar-date based and must not use time zones or an implicit system clock.

## 4. Questions

Each Question writes exactly one source Fact. Priority numbers are provisional fixture requirements for the later Missing-Fact Picker.

| Priority | Question ID | Writes | Arabic | English |
| ---: | --- | --- | --- | --- |
| 10 | `q.application_location` | `application_location` | هل ستقدّم طلب الجواز من داخل مصر أم من خارجها؟ | Will you apply for the passport from inside or outside Egypt? |
| 20 | `q.existing_passport_state` | `existing_passport_state` | ما حالة جواز سفرك الحالي؟ | What is the status of your current passport? |
| 30 | `q.passport_class` | `passport_class` | هل جواز السفر المطلوب جواز عادي أم من فئة أخرى؟ | Is the passport you need an ordinary passport or another class? |
| 40 | `q.birth_date` | `birth_date` | ما تاريخ ميلادك؟ | What is your date of birth? |
| 50 | `q.sex` | `sex` | ما الجنس المثبت في مستنداتك الرسمية؟ | What sex is recorded on your official documents? |
| 60 | `q.national_id_status` | `national_id_status` | هل بطاقة الرقم القومي سارية وبياناتها الحالية صحيحة؟ | Is your National ID valid and are its recorded details current? |
| 70 | `q.is_student` | `is_student` | هل أنت طالب أو طالبة في العام الدراسي الحالي؟ | Are you a student in the current academic year? |
| 80 | `q.service_level` | `service_level` | هل تريد الخدمة العادية أم العاجلة أم المميزة في نفس اليوم؟ | Do you want standard, next-working-day urgent, or same-day premium service? |
| 90 | `q.residence_police_jurisdiction` | `residence_police_jurisdiction` | ما قسم أو مركز الشرطة التابع له محل إقامتك؟ | Which police district or centre covers your residence? |
| 100 | `q.minor_presenting_adult_role` | `minor_presenting_adult_role` | من الشخص البالغ الذي سيقدّم طلب القاصر؟ | Which adult will submit the minor’s application? |

Questions about whether the person physically possesses each required document are optional readiness questions, not procedure-selection questions. They should not be asked until the applicable requirement is known. Question wording itself is product content and does not require a separate government Evidence Link unless it introduces a new administrative assertion.

## 5. Applicability rules required by this fixture

The Goal does not have an applicability rule. It supplies the curated set of related Procedures. Rules determine which Procedure and Procedure claims apply for the supplied Facts.

The notation below is descriptive pseudocode. It records fixture pressure on the rules contract without freezing JSON shape.

### Procedure boundary

```text
all(
  citizenship == egyptian,
  application_location == inside_egypt,
  passport_class == ordinary,
  existing_passport_state in {expired, pages_full}
)
```

### Identity document

```text
if age_years_on_evaluation_date >= 15:
  require National ID with current valid data
else:
  require machine-readable birth certificate
```

### Student certificate

```text
if is_student == true:
  require current-academic-year enrollment certificate
```

### Military-status document

```text
if sex == male
and birth_date >= 1941-03-18
and age_years_on_evaluation_date >= 19:
  require military-status document
```

### Service routing

```text
if service_level == standard:
  route by current territorial jurisdiction

if service_level == urgent:
  ordinary passport sections remain jurisdiction-bound;
  officially identified mall delegations/mobile units may be non-jurisdictional

if service_level == premium:
  return all currently evidenced premium-capable points;
  territorial jurisdiction is not required for the service categories named by the Ministry
```

### Operators this fixture actually proves useful

- typed equality;
- date and integer ordering;
- membership in a finite enum set;
- boolean `all` / `any` / `not` composition;
- `exists` may be useful only for submitted-key presence and is not a substitute for `has_*` domain Facts.

No rule references, scripts, fuzzy matching, substring matching, or procedure-specific evaluator code are justified by this evidence pack.

## 6. Eligibility Bases

No separate **Eligibility Basis** is required by the ordinary passport-renewal fixture. Egyptian citizenship and the renewal boundary are Procedure eligibility conditions, not additive alternative legal grounds. This is an explicit capability finding: the domain model must allow a Procedure to have zero Eligibility Bases.

### Evidence policy for this pack

Evidence is attached to the semantic administrative claim, not to every rendered sentence.

Claims in this pack require Evidence Links when they materially assert an external administrative fact: Procedure-selection/eligibility conditions, required documents and quantities, fees, validity or turnaround, material procedural steps, dependencies, routing/jurisdiction, or Field Guidance. A current Official Requirement therefore cannot be published without adequate current official evidence.

The following do **not** need independent government evidence merely because they appear in the product: Goal/Procedure labels, Question wording, Derived Fact calculations, deterministic explanations such as “because you are under 15,” UI grouping, summaries that introduce no new administrative fact, and product warnings such as “re-check before acting.” Those may inherit the provenance of the evidence-bearing claims they present.

Storage and display are deliberately separate. The fixture records granular Sources and Evidence Links for auditability, but a future public plan may group sources, show compact verification metadata, or reveal claim-level evidence on demand instead of printing a citation beside every item. Internal Evidence Discrepancy records are never public-plan content.

## 7. Document Types and checklist claims

The stable Document Type identifies the item only. Quantities, applicability, classification, and evidence-bearing administrative assertions belong to the Procedure Version claim. Every Official Requirement in the table below is evidence-bearing because each one tells the user what the authority requires.

| Claim ID | Classification | Applicability | Arabic | English | State | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `passport.requirement.national_id` | Official Requirement | age >= 15 | بطاقة رقم قومي سارية وبياناتها الحالية محدثة | Valid National ID with current recorded data | current | `EL-MOI-REQ-01` |
| `passport.requirement.birth_certificate` | Official Requirement | age < 15 | شهادة ميلاد مميكنة تحمل الرقم القومي | Machine-readable birth certificate carrying the national number | current | `EL-MOI-REQ-02` |
| `passport.requirement.student_enrollment` | Official Requirement | student | شهادة قيد دراسي عن العام الدراسي الحالي | Enrollment certificate for the current academic year | current | `EL-MOI-REQ-03` |
| `passport.requirement.military_status` | Official Requirement | applicable male branch | مستند يثبت الموقف من التجنيد | Military-status document | current | `EL-MOI-REQ-04` |
| `passport.requirement.photos` | Official Requirement | all supported cases | 3 صور شخصية ملونة حديثة بخلفية بيضاء مقاس 4×6 | Three recent colour 4×6 photos with a white background | current | `EL-MOI-REQ-05` |
| `passport.requirement.originals_and_copy` | Official Requirement | submitted supporting documents | أصول المستندات وصورة منها للمطابقة | Originals plus a copy for verification | current | `EL-MOI-REQ-06` |
| `passport.requirement.previous_passport` | Official Requirement candidate | expired/page-full renewal | جواز السفر السابق المنتهي أو ممتلئ الصفحات | Previous expired or page-full passport | needs-reverification | `EL-PSM-SERVICE-01`, `EL-HIST-OLDPASS-01`, `EL-MFA-CONSULAR-01` |

`passport.requirement.previous_passport` is deliberately **not** current guidance yet. Current domestic official pages clearly identify the service as replacement of an expired/page-full passport, but the research pass did not recover a current domestic exact passage explicitly saying to bring the previous passport. Historical domestic government guidance and current consular guidance both do, but they have insufficient present domestic applicability on their own.

No Practical Preparation claim is currently publishable. One 2026 web account was found, but it does not identify a precise Service Point and conflicts with the current official fee; it is retained only as a research lead in `sources.md`.

## 8. Procedure steps

Material steps that assert how the authority's process works are evidence-bearing. Presentation-level connective instructions derived from already supported steps do not require a new Evidence Link.

| Step ID | Phase | Slot | Arabic | English | State | Evidence |
| --- | --- | ---: | --- | --- | --- | --- |
| `passport.step.obtain_form_29` | prepare-at-office | 10 | الحصول على نموذج 29 جوازات مميكن مجانًا | Obtain machine-readable Passport Form 29 free of charge | current | `EL-MOI-PROCESS-01` |
| `passport.step.complete_form` | prepare-at-office | 20 | استيفاء بيانات الصفحة الأولى من النموذج بمعرفة صاحب الشأن | Complete the first page of the form with the applicant’s information | current | `EL-MOI-PROCESS-02` |
| `passport.step.submit_and_pay` | submit | 30 | تقديم الطلب والمستندات وسداد الرسم في نقطة الخدمة المختصة | Submit the application/documents and pay the applicable fee at the resolved Service Point | current at high level | `EL-MOI-ROUTING-01`, `EL-MOI-FEE-01` |
| `passport.step.collect` | collect | 40 | استلام الجواز وفق مستوى الخدمة المختار | Collect the passport according to the selected service level | current for urgent/premium timing; standard timing unresolved | `EL-MOI-URGENT-01`, `EL-MOI-PREMIUM-01` |

The ordinary-service completion time is left unknown because current first-party material recovered in this pass did not publish a standard turnaround time. Older government sources and recent press reports disagree, so the pack must not invent one.

## 9. Fees

| Fee ID | Type | Amount | Currency | Applicability | State | Evidence |
| --- | --- | ---: | --- | --- | --- | --- |
| `passport.fee.base` | government fee | 705 | EGP | ordinary machine-readable passport issuance/replacement | current as retrieved | `EL-MOI-FEE-01` |
| `passport.fee.urgent_service` | optional service fee | 100 | EGP | next-working-day urgent service | current as retrieved | `EL-MOI-URGENT-01` |
| `passport.fee.premium_service` | optional service fee | 500 | EGP | same-day premium service | current as retrieved | `EL-MOI-PREMIUM-01` |

The source does not expose the effective-from date for these values in the retrieved text. Their temporal applicability therefore begins as `effective_from: unknown`, `verified_on: 2026-08-25`, with a short re-verification interval recommended for the later publication workflow.

## 10. Service Points and routing pressure

Issue #1 explicitly excludes a comprehensive Service Point directory. This pack therefore captures enough current first-party evidence to prove the routing model without pretending to enumerate Egypt.

### `sp.gapin_headquarters_abbassia`

- identity: General Administration of Passports, Immigration and Nationality headquarters
- location: Abbassia, Cairo; the Ministry police-directory page gives the administration at El-Sikka El-Bayda Street, Abbassia
- evidence: `EL-MOI-HQ-01`
- routing: current Ministry passport material names the General Administration headquarters as a premium-service location; ordinary jurisdiction details for every resident are not inferred from headquarters identity alone

### `sp.giza_passport_office`

- identity: Giza Passport Office
- location: Giza Police Department building, Bahr El-Azam Street
- current listed jurisdiction includes Giza, Boulak El-Dakrour, Haram, Talbia, Abu El-Nomros, Omrania and the listed Giza/Kerdasa police centres
- evidence: `EL-MOI-GIZA-01`

### `sp.dandy_mall_passport_delegation`

- identity: Dandy Mall passport delegation
- location: Dandy Mall, 6th of October City
- current branch index lists the delegation; the Ministry’s premium/urgent descriptions state that mall delegations can provide the named accelerated services without territorial-jurisdiction restriction
- evidence: `EL-MOI-DANDY-01`, `EL-MOI-URGENT-01`, `EL-MOI-PREMIUM-01`

### Routing behavior proved by the fixture

1. Service Point identity and physical location are separate from a Procedure-Version association.
2. Ordinary routing can depend on `residence_police_jurisdiction`.
3. The same Service Point can have a different routing rule for an accelerated service.
4. More than one point may be valid; later planning must return all matches rather than recommend a “best” office.
5. If the user’s district is outside the small set encoded by the prototype fixture, routing becomes locally inconclusive while supported requirements remain available.
6. Mobile-unit schedules are not stable Service Point facts in this pack and must be re-verified at evaluation/publication time rather than encoded as evergreen availability.

## 11. Procedure Dependencies

No direct blocking Procedure Dependency is asserted by this evidence pack.

A valid/up-to-date National ID is a current adult requirement, but the source does not establish that one specific National ID Procedure must always be completed immediately before passport renewal. The later planner may explain that the adult identity requirement is unsatisfied and provide an official Civil Status verification path; it must not manufacture a dependency edge merely because a document is missing or expired.

## 12. Warnings and public limits

The first two warnings below contain external administrative facts and therefore carry evidence. The last two are product safety/limitation messages and deliberately do not need government Evidence Links.

### `passport.warning.personal_document`

- severity: `info`
- Arabic: جواز السفر المقروء آليًا شخصي ولا تُضاف إليه الزوجة أو الأبناء.
- English: The machine-readable passport is personal; a spouse or children are not added to it.
- evidence: `EL-MOI-PASSPORT-NATURE-01`

### `passport.warning.validity`

- severity: `info`
- Arabic: مدة الصلاحية القياسية المنشورة حاليًا سبع سنوات.
- English: The currently published standard validity is seven years.
- evidence: `EL-MOI-VALIDITY-01`

### `passport.warning.regenerate`

- severity: `important`
- Arabic: أعد التحقق من الخطة قبل التوجه مباشرة لأن الرسوم ونقاط الخدمة والتعليمات قد تتغير.
- English: Re-check the plan immediately before acting because fees, Service Points and instructions can change.
- basis: project safety requirement from #1; not a government claim and no government Evidence Link required

### `passport.warning.guidance_not_decision`

- severity: `important`
- Arabic: هذه إرشادات مبنية على مصادر منشورة وليست قرارًا ملزمًا من الجهة الحكومية.
- English: This is source-backed guidance, not a binding decision by the government authority.
- basis: project safety requirement from #1; not a government claim and no government Evidence Link required

## 13. Evidence discrepancies and unresolved claims

Evidence Discrepancies are lightweight **internal/admin-only** research records. They preserve which evidence conflicted or had the wrong applicability, a concise adjudication/status, and any eventual resolution. They are not rendered verbatim in a Personalized Plan and are not intended to become a generalized evidence graph. Public output reflects only their effect: for example a claim may be current, need re-verification, or become locally inconclusive with a simple user-appropriate explanation.

Detailed Source, Evidence Link, and internal discrepancy records are in `sources.md`. The consequential findings are:

1. **Age boundary:** current Ministry of Interior material uses 15; older government pages used 16. Current Ministry material controls this research snapshot; old material is stale context only.
2. **Fee:** current Ministry material publishes 705 EGP. Older government pages contain materially lower historic fees and a 2026 field-style web account reports a materially higher amount. The field account lacks sufficient Service Point context and therefore cannot override or qualify the official current amount as Field Guidance.
3. **Previous passport:** historically documented for renewal and present in current consular guidance, but the current domestic exact-passage requirement was not recovered. It remains `needs-reverification` and excluded from authoritative current checklist output.
4. **Minor submission authority:** current consular guidance requires a parent/legal guardian, and stale domestic material allowed parents to act for minors, but this research pass did not recover equivalent current domestic language. Standard minor identity requirements are supported; submission-authority behavior remains inconclusive pending domestic confirmation.
5. **Standard turnaround time:** current first-party pages recovered here do not state one. Older government and recent press/field sources differ; current value stays unknown.

## 14. Publication and review gate

This evidence pack is not public guidance and must not be promoted automatically into a published Procedure Version.

- [x] Broad passport Goal and distinct researched Procedure identity recorded.
- [x] Ordinary domestic Procedure boundary and recognized unsupported related Procedures/cases recorded.
- [x] Adult/minor identity branches researched against current Ministry material.
- [x] Candidate Facts and Derived Facts recorded.
- [x] Bilingual one-Fact Questions recorded.
- [x] Fixture-proven operator needs recorded.
- [x] Evidence-bearing claim IDs, classifications and Evidence Links recorded.
- [x] Current fees and accelerated-service behavior recorded.
- [x] Procedure-specific Service Point routing concepts pressure-tested with current Ministry records.
- [x] Stale/conflicting evidence preserved in lightweight internal discrepancy records rather than silently normalized.
- [x] Storage/persistence granularity kept separate from future public source presentation.
- [x] No low-context Field Report promoted to Field Guidance.
- [x] Named scenarios recorded in `scenarios.md`.
- [ ] Independent human review of Arabic wording.
- [ ] Independent human review of English wording and semantic parity.
- [ ] Independent source-click review confirming the current domestic previous-passport requirement or retaining it as unresolved.
- [ ] Independent source-click review confirming the current domestic minor-submission/guardian rule or retaining it as unresolved.
- [ ] Founder/trusted-peer approval before later tickets mark this pack authoritative prototype input.

No specialist legal review is required for the ordinary claims currently marked `current`. If a later revision attempts to publish contested identity, custody/guardianship, nationality, or non-routine military-status conclusions, specialist review becomes mandatory under #1.
