# Ordinary domestic National ID renewal evidence pack

Issue: #3  
Parent spec: #1  
Research snapshot: 2026-08-26  
Status: research-complete draft; independent human bilingual/source review pending before authoritative prototype use

This pack records the evidence-backed boundary and fixture pressure for routine renewal of an existing Egyptian National ID inside Egypt. It is deliberately a research artifact rather than a production schema. Material administrative assertions are sourced at claim level; presentation-only text is not turned into evidence-bearing claims merely because it may later appear in the product.

## 1. Goal and Procedure identity

- **Goal ID:** `get_egyptian_national_id`
- **Goal (Arabic):** الحصول على بطاقة رقم قومي مصرية
- **Goal (English):** Get an Egyptian National ID
- **Procedure ID:** `ordinary_domestic_national_id_renewal`
- **Procedure (Arabic):** تجديد بطاقة الرقم القومي المنتهية داخل مصر دون تغيير البيانات
- **Procedure (English):** Renew an expired Egyptian National ID inside Egypt without changing its recorded data
- **Authority:** Egyptian Ministry of Interior — Civil Status Sector
- **Administrative output:** a renewed Egyptian National ID card
- **Research version ID:** `ordinary_domestic_national_id_renewal.research-2026-08-26`
- **Evaluation-date assumption:** all current administrative claims are verified as of 2026-08-26 unless an effective interval is known explicitly.

The Goal groups related National ID transactions. Current Public Services Guide material exposes ordinary National ID issuance, lost/damaged replacement, residence-data change, profession-data change, and marital-status change as distinct services. This fixture therefore does not turn every reason for needing a new card into one giant renewal Procedure.

The researched Procedure is intentionally narrow: the person still holds the existing card, the card has expired, the person is applying inside Egypt, and no recorded card/civil-status data needs to change. First issuance, loss/damage, and data-update paths remain related Procedures under the same Goal rather than branches silently absorbed into ordinary renewal.

## 2. Supported boundary

The fixture supports the ordinary path when all of the following are established:

1. The person is applying **inside Egypt**.
2. The person already has and still physically holds the National ID being renewed.
3. The card's recorded expiry date has passed.
4. The person reports no change to card or civil-status data that requires updating as part of the transaction.
5. The case does not involve disputed identity, correction of underlying civil-status records, representation, or another non-routine legal issue.

The Civil Status Law requires the cardholder to apply for renewal within three months from expiry. The same law separately requires updating changed identity/civil-status data within three months of the change and separately governs lost/damaged replacement. Current government service-directory pages likewise expose data-change and lost/damaged services separately. These distinctions are sufficient to treat them as different Procedures for the prototype.

### Recognized unsupported or adjacent cases

- first National ID issuance;
- lost-card replacement;
- damaged-card replacement;
- residence-address change;
- profession change;
- marital-status change;
- another material card-data or civil-record change;
- identity/civil-status correction disputes;
- applications from outside Egypt / consular workflows;
- early renewal before the published expiry date, because this research pass did not establish a current first-party early-renewal window;
- cases whose route depends on an unverified online-service interpretation;
- comprehensive nationwide office routing.

Unsupported by this Procedure does not mean outside `get_egyptian_national_id`; it means another Procedure must be researched and selected.

## 3. Facts

These are fixture-driven candidate Facts, not a frozen production contract.

| Fact key | Type | Example values | Purpose |
| --- | --- | --- | --- |
| `application_location` | enum | `inside_egypt`, `outside_egypt` | domestic vs consular boundary |
| `national_id_possession_state` | enum | `held`, `lost`, `damaged`, `none` | distinguish renewal, replacement, and first issuance |
| `national_id_expiry_date` | calendar date | `2026-01-31` | determine whether this expired-card Procedure applies and derive statutory renewal deadline |
| `national_id_data_change_kind` | enum | `none`, `residence`, `profession`, `marital_status`, `other`, `multiple` | separate plain renewal from update Procedures |
| `residence_governorate` | stable enum/key | `giza` | routing input when a current service association is available |
| `residence_district` | stable enum/key | `dokki` | finer routing input where required |

