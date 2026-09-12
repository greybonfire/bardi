# Source Facts, Questions, and selection boundaries

These are research requirements for future production authoring. They do not extend the current
API registry. `backend/planning/facts.py` remains authoritative for existing keys and value types.
The [implementation handoff](implementation.md) separates vocabulary changes from content imports.

Questions obtain circumstances. They do not ask “which procedure applies?”, “are you legally
exempt?”, or “which documents does the authority require?”. The planner determines the researched
path from Facts. Unknown government policy remains a research gap even if the applicant offers an
opinion about it.

## Reuse existing Facts

Preserve existing enum values and semantics exactly. Existing Service Question IDs and priorities
are also part of the integration review; the wording below is proposed editorial wording, not
authorization to rewrite published evaluation context.

| Existing Fact | Type / values | Arabic prompt | English prompt | Consequential use |
| --- | --- | --- | --- | --- |
| `citizenship` | enum: `egyptian`, `other` | هل أنت مواطن مصري؟ | Are you an Egyptian citizen? | Citizen-suite boundary; no parentage-based legal inference |
| `application_location` | enum: `inside_egypt`, `outside_egypt` | هل ستقدم الطلب من داخل مصر أم من خارجها؟ | Will you submit the application from inside or outside Egypt? | Domestic/consular boundary; physical presence and represented-submission exceptions need separate scope |
| `passport_class` | enum: `ordinary`, `other` | هل يتعلق الطلب بجواز سفر مصري عادي؟ | Is this request for an ordinary Egyptian passport? | Ordinary-class boundary |
| `existing_passport_state` | enum: `expired`, `pages_full`, `valid_with_pages`, `lost`, `damaged`, `none` | ما حالة جواز سفرك المصري الحالي؟ | What is the state of your current Egyptian passport? | Transaction family; never interpret absence as loss automatically |
| `national_id_possession_state` | enum: `held`, `lost`, `damaged`, `none` | ما حالة بطاقة الرقم القومي لديك؟ | What is the state of your National ID card? | Renewal versus replacement/first-issuance investigation |
| `national_id_data_change_kind` | enum: `none`, `residence`, `profession`, `marital_status`, `other`, `multiple` | هل تغيرت بيانات الإقامة أو المهنة أو الحالة الاجتماعية أو بيانات أخرى؟ | Have residence, profession, marital-status or other recorded details changed? | Do not discard `multiple` or silently convert it to unchanged renewal |
| `national_id_expiry_date` | date | ما تاريخ الانتهاء المطبوع على بطاقتك؟ | What expiry date is printed on your card? | Existing expiry-derived Facts; not normally needed to identify loss |
| `national_id_status` | enum: `valid_current_data`, `invalid_or_expired`, `not_held` | هل بطاقة الرقم القومي سارية وبياناتها محدثة؟ | Is your National ID valid with current details? | Passport identity branch; this aggregate enum cannot explain every reason it is invalid |
| `birth_date` | date | ما تاريخ ميلادك؟ | What is your date of birth? | Existing deterministic age derivation |
| `sex` | enum: `male`, `female` | ما النوع المسجل في مستنداتك المصرية؟ | What sex is recorded in your Egyptian documents? | Scoped documentary conditions; contested records require separate handling |
| `is_student` | boolean | هل أنت مقيد بالدراسة حالياً؟ | Are you currently enrolled as a student? | Student documentary condition |
| `service_level` | enum: `standard`, `urgent`, `premium` | هل تطلب الخدمة العادية أم العاجلة أم المميزة؟ | Are you requesting standard, urgent or premium service? | Preference affecting researched fees/channel; not a legal conclusion |
| `residence_police_jurisdiction` | string | ما قسم الشرطة التابع له محل إقامتك؟ | Which police jurisdiction covers your residence? | Existing passport routing, only with a verified map |
| `residence_governorate` | string | ما محافظة محل إقامتك؟ | What is your governorate of residence? | Domestic ID routing |
| `residence_district` | string | ما المركز أو القسم التابع له محل إقامتك؟ | Which district or center covers your residence? | Domestic ID routing |

`has_current_enrollment_certificate`, `has_military_status_document`, `has_required_photos`, and
`minor_presenting_adult_role` also exist. Reuse only their established meaning. In particular,
`has_military_status_document=false` does not establish a military offense, and
`minor_presenting_adult_role=parent` does not distinguish the newly researched representation
cases. Do not overload `other` to mean “approved” or add new values to a preserved enum.

## Proposed additional source Facts

