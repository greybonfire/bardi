# National ID source Facts and bilingual Questions

These are future authoring requirements, not API registry changes. Existing definitions in
[backend/planning/facts.py](../../../backend/planning/facts.py) remain authoritative. Preserve
current enum meanings, Service Question IDs and priorities. Prompts here are proposed bilingual
wording, not permission to rewrite preserved evaluation context.

## Reuse existing Facts

| Fact | Type / values | Arabic prompt | English prompt | Consequential use |
| --- | --- | --- | --- | --- |
| `citizenship` | enum: `egyptian`, `other` | هل أنت مواطن مصري؟ | Are you an Egyptian citizen? | Citizen boundary; no parentage-based legal inference |
| `application_location` | enum: `inside_egypt`, `outside_egypt` | هل ستقدم الطلب من داخل مصر أم من خارجها؟ | Will you submit the application from inside or outside Egypt? | Domestic/consular boundary; represented-submission exceptions need separate scope |
| `national_id_possession_state` | enum: `held`, `lost`, `damaged`, `none` | ما حالة بطاقة الرقم القومي لديك؟ | What is the state of your National ID card? | Renewal versus replacement/first issuance |
| `national_id_data_change_kind` | enum: `none`, `residence`, `profession`, `marital_status`, `other`, `multiple` | هل تغيرت بيانات الإقامة أو المهنة أو الحالة الاجتماعية أو بيانات أخرى؟ | Have residence, profession, marital-status or other recorded details changed? | Preserve multiple; no unchanged-renewal fallback |
| `national_id_expiry_date` | date | ما تاريخ الانتهاء المطبوع على بطاقتك؟ | What expiry date is printed on your card? | Existing expiry derivations; not normally needed for loss |
| `birth_date` | date | ما تاريخ ميلادك؟ | What is your date of birth? | Deterministic age derivation |
| `sex` | enum: `male`, `female` | ما النوع المسجل في مستنداتك المصرية؟ | What sex is recorded in your Egyptian documents? | Scoped documentary conditions; contested records separate |
| `is_student` | boolean | هل أنت مقيد بالدراسة حالياً؟ | Are you currently enrolled as a student? | Student documentary condition |
| `residence_governorate` | string | ما محافظة محل إقامتك؟ | What is your governorate of residence? | Domestic ID routing |
| `residence_district` | string | ما المركز أو القسم التابع له محل إقامتك؟ | Which district or center covers your residence? | Domestic ID routing |

## Proposed additional source Facts

All keys below are **unimplemented**. Add only what the next bounded increment needs.
Each row resolves one Fact. Proposed Question IDs use `q.nid_suite.<fact_key>`.
Shared Fact keys retain one compatible registry definition and separately worded Service Questions;
separating the documents does not authorize divergent types or independent migrations for a key.

| Fact | Type / values | Arabic prompt | English prompt | Use |
| --- | --- | --- | --- | --- |
| `national_id_ever_issued` | boolean: whether an Egyptian National ID has ever been issued | هل سبق أن صدرت لك بطاقة رقم قومي؟ | Has a National ID card ever been issued to you? | N01/N11 |
| `national_id_record_discrepancy_kind` | enum: `none`, `printed_record_mismatch`, `underlying_record_needs_update`, `contested`; ID versus civil register | هل تختلف البطاقة عن القيد المدني، أم يحتاج القيد نفسه إلى تحديث، أم توجد منازعة؟ | Does the card differ from the civil register, does the register need updating, or is it disputed? | N05–N09 |
| `marital_status` | enum: `single`, `married`, `divorced`, `widowed`; stated current status | ما حالتك الاجتماعية الحالية؟ | What is your current marital status? | Conditional ID documentary branches; no legal adjudication |
| `application_country` | string: intended overseas submission country | في أي دولة ستقدم الطلب؟ | In which country will you submit the application? | Consular scope; not sufficient to identify jurisdiction |
| `consular_residence_region` | string: overseas region/state, without street address | في أي ولاية أو منطقة تقيم بالخارج؟ | In which state or region do you live abroad? | Verified mission jurisdiction after G06 |

## National ID-specific selection boundaries

Preserve possession, issuance history, real data changes and expiry as distinct circumstances.
A held card with a single ordinary change belongs to the corresponding researched change family,
regardless of expiry, only after that transaction is confirmed. Loss/damage plus changes and
multiple changes remain combined-case gaps, not silently competing candidates. none alone must
not prove first issuance without confirming its historical meaning.

Reuse age_years_on_evaluation_date, card_expired_before_evaluation_date, renewal_deadline_date
and renewal_deadline_passed with their current implementations. No applicant-supplied derived
values or Question-local arithmetic. Keep nid.no_current_card_with_expiry_date unchanged: none
plus an expiry is not the same as a lost card with a remembered expiry.

First-ID, data-change and loss/damage deadlines are not new production derived Facts in this
research PR. After D09 closes, introduce needed source event dates and reviewed deterministic
calendar derivations in a separate task. Do not copy the passport service_level fee vocabulary
into an ID promise without an evidenced ID tariff/channel. Marital-state answers cannot decide
D03's administrative proof requirement. Passport-only Facts remain in the [passport contract](../passport-suite/facts-and-questions.md).

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
