# Procedure-family catalog

The Services remain `get_egyptian_passport` / الحصول على جواز سفر مصري and
`get_egyptian_national_id` / الحصول على بطاقة رقم قومي مصرية.

Catalog row IDs (P01, N01, etc.) are research references. Proposed Procedure IDs are stable
concept names, not yet database records. Rows without a Procedure ID deliberately leave the
transaction model unresolved; do not turn every reason or channel into a separate Procedure.
Use the [claim ledger](claims.md) for exact evidence and the [Facts contract](facts-and-questions.md)
for selection behavior.

`draftable` means there is enough evidence for a bounded draft **with explicit gaps**.
`blocked` means consequential transaction details or selection semantics remain unestablished.
Neither status permits publication. Scope, claim trust, review, and acceptance scenarios must
all pass separately.

## Passport inventory

| Row | Proposed Procedure identity and bilingual label | Case boundary | Evidence / readiness |
| --- | --- | --- | --- |
| P01 | `ordinary_domestic_passport_first_issue` — إصدار جواز سفر عادي لأول مرة داخل مصر / First ordinary passport inside Egypt | Egyptian, domestic, ordinary class, never issued a passport | C-P-01–06, 08–10, 14–16, 18–22; draftable, representation/insurance gaps |
| P02 | **Existing** `ordinary_domestic_passport_renewal` — تجديد جواز سفر منتهٍ أو ممتلئ الصفحات داخل مصر / Replace an expired or page-full ordinary passport inside Egypt | Existing expired/page-full passport; preserve existing research identity | C-P-01–11, 14–16, 18–22; successor research, not an in-place rewrite |
| P03 | `ordinary_domestic_passport_lost_in_egypt` — بدل جواز سفر فُقد داخل مصر / Replace an ordinary passport lost inside Egypt | Apply inside Egypt; loss occurred inside Egypt | C-P-01–06, 08–12, 14–15, 17–20; draftable; G05/G07 for exceptional combinations |
| P04 | `ordinary_domestic_passport_lost_abroad` — بدل جواز سفر فُقد بالخارج بعد العودة لمصر / Replace a passport lost abroad after returning to Egypt | Apply inside Egypt after loss outside Egypt | C-P-01–06, 13–15, 17; draftable named department, G05 blocks missing-evidence alternatives |
| P05 | `ordinary_domestic_passport_damaged` — بدل جواز سفر تالف داخل مصر / Replace a damaged ordinary passport inside Egypt | Apply domestically; passport damaged and available | C-P-01–06, 08–10, 14–15, 17–20; blocked on G04 for complete damage-specific steps |
| P06 | `ordinary_domestic_passport_data_reissue` (candidate only) — إصدار جواز سفر ببيانات محدثة داخل مصر / Reissue a passport with updated data inside Egypt | Existing passport; data differs from authoritative records or needs updating | C-P-01, 14, 21–22; blocked G04/G07; distinguish record correction from transcription into a new passport |
| P07 | No new identity yet — التجديد المبكر لجواز السفر / Early passport renewal | Valid passport with usable pages and no data change | No verified early-renewal window; blocked G04 |
| P08 | `ordinary_consular_passport_first_issue` (mission-scoped versions) — إصدار جواز سفر لأول مرة بالخارج / First ordinary passport through a consulate | Overseas submission; never had a passport; adult/child subcases | C-O-01, 05–06; child draft research; adult checklist/mission conditions blocked G08/G09 |
| P09 | `ordinary_consular_passport_renewal` (mission-scoped versions) — تجديد جواز السفر بالخارج / Renew an ordinary passport through a consulate | Overseas application; existing passport available; renewal reason verified | C-O-02, 04–06; draftable per mission after D04/D05 |
| P10 | `ordinary_consular_passport_lost` (mission-scoped versions) — بدل جواز سفر مفقود بالخارج / Replace a lost passport through a consulate | Applying abroad after loss; nationality/identity established | C-O-03–06; draftable with prior-approval step; incomplete-copy cases G05 |
| P11 | `ordinary_consular_passport_damaged` (mission-scoped versions) — بدل جواز سفر تالف بالخارج / Replace a damaged passport through a consulate | Applying abroad with damaged passport | C-O-03–06; blocked on separating damage from loss-only checklist text |
| P12 | No separate identity until confirmed — تحديث بيانات جواز السفر بالخارج / Update passport data through consular reissuance | Profession/qualification/marital data changes; may coexist with renewal | C-O-02/05; blocked G07/G08; not assumed to be a second fee-bearing transaction |
| P13 | `consular_temporary_return_document` — وثيقة سفر مؤقتة للعودة إلى مصر / Temporary document to return to Egypt | Abroad, temporary return output requested because ordinary travel document unavailable/expired | C-O-10/11; draftable scoped guidance, D06/G06/G08 |
| P14 | `consular_newborn_return_document` — وثيقة سفر مؤقتة لحديث الولادة / Temporary return document for a newborn | Newborn abroad; temporary return output, not a full passport | C-O-12; draftable baseline, specialist/mission exceptions unresolved |

