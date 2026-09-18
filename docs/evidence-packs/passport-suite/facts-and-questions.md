# Passport source Facts and bilingual Questions

These are future authoring requirements, not API registry changes. Existing definitions in
[backend/planning/facts.py](../../../backend/planning/facts.py) remain authoritative. Preserve
current enum meanings, Service Question IDs and priorities. Prompts here are proposed bilingual
wording, not permission to rewrite preserved evaluation context.

## Reuse existing Facts

| Fact | Type / values | Arabic prompt | English prompt | Consequential use |
| --- | --- | --- | --- | --- |
| `citizenship` | enum: `egyptian`, `other` | هل أنت مواطن مصري؟ | Are you an Egyptian citizen? | Citizen boundary; no parentage-based legal inference |
| `application_location` | enum: `inside_egypt`, `outside_egypt` | هل ستقدم الطلب من داخل مصر أم من خارجها؟ | Will you submit the application from inside or outside Egypt? | Domestic/consular boundary; represented-submission exceptions need separate scope |
| `passport_class` | enum: `ordinary`, `other` | هل يتعلق الطلب بجواز سفر مصري عادي؟ | Is this request for an ordinary Egyptian passport? | Ordinary-class boundary |
| `existing_passport_state` | enum: `expired`, `pages_full`, `valid_with_pages`, `lost`, `damaged`, `none` | ما حالة جواز سفرك المصري الحالي؟ | What is the state of your current Egyptian passport? | Never interpret absence as loss automatically |
| `national_id_status` | enum: `valid_current_data`, `invalid_or_expired`, `not_held` | هل بطاقة الرقم القومي سارية وبياناتها محدثة؟ | Is your National ID valid with current details? | Passport identity aggregate, not every reason for invalidity |
| `birth_date` | date | ما تاريخ ميلادك؟ | What is your date of birth? | Deterministic age derivation |
| `sex` | enum: `male`, `female` | ما النوع المسجل في مستنداتك المصرية؟ | What sex is recorded in your Egyptian documents? | Scoped documentary conditions; contested records separate |
| `is_student` | boolean | هل أنت مقيد بالدراسة حالياً؟ | Are you currently enrolled as a student? | Student documentary condition |
| `service_level` | enum: `standard`, `urgent`, `premium` | هل تطلب الخدمة العادية أم العاجلة أم المميزة؟ | Are you requesting standard, urgent or premium service? | Preference for researched fees/channel, not legal conclusion |
| `residence_police_jurisdiction` | string | ما قسم الشرطة التابع له محل إقامتك؟ | Which police jurisdiction covers your residence? | Passport routing only with a verified map |

## Proposed additional source Facts

All keys below are **unimplemented**. Add only what the next bounded increment needs.
Each row resolves one Fact. Proposed Question IDs use `q.passport_suite.<fact_key>`.
Shared Fact keys retain one compatible registry definition and separately worded Service Questions;
separating the documents does not authorize divergent types or independent migrations for a key.