Omission is generic UNKNOWN. `null` is not a substitute for missing information.

### Derived Facts

- `card_expired_before_evaluation_date`: `evaluation_date > national_id_expiry_date`.
- `renewal_deadline_date`: `national_id_expiry_date + 3 calendar months`, using calendar-month arithmetic rather than a fixed 90-day duration.
- `renewal_deadline_passed`: `evaluation_date > renewal_deadline_date`.
- `has_data_change`: `national_id_data_change_kind != none`.

The same-calendar-day semantics of a card whose printed expiry date equals the evaluation date are not explicitly established by the recovered material. A scenario at that exact boundary should therefore stay outside the authoritative fixture rather than hide a policy assumption.

The calendar-month deadline is a useful capability finding. For example, adding three calendar months to `2026-01-31` yields `2026-04-30` under normal month-end clamping; the planner must not translate the legal wording into “90 days.”

## 4. Questions

Each Question writes one source Fact. Priorities are provisional requirements for the later Missing-Fact Picker.

| Priority | Question ID | Writes | Arabic | English |
| ---: | --- | --- | --- | --- |
| 10 | `q.nid.application_location` | `application_location` | هل ستجري معاملة بطاقة الرقم القومي من داخل مصر أم من خارجها؟ | Will you handle the National ID transaction from inside or outside Egypt? |
| 20 | `q.nid.possession_state` | `national_id_possession_state` | ما حالة بطاقة الرقم القومي الحالية لديك؟ | What is the status of your current National ID card? |
| 30 | `q.nid.data_change_kind` | `national_id_data_change_kind` | هل تحتاج إلى تغيير أي بيانات مسجلة على البطاقة أو في حالتك المدنية؟ | Do you need to change any data recorded on the card or in your civil-status record? |
| 40 | `q.nid.expiry_date` | `national_id_expiry_date` | ما تاريخ انتهاء بطاقة الرقم القومي الحالية؟ | What is the expiry date printed on your current National ID? |
| 50 | `q.nid.residence_governorate` | `residence_governorate` | ما محافظة محل إقامتك؟ | What is your governorate of residence? |
| 60 | `q.nid.residence_district` | `residence_district` | ما المركز أو القسم التابع له محل إقامتك؟ | Which district or centre covers your residence? |

The product need not ask office-routing questions until the core Procedure is known. Question wording itself does not require an Evidence Link because it introduces no new administrative assertion.

## 5. Applicability rules required by this fixture

The Goal has no applicability rule; it supplies candidate Procedures. The ordinary renewal Procedure is described by:

```text
all(
  application_location == inside_egypt,
  national_id_possession_state == held,
  national_id_data_change_kind == none,
  evaluation_date > national_id_expiry_date
)
```

Related Procedure-selection behavior:

```text
if national_id_possession_state == none:
  ordinary renewal = FALSE; first issuance is a related Procedure

if national_id_possession_state in {lost, damaged}:
  ordinary renewal = FALSE; replacement is a related Procedure

if national_id_data_change_kind != none:
  ordinary renewal = FALSE; select the appropriate update Procedure when researched

if application_location == outside_egypt:
  domestic renewal = FALSE; consular workflow is separate
```

An unexpired held card with no data change does not make an early-renewal claim. It only means this **expired-card** fixture does not apply; early-renewal availability remains unverified.

### Operators and derivations proved useful

- typed equality;
- finite-set membership;
- calendar-date ordering;
- boolean composition;
- deterministic calendar-month addition with month-end handling.

The last item is new pressure relative to the passport pack and should be represented as a validated Derived Fact capability rather than an ad-hoc rule script.

## 6. Eligibility Bases

No separate Eligibility Basis is required. The fixture is one routine administrative route, not a set of additive legal qualification grounds.

## 7. Evidence policy and document/checklist findings

Every material administrative assertion below requires evidence. The Goal label, Procedure label, Questions, Derived Fact explanations, and product warnings do not require independent government citations.