### Passport version contents

For P01–P05, author common documentary claims separately with their own conditions; share
Document Type identities rather than making one global checklist. Student, military, marital,
identity-age, representation, and channel conditions are independent. Merely possessing a
document is usually readiness information, not an eligibility decision.

| Component | What the evidence supports | Boundary still requiring work |
| --- | --- | --- |
| Identity/checklist | C-P-01–09 with individual applicability; S06's replacement context | G05 document alternatives; G08 contested records |
| Preparation/submission steps | C-P-15 and the accepted-submitter framework C-P-10; P03 uses C-P-12; P04 uses C-P-13 | Detailed collection/representative proof and damage-specific handling |
| Military condition | C-P-04 plus the exact C-P-11 exception and student subcase | Treat exemptions, postponement, travel permission and military legal eligibility as different concepts |
| Fees | C-P-16 or C-P-17, plus researched optional service components | G01 complete total; do not promise accelerated loss-case timing before approvals |
| Routing | C-P-20; P04's named domestic department | G06 exact jurisdiction and current named outlet coverage |
| Warnings | Supported administrative limits such as C-P-14; separate product “verify unresolved details” wording | No unverified detention, travel-ban, custody, or penalty advice |
| Dependencies | C-P-01 establishes an ID-document prerequisite for its branch | Target the appropriate researched ID Procedure; do not direct a lost-ID holder to unchanged-data renewal |

P06 must model a **new document** where supported, not editing an issued booklet. It is not yet
known whether a particular changed-data case belongs to P02 or a separate reissuance transaction.
An expired passport plus changed data is coherent input. Do not resolve the catalog uncertainty
by declaring a contradiction or discarding the changed-data fact.

Representative categories are source claims, not a universal permission for another person to
act. For example, possession of a generic power of attorney does not establish the passport
powers in C-P-10. The current `minor_presenting_adult_role` vocabulary cannot encode all categories.
Keep those branches blocked until their narrower Fact definitions and evidence are reviewed.

For P08–P14, each version needs an explicit mission/channel boundary and current local evidence.
MFA general guidance can support common claims but cannot supply a missing London/Dubai/Sydney
price or appointment. A normal consular renewal, an approval request after loss, and an emergency
return document are not interchangeable. Urgency alone must never automatically select P13.

## National ID inventory

| Row | Proposed Procedure identity and bilingual label | Case boundary | Evidence / readiness |
| --- | --- | --- | --- |
| N01 | `ordinary_domestic_national_id_first_issue` — إصدار بطاقة رقم قومي لأول مرة داخل مصر / First National ID inside Egypt | Egyptian; no prior card; age branch reviewed | C-N-01/06; draftable student-channel research; G02/G03 for complete general service |
| N02 | **Existing** `ordinary_domestic_national_id_renewal` — تجديد بطاقة الرقم القومي دون تغيير البيانات داخل مصر / Renew an expired National ID without data changes inside Egypt | Card held, expired, unchanged recorded data | C-N-02/07; successor research; D03/G02 |
| N03 | `ordinary_domestic_national_id_lost` — بدل بطاقة رقم قومي مفقودة داخل مصر / Replace a lost National ID inside Egypt | Previously issued card now lost; no assumed expiry requirement | C-N-04/10; blocked D02/G02/G07 |
| N04 | `ordinary_domestic_national_id_damaged` — بدل بطاقة رقم قومي تالفة داخل مصر / Replace a damaged National ID inside Egypt | Previously issued card damaged and available | C-N-04/08; draftable card requirement, D03/G02 |
| N05 | `ordinary_domestic_national_id_residence_change` — تغيير محل الإقامة ببطاقة الرقم القومي / Change National ID residence data | Address changed, current card held; authoritative-record issue distinguished | C-N-03/09; blocked G02/G03 for accepted address-proof alternatives |
| N06 | `ordinary_domestic_national_id_profession_change` — تغيير المهنة ببطاقة الرقم القومي / Change National ID profession data | Profession/study/qualification update; card held | C-N-03/09; blocked G02/G03; occupation subtypes are not separate Procedures by default |
| N07 | `ordinary_domestic_national_id_marital_status_change` — تغيير الحالة الاجتماعية ببطاقة الرقم القومي / Change National ID marital-status data | Marriage/divorce/widowhood change; card held | C-N-03/09; blocked G02/G03/G08 for record-registration and evidence details |
| N08 | No generic “other” Procedure yet — تصحيح بيانات البطاقة أو القيد المدني / Correct card or civil-register data | Name/birth/religion/sex/nationality or another disputed/incorrect record | Outside routine data-change guidance; blocked G08; do not promise an ordinary counter correction |
| N09 | No identity until transaction model confirmed — تغيير عدة بيانات / Change multiple data fields | More than one real change, or change plus replacement | Coherent case; blocked G07; do not manufacture several charges or mutually exclusive “truths” |
| N10 | No new identity yet — التجديد المبكر لبطاقة الرقم القومي / Early National ID renewal | Card held and not yet expired, no changes | Window not established; blocked G02 |
| N11 | `consular_national_id_first_issue` (committee-scoped candidate) — إصدار أول بطاقة رقم قومي بالخارج / First National ID abroad | First issuance through a confirmed mission/visiting committee | C-N-05, C-O-09; blocked on live committee scope and D04/G09 |
| N12 | `consular_national_id_renewal` (mission-scoped versions) — تجديد بطاقة الرقم القومي بالخارج / Renew National ID through a consulate | Existing card available; overseas application | C-N-05, C-O-07/08/13; draftable scoped material, D07/G06 |
| N13 | No separate identity until confirmed — تحديث بيانات بطاقة الرقم القومي بالخارج / Update National ID data through a consulate | Renewal with residence/profession/marital changes or standalone change | C-O-07/08/13; potentially conditional N12 content; G07/G08 |
| N14 | `consular_national_id_lost` (candidate only) — بدل بطاقة رقم قومي مفقودة بالخارج / Replace a lost National ID abroad | Overseas application; lost card | C-N-05 gives framework only; blocked G09; do not require N12's old original |
| N15 | `consular_national_id_damaged` (candidate only) — بدل بطاقة رقم قومي تالفة بالخارج / Replace a damaged National ID abroad | Overseas application; damaged card | C-N-05 gives framework only; blocked G09 |