Every proposed key is currently **unimplemented**. Add only those needed by the next bounded
content increment. Each row resolves exactly one source Fact. Proposed Question IDs use
`q.passport_suite.<fact_key>` or `q.nid_suite.<fact_key>` under the corresponding Service; a shared
Fact gets separately worded Service Questions where needed.

| Proposed Fact and type | Allowed values / meaning | Arabic prompt | English prompt | Used by |
| --- | --- | --- | --- | --- |
| `passport_ever_issued`: boolean | Whether an Egyptian passport has ever been issued to this person | هل سبق أن صدر لك جواز سفر مصري؟ | Has an Egyptian passport ever been issued to you? | P01/P08; explicit history avoids redefining the existing `none` state |
| `national_id_ever_issued`: boolean | Whether an Egyptian National ID card has ever been issued | هل سبق أن صدرت لك بطاقة رقم قومي؟ | Has a National ID card ever been issued to you? | N01/N11 |
| `passport_loss_location`: enum | `inside_egypt`, `outside_egypt`; location of loss, not application | هل فُقد الجواز داخل مصر أم خارجها؟ | Was the passport lost inside or outside Egypt? | P03/P04/P10 |
| `passport_data_change_kind`: enum | `none`, `name`, `residence`, `profession`, `marital_status`, `other`, `multiple` | هل تحتاج إلى تحديث أي بيانات في جواز السفر، وما نوعها؟ | Do any passport details need updating, and which kind? | P06/P12 and combined cases |
| `passport_record_discrepancy_kind`: enum | `none`, `printed_record_mismatch`, `underlying_record_needs_update`, `contested` | هل يختلف الجواز عن السجل الرسمي، أم يحتاج السجل نفسه إلى تحديث، أم توجد منازعة؟ | Does the passport differ from the official record, does the record itself need updating, or is it disputed? | P06; do not equate a printing error with a legal record change |
| `national_id_record_discrepancy_kind`: enum | Same four values, referring to ID and civil register | هل تختلف البطاقة عن القيد المدني، أم يحتاج القيد نفسه إلى تحديث، أم توجد منازعة؟ | Does the card differ from the civil register, does the register need updating, or is it disputed? | N05–N09 |
| `military_notation_on_previous_passport`: enum | `not_required`, `other_notation`, `no_notation`; report exact category recorded, not inferred exemption | هل يحمل جوازك السابق عبارة «غير مطلوب للتجنيد» أم بياناً آخر أم لا يوجد بيان؟ | Does your previous passport say “not required for military service”, show another notation, or have no notation? | C-P-11; omitted if the previous document cannot be inspected |
| `enrollment_records_military_postponement`: boolean | Current enrollment evidence explicitly records postponement | هل تثبت شهادة القيد الدراسي الحالية تأجيل التجنيد؟ | Does the current enrollment certificate explicitly record military postponement? | Male student branch after specialist review |
| `marital_status`: enum | `single`, `married`, `divorced`, `widowed`; current stated status | ما حالتك الاجتماعية الحالية؟ | What is your current marital status? | Conditional documentary branches; no automatic legal adjudication |
| `marital_status_recorded_in_national_id`: boolean | ID already records that current status | هل الحالة الاجتماعية الحالية مثبتة في بطاقة الرقم القومي؟ | Does your National ID already record that marital status? | C-P-09; D03 cannot be resolved by this answer alone |
| `passport_presenting_person_relationship`: enum | `self`, `spouse`, `parent`, `adult_sibling`, `adult_child`, `paternal_grandfather`, `maternal_grandfather`, `paternal_uncle`, `formal_agent`, `other` | ما صلة مقدم الطلب بصاحب جواز السفر؟ | What is the submitter's relationship to the passport holder? | C-P-10; further proof/age rules must be researched |
| `both_parents_abroad`: boolean | Both parents are physically abroad | هل الأب والأم كلاهما خارج مصر؟ | Are both parents outside Egypt? | Specific grandfather/paternal uncle representation branch |
| `passport_authorization_scope`: enum | `apply_and_collect`, `apply_only`, `collect_only`, `no_explicit_passport_power`; stated scope in authority document | ما الصلاحيات المذكورة صراحة في التوكيل بشأن الجوازات: التقديم أم الاستلام أم كلاهما؟ | What passport powers are expressly stated in the authorization: applying, collecting, or both? | Formal-agent branch; specialist verifies scope semantics |
| `application_country`: string | Country where an overseas submission is intended | في أي دولة ستقدم الطلب؟ | In which country will you submit the application? | Consular scope; does not by itself identify jurisdiction |
| `consular_residence_region`: string | Region/state of overseas residence, without street address | في أي ولاية أو منطقة تقيم بالخارج؟ | In which state or region do you live abroad? | Mission jurisdiction once G06 is closed |
| `travel_document_purpose`: enum | `general_travel`, `return_to_egypt_only`; intended output/purpose, not route eligibility | هل تحتاج وثيقة للسفر عموماً أم للعودة إلى مصر فقط؟ | Do you need a document for general travel or only to return to Egypt? | P13/P14 investigation; purpose alone does not establish entitlement |