The research pass did **not** recover a current domestic first-party documentary checklist detailed enough to publish form/photo/copy quantities for ordinary renewal. That absence is preserved instead of filling the gap from generic articles.

| Claim ID | Classification | Arabic | English | State | Evidence |
| --- | --- | --- | --- | --- | --- |
| `nid.requirement.renew_after_expiry` | Official Requirement | يجب التقدم لتجديد البطاقة خلال ثلاثة أشهر من انتهاء مدة سريانها | Apply to renew within three months from expiry | current as researched | `EL-CIVIL-LAW-52` |
| `nid.requirement.changed_data_update_route` | Official Requirement | تغيير بيانات البطاقة أو الحالة المدنية يستلزم تحديث البيانات في المسار المختص | Changed card/civil-status data requires the update route | current as researched | `EL-CIVIL-LAW-53`, `EL-PSM-DATA-CHANGE-SERVICES` |
| `nid.requirement.previous_card` | Official Requirement candidate | البطاقة الحالية/القديمة | Current/previous card | needs-reverification | `EL-SIS-CONSULAR-PREVIOUS-CARD` |

`nid.requirement.previous_card` is deliberately excluded from authoritative domestic checklist output. Current consular guidance says to provide the old card, but its jurisdiction is overseas; the domestic sources recovered here do not provide a current exact-passage checklist for that item.

No Practical Preparation claim is promoted in this pack because no sufficiently contextual current Field Report is needed to establish the core behavior.

## 8. Procedure steps

| Step ID | Phase | Arabic | English | State | Evidence |
| --- | --- | --- | --- | --- | --- |
| `nid.step.apply_for_renewal` | submit | التقدم بطلب تجديد البطاقة خلال المدة القانونية بعد انتهاء سريانها | Apply for renewal within the legal period after expiry | current as researched | `EL-CIVIL-LAW-52` |
| `nid.step.resolve_service_location` | route | تحديد جهة الخدمة وفق المحافظة والمنطقة أو قناة خدمة حالية موثقة | Resolve the service location from governorate/district or another currently evidenced channel | current at high level; exact office list incomplete | `EL-PSM-NID-SERVICE`, `EL-MOI-MOBILE-2026` |

No exact current first-party claim is made here about the form, photograph count, ordinary turnaround, or collection method.

## 9. Fees and timing

### Fee

- **Current ordinary-renewal amount:** `unknown`.
- The base Civil Status Law delegates card cost-setting to the Interior Minister; an old statutory cap or secondary article is not a current service fee.
- No amount is synthesized from press or commercial service articles.

### Timing

- The legally evidenced renewal deadline is three **calendar months** from expiry.
- Ordinary service completion time is unresolved.
- Mobile/humanitarian service announcements describe availability and completed transactions, not a universal ordinary-card turnaround promise.

## 10. Service Points and routing pressure

The Public Services Guide requires choosing a governorate and area for the National ID service, which proves that geographic context can participate in service discovery. The research pass does not provide a verified nationwide office-to-district table, so the prototype must not invent one.

### `sp.civil_status_sector_abbassia`

- **Identity:** Ministry of Interior — Civil Status Sector
- **Location:** extension of Ramses Street, Abbassia, Cairo
- **Evidence:** `EL-MOI-CIVIL-STATUS-HQ`
- **Use in fixture:** authoritative sector/contact identity only; the pack does **not** assume every ordinary renewal is submitted at sector headquarters.

### Current mobile and humanitarian service channels

A January 2026 Ministry announcement documents Civil Status caravans issuing National IDs in a named set of governorates, home/hospital missions for humanitarian cases, and missions for issuance/renewal at the New Administrative Capital and some clubs. These are current operational channels, but their schedules are transient.

Fixture behavior:

1. stable Authority identity is separate from individual Service Point availability;
2. ordinary service discovery can depend on governorate/district;
3. mobile/humanitarian schedules must be re-verified rather than encoded as evergreen points;
4. if no exact office association is available, routing is locally inconclusive while the legal renewal deadline remains usable;
5. a current overseas guide describes online renewal for applicants abroad with no basic data changes, but this does not by itself establish domestic online applicability.