### National ID version contents

| Component | What can be authored from this pass | What must remain unresolved |
| --- | --- | --- |
| Selection | Separate issuance, physical loss/damage, unchanged renewal, and genuine data changes using factual circumstances | G07 simultaneous changes and replacements; N08 civil-record correction |
| Checklist | C-N-06–09 only in their channel/transaction scope | Detailed acceptable alternatives, universal photo/copy requirements, D02/D03 |
| Steps | Evidence-supported application/deadline obligations after legal review | Exact domestic purchase/capture/attendance/payment/collection sequence; do not fill this with generic advice |
| Fees | Explicit unknown domestic amounts; separate scoped overseas research values | Current domestic form tiers, same-day price, penalties/exemptions, complete totals |
| Dependencies | Establish an authoritative record before asserting it can be copied to a new card | Whether foreign civil events need prior Egyptian registration in each case; accepted court/registry process |
| Routing | C-N-03's statutory registry framework; scoped service-center/consular leads | Complete governorate-office mapping and current channels |
| Warnings | Deadline/old-card-use rules after current-law review; product uncertainty wording separately | No calculated fine or eligibility denial simply because a deadline passed |

An alternative proof route, once researched, should use the production alternative-content
contract where it genuinely represents an alternative. Do not present every possible proof as
mandatory, and do not create an Eligibility Basis just to implement interview ordering.

## Cross-cutting cases and adjacent outputs

| Case or output | Suite treatment |
| --- | --- |
| Child or newborn ordinary passport | Age/representation branch in the appropriate passport Procedure; temporary return document remains P14 |
| Military documents or travel permission | Passport documentary conditions may be included; deciding exemption, mobilization status or permission to travel is a different researched service |
| Both passport and ID unavailable | Keep the identity-proof/dependency path unresolved under G05; never create a cyclic “obtain each first” plan |
| Student, union profession, public/private employment, pensioner, unemployed | Personalization subcases needing specific proof evidence; consular examples do not prove domestic requirements |
| New nationality, dual nationality, disputed identity, custody orders | Explicit specialist boundary G08; do not infer a legal status from birth, parentage or a court-document name |
| Passport data certificate and movement certificate | Adjacent outputs, not replacement/renewal; PSM discovery and S22 do not provide a complete procedure pack |
| Diplomatic, special, mission/service passport | Non-ordinary class; route outside this citizen suite until a separately researched service exists |
| Palestinian/refugee/stateless travel document | Distinct status/output, explicitly outside ordinary Egyptian-citizen passport selection |
| Recovering a lost card/passport after replacement | Do not assume either document is still usable; C-N-04 covers the ID rule, passport cancellation consequences need their own evidence |
| Accessible, mobile, mall, home/hospital, postal or online service | Channel/Service Point material, not a new Procedure unless the actual administrative transaction differs; G06/G10 govern availability |
| Speed or intended travel date | User circumstance/preference; cannot remove requirements, replace approval, or guarantee completion |

## Per-version handoff checklist

Before any catalog row becomes publishable, it needs a named human author; reviewed bilingual
text; explicit version applicability and editorial effective interval; every material claim
linked to the correct scoped Source; resolved consequential discrepancies; and passing production
Planning Scenarios. General legal review covers statutory interpretation. Military,
custody/guardianship, and contested-identity branches require the corresponding specialists.

A fee or precise routing component may remain explicitly unknown where the production contract
allows a locally inconclusive result. A missing transaction definition, unsupported legal basis,
or unresolved required-document alternative must not be hidden inside a supposedly complete plan.