Do not add a Fact for every item on a checklist. If the requirement is unconditional, show it.
Ask possession/readiness only if a supported rule makes the answer consequential. Do not collect
document numbers, photos, scans, full addresses, flight numbers, or relatives' names in the public
planner merely because the government form later asks for them.

## Interview and selection contract

This is a target behavior specification, **not executable selection code**. Do not create live
candidates for blocked catalog rows. New missing-Fact coverage must use the production contract
for selection, version applicability, official checklists, steps and fees.

1. Preserve typed validation and contradiction handling before selection. Omitted values are
   UNKNOWN. `null`, an invalid enum, or a fabricated derived age is not a substitute for UNKNOWN.
2. Resolve only consequential source Facts. Use Service Question priority followed by stable ID;
   do not add a second interview engine, editor formulas, or rule-specific UI visibility scripts.
3. Establish domestic/consular scope and the ordinary citizen service boundary. For passports,
   distinguish physical state and issuance history. For IDs, distinguish possession, history,
   actual changes and expiry. Never make the user select an administrative Procedure name.
4. If passport state is `lost`, loss location distinguishes P03 from P04 when applying domestically.
   Do not ask this for an intact first-issue/renewal case. Missing evidence is different from
   unknown loss location: the former cannot be repaired by guessing a location.
5. `none` alone must not prove first issuance until its historical semantic contract is confirmed.
   The proposed explicit issuance-history Facts make the distinction reviewable. A person who
   once had a document but cannot describe its current state needs clarification, not a first
   issuance rule inferred from physical absence.
6. For National ID selection, a single ordinary change with a held card belongs to the corresponding
   researched change family, regardless of whether the card is also expired. The exact authority
   transaction must be verified before activation. Loss/damage plus changes and `multiple` remain
   combined-case gaps; do not guess precedence or silently match two candidates.
7. Passport expiry plus a data change likewise needs an explicit reviewed boundary between P02
   and P06. Preserve the currently implemented P02 behavior until a reviewed successor rollout
   replaces it. The suite's stricter target is not a claim that current code already checks it.
8. A missing scope Fact can trigger a Question; a missing law, accepted proof alternative, fee
   tariff, or office rule cannot. Supported checklist material can remain available with local
   routing/fee uncertainty where permitted; unresolved transaction selection is inconclusive.

### Proposed Question priority bands

For **new** Questions, use reviewed priorities in these bands: service boundary 0–19; document
state/history 20–39; loss/change/output distinctions 40–59; version-specific personal circumstances
60–79; preparation/representation 80–99; optional service/routing 100–119. These are editorial
defaults, not authority rules. Do not reorder existing Questions merely to fit them. I02 must
demonstrate coexistence and deterministic results before integrating either Service.

## Derived Facts and invariants

- Reuse `age_years_on_evaluation_date`, `card_expired_before_evaluation_date`,
  `renewal_deadline_date`, and `renewal_deadline_passed` with their existing implementations.
  Do not accept them as applicant-supplied Facts or recompute them in Question code.
- Additional statutory dates (first-ID deadline, data-change deadline, loss/damage deadline)
  are **not defined by this pack as new production derived Facts**. After D09 closes, add the
  necessary source event dates and deterministic calendar derivations in a separate task.
- Keep the current `nid.no_current_card_with_expiry_date` contradiction intact. A lost card with a
  remembered expiry is not the same input as `none` plus an expiry; do not broaden that invariant.
- Proposed future contradiction: explicitly “never issued” plus explicitly “lost/damaged existing
  document.” First inspect the old Fact meanings; only genuinely incoherent submitted circumstances
  should trigger it. UNKNOWN contradiction conditions must not generate Questions.
- Expiry plus changes, working while studying, a late application, and citizenship plus missing
  proof are not automatically contradictions. A policy boundary or research limitation is not an
  invalid user case.
- Alternative documentary evidence must remain alternatives. A single question should not claim
  to resolve several independent source Facts without a deterministic declared mapping.
