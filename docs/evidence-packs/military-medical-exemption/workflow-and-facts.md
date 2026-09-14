# Administrative workflow and Fact proposals

This is a future production-authoring contract, not implemented behavior. All paths below require
current evidence, coherent version publication and the selection design in I02. The authority
determines medical fitness; Bardi helps the applicant prepare for the evidenced administrative step.

## Stage map

The branch has one proposed parent Procedure identity, specified in [README](README.md).
Stage IDs below are research references, not automatically separate Procedures or fees.

| Stage | Applicant circumstance | Supported direction | Remaining gate |
| --- | --- | --- | --- |
| A01 | No military medical assessment/decision; seeking help presenting their health circumstances | Preparation for the competent authority's assessment, C02-C04; no exemption outcome predicted | G01/G02/G05; not a complete first-application plan yet |
| A02 | Military referral or assessment pending | Follow the evidenced referral/notification process; keep outcome unresolved | G02; do not invent a committee appointment, specialist tests or a waiting period |
| A03 | Military unfitness recorded; exemption/certificate not yet confirmed | Separate medical outcome from completion of exemption paperwork | G02; no assertion that a preliminary outcome equals a final certificate |
| A04 | Exemption expressly granted; certificate not yet issued | First certificate/collection stage after the authority's recorded decision | G02/G04; not assumed covered by C10's replacement service |
| A05 | Prior medical-exemption certificate issued; copy lost or another copy wanted | A distinct certificate transaction supported at historical discovery level by C10 | G03/G04/G05; separate Procedure if confirmed by the transaction research |
| A06 | Certificate damaged | Replacement boundary; loss and damage need their own current source coverage | G03; do not silently relabel damage as loss |
| A07 | Recorded fit/refusal, unclear outcome, or current instruction for another examination | Obtain the applicable authority clarification/review instructions | G07; C02/C14 are not a ready appeal workflow |
| A08 | Unable to travel or needing another person to assist | Investigate the scoped arrangements in C12/C13 and authorized representation | G05; no universal home visit, proxy submission or fee waiver |

For A01/A02, an eventual `plan` may describe a reviewed assessment process; it must not claim
qualification for exemption. If the current production model cannot represent that distinction
without presenting a matched legal Basis, record the exact contract change needed in I02 and keep
the path inconclusive. Do not invent an always-true medical Eligibility Basis to force a plan.

For any authored exemption Basis, use the existing reachability/qualification separation.
Reachability concerns the researched administrative context. Qualification may use a clearly
defined **reported authority record** only after review of its meaning; it must never derive
fitness from symptoms, diagnosis names or measurements. Item/Basis trust still comes from editorial
evidence, independently of the applicant's answer. Keep multiple genuine legal grounds visible;
do not rank family versus medical entitlement.

## Content to author after the relevant gaps close

| Component | Bounded instruction |
| --- | --- |
| Checklist | C03/C11 support providing evidence, not a universal list. Obtain actual form, identity, existing military record and medical-document requirements for the selected stage. Do not copy all intake documents or another exemption's family-registration list. |
| Psychiatric documentary item | C06 stays blocked pending G06. If later supported, preserve its exact narrow condition and alternatives. Neither hospital admission nor Council certification is a blanket prerequisite for all mental-health cases. |
| Preparation | Existing documents may be described as optional preparation only where supported. Do not prescribe obtaining tests, stopping medication or seeking hospitalization to satisfy the planner. |
| Steps | Separate initiation/referral, examination by the authority, any further examination, decision, and certificate issuance. Include only evidenced steps; a source describing one event is not a complete sequence. |
| Fees | Represent missing amounts explicitly. Do not use zero, the old military-card tariff, consular family-exemption fees or an event's waiver as the default medical-exemption price. |
| Routing | Name the competent authority from C02/C04. Exact region and accessibility arrangements require G05; do not map current residence to a region merely because the older family fixture does so. |
| Timing | No appointment dates, assessment duration, certificate-validity period or appeal countdown inferred from this snapshot. G07 must close before deadline derivations. |
| Dependencies | A supporting document is not automatically a prerequisite Procedure. Add only evidenced direct dependencies; do not create a loop requiring the final exemption certificate before assessment. |
| Public wording | Explain what the next administrative step does. Clearly distinguish a reported record from Bardi verification and an assessment plan from an exemption decision. |

## Reuse existing source Facts

Use the registry in `backend/planning/facts.py` without redefining existing keys or enum values.
Questions belong to the existing military Service. A Fact used by another Service does not prove
that the military Service already has Question coverage for it.

