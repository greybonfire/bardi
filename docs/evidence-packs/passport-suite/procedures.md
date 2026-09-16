# Passport procedure-family catalog

Catalog row IDs are research references. Proposed Procedure IDs are not live records.
Rows without an identity leave transaction modeling unresolved; do not make every reason or
channel a separate Procedure. Use [claims](claims.md) and [Facts](facts-and-questions.md).
`draftable` means a bounded draft with explicit gaps is possible; `blocked` means consequential
details/selection remain unestablished. Neither status permits publication.

Service: `get_egyptian_passport` / الحصول على جواز سفر مصري.

| Row | Proposed identity and bilingual label | Case boundary | Evidence / readiness |
| --- | --- | --- | --- |
| P01 | `ordinary_domestic_passport_first_issue` — إصدار جواز سفر عادي لأول مرة داخل مصر / First ordinary passport inside Egypt | Egyptian, domestic, ordinary class, never issued a passport | C-P-01–06, 08–10, 14–16, 18–22; draftable, representation/insurance gaps |
| P02 | **Existing** `ordinary_domestic_passport_renewal` — تجديد جواز سفر منتهٍ أو ممتلئ الصفحات داخل مصر / Replace an expired or page-full ordinary passport inside Egypt | Existing expired/page-full passport; preserve existing research identity | C-P-01–11, 14–16, 18–22; successor research, not an in-place rewrite |
| P03 | `ordinary_domestic_passport_lost_in_egypt` — بدل جواز سفر فُقد داخل مصر / Replace an ordinary passport lost inside Egypt | Apply inside Egypt; loss occurred inside Egypt | C-P-01–06, 08–12, 14–15, 17–20; draftable; G05/G07 for exceptional combinations |
| P04 | `ordinary_domestic_passport_lost_abroad` — بدل جواز سفر فُقد بالخارج بعد العودة لمصر / Replace a passport lost abroad after returning to Egypt | Apply inside Egypt after loss outside Egypt | C-P-01–06, 13–15, 17; draftable named department, G05 blocks missing-evidence alternatives |
| P05 | `ordinary_domestic_passport_damaged` — بدل جواز سفر تالف داخل مصر / Replace a damaged ordinary passport inside Egypt | Apply domestically; passport damaged and available | C-P-01–06, 08–10, 14–15, 17–20; blocked on G04 for complete damage-specific steps |
| P06 | `ordinary_domestic_passport_data_reissue` (candidate only) — إصدار جواز سفر ببيانات محدثة داخل مصر / Reissue a passport with updated data inside Egypt | Existing passport; data differs from authoritative records or needs updating | C-P-01, 14, 21–22; blocked G04/G07; distinguish record correction from transcription into a new passport |
| P07 | No new identity yet — التجديد المبكر لجواز السفر / Early passport renewal | Valid passport with usable pages and no data change | No verified early-renewal window; blocked G04 |
| P08 | `ordinary_consular_passport_first_issue` (mission-scoped versions) — إصدار جواز سفر لأول مرة بالخارج / First ordinary passport through a consulate | Overseas submission; never had a passport; adult/child subcases | C-O-01, 05–06; child draft research; adult checklist/mission conditions blocked under G06/G08 |
| P09 | `ordinary_consular_passport_renewal` (mission-scoped versions) — تجديد جواز السفر بالخارج / Renew an ordinary passport through a consulate | Overseas application; existing passport available; renewal reason verified | C-O-02, 04–06; draftable per mission after D04/D05 |
| P10 | `ordinary_consular_passport_lost` (mission-scoped versions) — بدل جواز سفر مفقود بالخارج / Replace a lost passport through a consulate | Applying abroad after loss; nationality/identity established | C-O-03–06; draftable with prior-approval step; incomplete-copy cases G05 |
| P11 | `ordinary_consular_passport_damaged` (mission-scoped versions) — بدل جواز سفر تالف بالخارج / Replace a damaged passport through a consulate | Applying abroad with damaged passport | C-O-03–06; blocked on separating damage from loss-only checklist text |
| P12 | No separate identity until confirmed — تحديث بيانات جواز السفر بالخارج / Update passport data through consular reissuance | Profession/qualification/marital data changes; may coexist with renewal | C-O-02/05; blocked G07/G08; not assumed to be a second fee-bearing transaction |
| P13 | `consular_temporary_return_document` — وثيقة سفر مؤقتة للعودة إلى مصر / Temporary document to return to Egypt | Abroad, temporary return output requested because ordinary travel document unavailable/expired | C-O-10/11; draftable scoped guidance, D06/G06/G08 |
| P14 | `consular_newborn_return_document` — وثيقة سفر مؤقتة لحديث الولادة / Temporary return document for a newborn | Newborn abroad; temporary return output, not a full passport | C-O-12; draftable baseline, specialist/mission exceptions unresolved |