| Fact | Type / values | Arabic prompt | English prompt | Use |
| --- | --- | --- | --- | --- |
| `passport_ever_issued` | boolean: whether an Egyptian passport has ever been issued | هل سبق أن صدر لك جواز سفر مصري؟ | Has an Egyptian passport ever been issued to you? | P01/P08; avoids redefining existing none |
| `passport_loss_location` | enum: `inside_egypt`, `outside_egypt`; loss location, not application | هل فُقد الجواز داخل مصر أم خارجها؟ | Was the passport lost inside or outside Egypt? | P03/P04/P10 |
| `passport_data_change_kind` | enum: `none`, `name`, `residence`, `profession`, `marital_status`, `other`, `multiple` | هل تحتاج إلى تحديث أي بيانات في جواز السفر، وما نوعها؟ | Do any passport details need updating, and which kind? | P06/P12 and combined cases |
| `passport_record_discrepancy_kind` | enum: `none`, `printed_record_mismatch`, `underlying_record_needs_update`, `contested` | هل يختلف الجواز عن السجل الرسمي، أم يحتاج السجل نفسه إلى تحديث، أم توجد منازعة؟ | Does the passport differ from the official record, does the record itself need updating, or is it disputed? | P06; printing error is not legal record change |
| `military_notation_on_previous_passport` | enum: `not_required`, `other_notation`, `no_notation`; report recorded category, not inferred exemption | هل يحمل جوازك السابق عبارة «غير مطلوب للتجنيد» أم بياناً آخر أم لا يوجد بيان؟ | Does your previous passport say “not required for military service”, show another notation, or have no notation? | C-P-11; omit when previous document cannot be inspected |
| `enrollment_records_military_postponement` | boolean: current enrollment evidence explicitly records postponement | هل تثبت شهادة القيد الدراسي الحالية تأجيل التجنيد؟ | Does the current enrollment certificate explicitly record military postponement? | Male student branch after specialist review |
| `marital_status` | enum: `single`, `married`, `divorced`, `widowed`; stated current status | ما حالتك الاجتماعية الحالية؟ | What is your current marital status? | Conditional documentary branches; no legal adjudication |
| `marital_status_recorded_in_national_id` | boolean: ID records that current status | هل الحالة الاجتماعية الحالية مثبتة في بطاقة الرقم القومي؟ | Does your National ID already record that marital status? | C-P-09; this answer alone cannot resolve D03 |
| `passport_presenting_person_relationship` | enum: `self`, `spouse`, `parent`, `adult_sibling`, `adult_child`, `paternal_grandfather`, `maternal_grandfather`, `paternal_uncle`, `formal_agent`, `other` | ما صلة مقدم الطلب بصاحب جواز السفر؟ | What is the submitter's relationship to the passport holder? | C-P-10; proof/age rules require research |
| `both_parents_abroad` | boolean: both parents physically abroad | هل الأب والأم كلاهما خارج مصر؟ | Are both parents outside Egypt? | Specific grandfather/paternal uncle branch |
| `passport_authorization_scope` | enum: `apply_and_collect`, `apply_only`, `collect_only`, `no_explicit_passport_power`; stated document scope | ما الصلاحيات المذكورة صراحة في التوكيل بشأن الجوازات: التقديم أم الاستلام أم كلاهما؟ | What passport powers are expressly stated in the authorization: applying, collecting, or both? | Formal agent; specialist reviews scope semantics |
| `application_country` | string: intended overseas submission country | في أي دولة ستقدم الطلب؟ | In which country will you submit the application? | Consular scope; not sufficient to identify jurisdiction |
| `consular_residence_region` | string: overseas region/state, without street address | في أي ولاية أو منطقة تقيم بالخارج؟ | In which state or region do you live abroad? | Verified mission jurisdiction after G06 |
| `travel_document_purpose` | enum: `general_travel`, `return_to_egypt_only`; intended output, not route eligibility | هل تحتاج وثيقة للسفر عموماً أم للعودة إلى مصر فقط؟ | Do you need a document for general travel or only to return to Egypt? | P13/P14; purpose alone is not entitlement |

## Passport-specific selection boundaries

Confirm existing none semantics before using passport_ever_issued to distinguish first issuance
from physical absence. When a passport is lost and application is domestic, passport_loss_location
distinguishes P03/P04; do not ask it for an intact renewal or first issue. Passport expiry plus
changes requires a reviewed P02/P06 boundary; until rollout, preserve the implemented P02 baseline
rather than pretending it already checks proposed Facts.

Reuse age_years_on_evaluation_date as a derived Fact, never a submitted age. Existing
has_current_enrollment_certificate, has_military_status_document, has_required_photos and
minor_presenting_adult_role retain their meaning. Lacking a military document is not an offense
finding; parent/other cannot encode all newly researched representatives. Do not extend a
preserved enum or overload other as approved. Military notation/postponement conditions require
specialist review. The separate ID marriage ambiguity is [D03](../national-id-suite/claims.md#d03),
not resolved by a status-recorded answer. ID remediation needs the [ID Facts contract](../national-id-suite/facts-and-questions.md).

## Interview and invariants

Preserve validation and contradiction handling before selection. Omission is UNKNOWN; null,
invalid enums and applicant-supplied derived Facts are errors, not missing answers. Ask only
consequential source Facts using the existing priority/stable-ID order, not a second interview
engine or UI rule scripts. No live candidate is created for a blocked transaction.

For new Questions the proposed editorial bands remain: service boundary 0–19, state/history
20–39, loss/change/output 40–59, version circumstances 60–79, preparation/representation 80–99,
service/routing 100–119. Do not reorder existing Questions just to fit. The shared
[I02 prerequisite](../catalog-compatibility.md) must establish compatible catalog growth first.

Never ask which Procedure applies, whether the person is legally exempt, or what documents an
authority requires. Missing policy, tariffs, accepted proof or jurisdiction is a research gap,
not a source Fact. Supported guidance may coexist with local routing/fee uncertainty; unknown
transaction selection remains inconclusive. No defaulting to a named consulate.

Do not ask a possession/readiness Question for every unconditional checklist item. Collect only
what a supported condition needs, never document numbers, scans, full addresses, flight numbers
or relatives' names merely because a later government form requests them. Alternative proof
remains alternative; independent source Facts need explicit declared mappings.

An explicitly never-issued history plus explicit lost/damaged existing document can become a
contradiction only after old Fact meanings and the new invariant are reviewed. Omitted history
is not contradictory. Expiry plus changes, working while studying, lateness and citizenship with
missing proof are not automatically contradictions; unknown contradictions do not create Questions.