| Fact / type | Arabic prompt | English prompt | Use |
| --- | --- | --- | --- |
| `citizenship`: enum `egyptian`, `other` | هل تحمل الجنسية المصرية؟ | Do you hold Egyptian citizenship? | Bounded citizen scope; does not adjudicate disputed/dual nationality |
| `application_location`: enum `inside_egypt`, `outside_egypt` | هل ستتعامل مع موقفك التجنيدي من داخل مصر أم من خارجها؟ | Will you handle your military-service status from inside or outside Egypt? | Reuse the existing military Question |
| `birth_date`: date | ما تاريخ ميلادك؟ | What is your date of birth? | Only if an evidenced age scope needs it; never ask for a derived age |
| `sex`: enum `male`, `female` | ما الجنس المسجل في مستنداتك الرسمية؟ | What sex is recorded in your official documents? | Only if the reviewed scope requires it; discrepancies are a separate boundary |
| `residence_governorate`: string | ما محافظة محل الإقامة المستخدمة في معاملتك التجنيدية؟ | Which governorate of residence is used for your recruitment transaction? | Existing Question; insufficient by itself to establish medical jurisdiction |
| `has_military_status_document`: boolean | هل لديك مستند يوضح موقفك التجنيدي؟ | Do you have a document showing your military-service status? | Generic document presence, not proof of medical exemption; do not change its meaning |

The initial bounded content may choose an adult pre-service scope, but no numeric age limit is
established by this proposal alone. Do not use the passport military-document age threshold or a
family-exemption age rule to determine medical exemption. Birth date/sex remain unasked if they
cannot affect usable researched content in the selected increment.

## Proposed new source Facts

These names, enum values and prompts are proposals requiring I02 review before registration.
Use Question IDs `q.mil.medical.<fact_key>`. Use the bilingual choice-label proposals below after
independent wording review; enum values are machine keys, not public labels. Never accept clinical
free text. Existing shared Questions retain their IDs and wording unless I02 expressly changes them.

| Fact / exact type and values | Arabic prompt | English prompt |
| --- | --- | --- |
| `military_paperwork_subject`: enum `own_health_assessment`, `existing_medical_exemption_document`, `family_circumstances`, `other` | ما موضوع الأوراق التي تريد المساعدة بشأنها: عرض حالتك الصحية على جهة التجنيد، أم مستند إعفاء طبي سبق تقريره، أم ظروف عائلية، أم موضوع آخر؟ | What does the paperwork concern: presenting your health circumstances to the recruitment authority, a document for an existing medical exemption, family circumstances, or something else? |
| `military_service_history`: enum `never_started`, `currently_serving`, `previously_served` | هل بدأت أداء الخدمة العسكرية: لم تبدأ، أم تؤديها حاليًا، أم سبق أن أديتها؟ | Have you started military service: never started, currently serving, or previously served? |
| `military_medical_assessment_record`: enum `no_record`, `referred_or_pending`, `recorded_fit`, `recorded_unfit`, `unclear` | ما النتيجة أو الإحالة التي أبلغتك بها الجهة الطبية العسكرية في هذه المعاملة؟ | What result or referral has the military medical authority communicated for this transaction? |
| `military_medical_exemption_record`: enum `no_decision_communicated`, `granted`, `refused`, `unclear` | هل أبلغتك جهة التجنيد بقرار الإعفاء الطبي في هذه المعاملة، وما القرار المسجل؟ | Has the recruitment authority communicated a medical-exemption decision for this transaction, and what was recorded? |
| `medical_exemption_certificate_ever_issued`: boolean | هل سبق أن صدرت لك شهادة عن الإعفاء النهائي لعدم اللياقة الطبية الذي تتعلق به هذه المعاملة؟ | Has a certificate ever been issued for the final medical-unfitness exemption this transaction concerns? |
| `medical_exemption_certificate_state`: enum `held`, `lost`, `damaged`, `not_issued` | ما حالة شهادة هذا الإعفاء الطبي: معك، أم مفقودة، أم تالفة، أم لم تصدر لك من قبل؟ | Is the certificate for this medical exemption held, lost, damaged, or never issued? |
| `has_current_military_medical_review_instruction`: boolean | هل لديك إخطار أو تعليمات حالية من جهة التجنيد بالحضور لفحص أو مراجعة طبية أخرى؟ | Do you have a current recruitment-authority notice or instruction to attend another medical examination or review? |
| `needs_assistance_to_attend`: boolean | هل تحتاج إلى مساعدة في الحضور بسبب صعوبة الانتقال؟ | Do you need assistance attending because travelling is difficult? |

### Proposed answer labels

Boolean choices are `true`: نعم / Yes and `false`: لا / No. Not knowing is omission, never a
coerced `false`; an explicit `unclear` choice has the separate meaning described below.