## Version contents and conditions

For P01–P05, author common documentary claims separately with their own conditions. Share
Document Type identities, not a global checklist. Student, military, marital, identity-age,
representation and channel conditions are independent. Document possession normally describes
readiness; it is not by itself an eligibility decision.

| Component | Supported content | Remaining boundary |
| --- | --- | --- |
| Identity/checklist | C-P-01–09 with individual applicability; S06 replacement scope | G05 alternatives, G08 contested records |
| Preparation/submission | C-P-15 and reviewed C-P-10; P03 uses C-P-12; P04 uses C-P-13 | Collection/representative proof and damage-specific handling |
| Military | C-P-04 plus exact C-P-11 exception and student subcase | Exemption, postponement, travel permission and legal eligibility are different concepts |
| Fees | C-P-16 or C-P-17 and the chosen researched optional component | G01 totals and approvals affecting timing |
| Routing | C-P-20; P04 domestic Consulates Department | G06 named outlets, jurisdiction and current availability |
| Warnings | C-P-14 and other scoped administrative limits; separate product safety wording | No unverified detention, travel-ban, custody or penalty advice |
| Dependencies | C-P-01 ID-document prerequisite in its branch | Use the appropriate [National ID transaction](../national-id-suite/procedures.md), not unchanged renewal for a lost card |

P06 means a **new document** where supported, not editing an issued booklet. Whether particular
changed-data cases are P02 or a separate transaction remains G04/G07. Expiry plus changes is
coherent; do not invent a contradiction, discard facts or select two candidates. A generic power
of attorney does not establish C-P-10 passport powers; the current minor-role enum cannot encode
all categories. Keep expansion blocked until narrower meanings and proof are reviewed.

P08–P14 need explicit mission/channel scope and current local evidence. MFA general guidance does
not establish a missing local price/appointment or an adult-first-passport checklist. A renewal,
loss approval and emergency return output are distinct. Urgency alone must not select P13.

## Adjacent and combined cases

Child/newborn ordinary passports use reviewed age/representation branches; temporary newborn
return documents remain P14. Military-status determinations/travel permission, nationality and
contested identity/custody issues are separate specialist services, not conclusions from a
parent's answer or document name. A lost passport and ID together remain G05: no circular
“obtain each first” plan and no invented identity alternative.

Passport data certificates and movement certificates are adjacent outputs, not renewal;
PSM/[S22](../national-id-suite/sources.md#s22) discovery is not a complete procedure pack.
Diplomatic/special/service passports and Palestinian/refugee/stateless travel documents are
outside ordinary Egyptian-citizen selection. A recovered passport after replacement is not
assumed usable; its cancellation consequence needs its own evidence. The separate ID rule is
[C-N-04](../national-id-suite/claims.md), not authority for a passport cancellation claim.

Accessible/mobile/mall/home/hospital/postal channels belong to Service Point material unless
the administrative transaction genuinely differs. G06 controls verified availability. No online
passport-completion promise was established. Speed/travel dates never waive a requirement or approval.

## Per-version publication checklist

Each version needs a named human author, reviewed bilingual text, explicit applicability and
editorial interval, correctly scoped evidence for every material claim, resolved consequential
discrepancies and passing production Planning Scenarios. Legal interpretation and applicable
military/custody/guardianship/contested-identity branches need the relevant independent specialists.
Fees or exact routing may remain unknown where permitted; missing transaction definitions or
required-document alternatives cannot be hidden inside a supposedly complete plan.