## 11. Procedure Dependencies

No blocking Procedure Dependency is asserted for the supported no-data-change path.

If a user has changed address, profession, marital status, or other material data, this fixture routes away from ordinary renewal to a related update Procedure. That is Procedure selection, not a fabricated dependency from renewal to every possible update transaction.

## 12. Warnings and public limits

### `nid.warning.deadline`

- severity: `important`
- Arabic: يجب تقديم طلب التجديد خلال ثلاثة أشهر من تاريخ انتهاء مدة سريان البطاقة.
- English: Apply for renewal within three months from the card's expiry date.
- evidence: `EL-CIVIL-LAW-52`

### `nid.warning.changed_data`

- severity: `important`
- Arabic: إذا تغيرت بيانات البطاقة أو الحالة المدنية فقد تحتاج إلى مسار تحديث بيانات مختلف عن التجديد العادي.
- English: If card or civil-status data changed, you may need a data-update Procedure rather than ordinary renewal.
- evidence: `EL-CIVIL-LAW-53`, `EL-PSM-DATA-CHANGE-SERVICES`

### `nid.warning.recheck`

- severity: `important`
- Arabic: أعد التحقق من الخطة قبل التوجه لأن الرسوم ومنافذ الخدمة والتعليمات التشغيلية قد تتغير.
- English: Re-check the plan before acting because fees, service channels and operational instructions can change.
- basis: product safety requirement; no government Evidence Link required

## 13. Internal discrepancies and unresolved claims

Evidence Discrepancies remain internal/admin-only and concise.

### `DISC-NID-ONLINE-DOMESTIC-APPLICABILITY`

- status: `needs_reverification`
- current overseas government guidance describes online renewal where no basic data change is required;
- a Ministry public-services portal exposes National ID services but the retrieved domestic page did not establish the exact ordinary-renewal online boundary;
- consequence: do not promise domestic online renewal until first-party domestic applicability is confirmed.

### Unresolved without a discrepancy record

- current ordinary-renewal fee amount;
- current domestic exact documentary checklist and quantities;
- previous-card requirement for the domestic path;
- ordinary turnaround time;
- comprehensive office routing;
- early-renewal availability before the printed expiry date.

These are knowledge gaps, not source conflicts, so they remain unverified claims rather than being forced into discrepancy records.

## 14. Capability findings

This fixture adds useful pressure to the domain model:

1. one Goal can contain renewal, first issuance, lost/damaged replacement, and multiple data-update Procedures;
2. a three-calendar-month legal deadline requires calendar-month derivation rather than fixed-duration arithmetic;
3. an administrative route can be well-supported even when the current fee and documentary checklist remain unknown;
4. geographic service discovery can be locally inconclusive without suppressing reliable legal deadline guidance;
5. a service/channel claim from an overseas government guide cannot automatically be reused domestically.

No new generalized `Procedure Channel` abstraction is justified yet; current channels can remain Service Point/digital-destination research facts until another fixture proves the abstraction necessary.

## 15. Publication and review gate

- [x] Broad National ID Goal and concrete ordinary-renewal Procedure distinguished.
- [x] Adjacent first-issue, lost/damaged, data-change, and consular routes named rather than merged.
- [x] Current legal renewal deadline and data-change rule captured with claim-level evidence.
- [x] Calendar-month derivation requirement documented.
- [x] Current Civil Status authority and routing pressure documented.
- [x] Current fee left unknown rather than synthesized.
- [x] Unsupported domestic documentary details left unresolved.
- [x] Internal online-applicability discrepancy recorded without public editorial leakage.
- [x] Named scenarios recorded in `scenarios.md`.
- [ ] Independent source-click review of Civil Status Law Articles 52–54 against a current consolidated legal text.
- [ ] Independent Arabic wording review.
- [ ] Independent English wording and semantic-parity review.
- [ ] Current first-party domestic documentary checklist review.
- [ ] Current ordinary-renewal fee verification.
- [ ] Founder/trusted-peer approval before authoritative prototype use.

This is a review-ready research fixture, not public guidance and not a substitute for an authority decision.