| Fact | Value | Arabic label | English label |
| --- | --- | --- | --- |
| `military_paperwork_subject` | `own_health_assessment` | عرض حالتي الصحية على جهة التجنيد | Present my health circumstances to the recruitment authority |
| `military_paperwork_subject` | `existing_medical_exemption_document` | مستند يتعلق بإعفاء طبي سبق تقريره | A document for an existing medical exemption |
| `military_paperwork_subject` | `family_circumstances` | ظروف عائلية | Family circumstances |
| `military_paperwork_subject` | `other` | موضوع آخر | Another subject |
| `military_service_history` | `never_started` | لم أبدأ أداء الخدمة العسكرية | I have never started military service |
| `military_service_history` | `currently_serving` | أؤدي الخدمة العسكرية حاليًا | I am currently serving |
| `military_service_history` | `previously_served` | سبق أن أديت الخدمة العسكرية | I have previously served |
| `military_medical_assessment_record` | `no_record` | لا تتوفر لدي نتيجة أو إحالة طبية عسكرية يمكنني الإبلاغ عنها | No military medical result or referral is available for me to report |
| `military_medical_assessment_record` | `referred_or_pending` | أُبلغت بإحالة أو بأن التقييم لم ينته بعد | A referral or pending assessment was communicated |
| `military_medical_assessment_record` | `recorded_fit` | أُبلغت بنتيجة لائق طبيًا | A medically fit result was communicated |
| `military_medical_assessment_record` | `recorded_unfit` | أُبلغت بنتيجة غير لائق طبيًا | A medically unfit result was communicated |
| `military_medical_assessment_record` | `unclear` | وصلني إخطار لكن معناه غير واضح لي | I received a communication but its meaning is unclear to me |
| `military_medical_exemption_record` | `no_decision_communicated` | لم أُبلغ بقرار بشأن الإعفاء الطبي | No medical-exemption decision has been communicated to me |
| `military_medical_exemption_record` | `granted` | أُبلغت بالموافقة على الإعفاء الطبي | Medical exemption was granted |
| `military_medical_exemption_record` | `refused` | أُبلغت برفض الإعفاء الطبي | Medical exemption was refused |
| `military_medical_exemption_record` | `unclear` | وصلني إخطار لكن معناه غير واضح لي | I received a communication but its meaning is unclear to me |
| `medical_exemption_certificate_state` | `held` | معي شهادة سليمة | I hold an undamaged certificate |
| `medical_exemption_certificate_state` | `lost` | الشهادة مفقودة | The certificate is lost |
| `medical_exemption_certificate_state` | `damaged` | الشهادة تالفة | The certificate is damaged |
| `medical_exemption_certificate_state` | `not_issued` | لم تصدر لي شهادة لهذا الإعفاء من قبل | No certificate has ever been issued to me for this exemption |

### Meaning and consistency

`military_paperwork_subject` records the user's intended subject/output, as a Service entry choice
does. It is not a declaration of fitness, legal entitlement, or the government transaction Bardi
will select. A request for an existing document does not establish that a decision or certificate
exists; the remaining Facts determine the researched next stage. The exact coexistence with the
old selector must be designed before this Fact affects production.

For `military_medical_assessment_record`, `no_record` means no military assessment record/result
is available to report; it does not mean medically fit. Civilian paperwork is not a military record.
`unclear` means a communication exists but its meaning cannot be reported reliably. Distinguish
that from omission: an omitted answer may be asked; `unclear` must not cause an endless loop.
Apply the same rule to the exemption record. No evidence screenshot, certificate number, medical
history, medication list, diagnosis or service number is collected to verify these answers.

Both certificate Facts concern the same applicant and exemption record. `held` means an undamaged
copy is available; use `damaged` if only a damaged copy remains, and `lost` if no copy is available
because it was lost. The boolean is issuance
history; the enum distinguishes a held/lost/damaged certificate from one never issued. `not_issued`
does not mean a replacement is pending: an already-issued lost certificate remains `lost` while
a replacement is awaited. Expressly false issuance history plus `held`, `lost` or `damaged`, or
expressly true history plus `not_issued`, are proposed contradictions. Record this scope before
implementing the invariant; omitted history is never a contradiction. A medical decision with
`not_issued` is coherent when no certificate has yet been issued.
Old/new differing medical results may reflect a later review, so do not declare them impossible
or automatically overwrite an earlier decision.

## Question flow and privacy

After the accepted catalog rollout, resolve subject/location/service-history boundaries first,
then the consequential record/stage Facts. Ask certificate history/state only on an issuance/copy
path, and accessibility only when it changes usable supported instructions. A new review notice
must prevent certificate guidance from silently ignoring a live assessment/review requirement.
Specify priorities in I02; do not renumber historical Questions by convenience.

Unknown eligibility research is not a missing applicant Fact. If only blocked C06 content would
benefit from more personal data, ask nothing about the condition and keep the gap. Respect the
existing `plan`, `next_question`, `inconclusive` and `invalid` API families and local uncertainty.
No new disease classifier, medical outcome prediction, upload flow, application submission,
stored case record, raw-Fact logging or analytics payload is needed.
