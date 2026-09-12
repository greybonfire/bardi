# Sources and retrieval record

All retrievals in this file were made on **2026-09-12**. Claim content is centralized in
[claims.md](claims.md); a Source is not blanket support for an entire Procedure Version.
S01–S25 are local research aliases. Use new dated semantic Source IDs on import, preserving old
Source rows. Effective dates are unknown except where explicitly stated below.

The public web reader returned access-rejection pages for several Ministry URLs. Ordinary,
unauthenticated HTTP GETs from the research workspace returned the actual public HTML for
S01–S04 and S22–S24. No login, cookies, access-control changes, or private endpoints were used.
The passport tab URLs are GET endpoints referenced by the public page's own JavaScript.

Short anchors below are navigation aids, not complete transcriptions or approved translations.
Byte digests identify the inspected response; a digest alone does not preserve its full contents.
Reviewers must reopen the source and preserve the relevant material in the editorial evidence
system before publication. Search snippets used only for discovery are explicitly identified.

### S01

- **Publisher:** Ministry of Interior, General Administration of Passports, Immigration and Nationality.
- **Title:** Passport issuance / fees.
- **URL:** https://moi.gov.eg/passports/home/GetPassport/1
- **Inspected equivalent request:** https://moi.gov.eg/passports/home/getpassport/1
- **Location:** introductory paragraph; Form 29 bullets; ordinary/replacement fee and accelerated-service headings.
- **Anchor:** `رسم إستخراج جواز السفر المصري`
- **State:** full public HTML inspected; page has no dated administrative update. Footer 2019 is not a fee effective date.
- **Scope:** domestic passport services and explicitly described jurisdiction exceptions.
- **SHA-256:** `70b1c49913aa6180559351efce261d367de6e09b67c4c40455715e742fa714dd`.

### S02

- **Publisher:** same competent Ministry authority.
- **Title:** Documents required for a passport.
- **URL:** https://moi.gov.eg/Passports/home/PassportRequiredPapers
- **Location:** document bullets and following instructions.
- **Anchor:** `بطاقة الرقم القومي لمن أتم الخامسة عشر عاماً`
- **State:** full public HTML inspected; publication/effective dates unknown.
- **Scope:** domestic passport documentary guidance; military exception must also be read with S03.
- **SHA-256:** `a646274ada78e1cfd1c4af70a6a0c1f2bb8eb97c8948d804d2d520c60d9d379e`.

### S03

- **Publisher:** same competent Ministry authority.
- **Title:** Acceptance of passport applications.
- **URL:** https://moi.gov.eg/Passports/home/PasswordAcceptRequests
- **Location:** acceptance list; military-document section; final notes.
- **Anchor:** `قبول الطلبات`
- **State:** full public HTML inspected; administrative update date unknown.
- **Scope:** domestic submission/representation and military-document exceptions. Described emigrant
  and maternal-nationality cases are specialist leads, not a nationality adjudication algorithm.
- **SHA-256:** `e5dd1516c94aaf2c9e9ad2766f567c70c61014fcea26d8ebe6aa3dd9fb830cec`.

### S04

- **Publisher:** same competent Ministry authority.
- **Title:** Passport loss.
- **URL:** https://moi.gov.eg/Passports/home/PasswordLost
- **Location:** domestic-loss paragraph and overseas-loss/Consulates Department section.
- **Anchor:** `ولا يطالب بمذكرة الإبلاغ عن فقده بقسم الشرطة`
- **State:** full public HTML inspected; publication/effective dates unknown.
- **Scope:** loss inside Egypt; application to the domestic Consulates Department after loss abroad.
  Later refugee/stateless travel-document sections are adjacent-service leads only.
- **SHA-256:** `2e092d76625551c7ce193f8faa28928f8a50936e70ba7abf32f1da6b7481810b`.

### S05

- **Publisher:** Government of Egypt, Khadamat Misr service centers.
- **Title / URL:** [New/renewed passport](https://www.khadamatmisr.gov.eg/node/54).
- **Location:** required-documents list; service-center list.
- **Anchor:** `جواز سفر سابق إن وجد`
- **State:** full page inspected; undated. Channel-scoped documentary support; not an exhaustive checklist.

### S06

- **Publisher:** Khadamat Misr.
- **Title / URL:** [Lost/damaged passport](https://www.khadamatmisr.gov.eg/node/53).
- **Location:** required-documents list.
- **Anchor:** `جواز سفر بدل فاقد/تالف`
- **State:** full page inspected; undated. Combined heading does not erase the Ministry's loss-specific steps.

### S07

- **Publisher:** Khadamat Misr.
- **Title / URL:** [First National ID](https://www.khadamatmisr.gov.eg/node/63).
- **Location:** two required-document bullets.
- **Anchor:** `ضامن: أقارب حتى الدرجة الثالثة`
- **State:** full page inspected; undated. Sparse student/guarantor guidance; not a complete general first-issuance checklist.

### S08

- **Publisher:** Khadamat Misr.
- **Title / URL:** [National ID renewal](https://www.khadamatmisr.gov.eg/node/61).
- **Location:** required-documents sentence.
- **Anchor:** `بطاقة الرقم القومي القديمة`
- **State:** full page inspected; undated. Marriage-document condition needs clarification for unchanged-data renewals.

### S09

- **Publisher:** Khadamat Misr.
- **Title / URL:** [Lost National ID](https://www.khadamatmisr.gov.eg/node/62).
- **Location:** required-documents sentence.
- **Anchor:** `بطاقة الرقم القومي القديمة`
- **State:** full page inspected; **internally ambiguous** because the transaction is loss replacement.
  Do not silently substitute “copy” for “old card.”

### S10

- **Publisher:** Khadamat Misr.
- **Title / URL:** [Damaged National ID](https://www.khadamatmisr.gov.eg/node/64).
- **Location:** required-documents sentence.
- **Anchor:** `بطاقة الرقم القومي التالفة`
- **State:** full page inspected; undated. Marriage proof is mentioned for a husband/wife; applicability needs review.

### S11

- **Publisher:** Khadamat Misr.
- **Title / URL:** [National ID data changes](https://www.khadamatmisr.gov.eg/node/65).
- **Location:** two required-document bullets.
- **Anchor:** `ما يفيد تغيير البيانات`
- **State:** full page inspected; undated. Does not specify which address, profession, or civil-record documents qualify.

### S12

- **Publisher:** Egyptian Official Gazette; scan hosted by Manshurat Legal, an external archive.
- **Document:** Civil Status Law 143/1994.
- **Metadata:** https://manshurat.org/node/31633
- **Scan:** https://manshurat.org/file/41801/download?token=z74noS-l
- **Locations visually inspected:** PDF pages 15–17 (1-based), printed pages 17–19: Articles
  48, 52–54, and 62. Do not confuse printed and PDF page numbers.
- **Anchor:** `خلال خمسة عشر يوما`
- **Published:** 1994-06-09; base law effective 1994-06-10 per archive metadata.
- **State:** original enacted wording verified visually; **not a certified current consolidation**.
  The archive's amendment list omits the 2022 amendment, so it cannot prove the absence of later changes.
- **SHA-256:** `7e1d629a6756a5bb2937230ba4fab5446f7de182b39192459721305318a94535`.

### S13

- **Publisher:** Egyptian Official Gazette; scan hosted by Al-Ahram, not a government-hosted consolidation.
- **Document:** Law 165/2022 amending Article 48 of Law 143/1994.
- **Discovery page:** https://gate.ahram.org.eg/News/3805812.aspx
- **Scan:** https://gate.ahram.org.eg/media/News/2022/11/6/2022-638033397276961233-696.pdf
- **Location visually inspected:** PDF page 1, printed page 9; Gazette 44 supplement (A), 2022-11-03.
- **Anchor:** `خمسة عشر عاماً`
- **Effective:** 2022-11-04, derived from the Gazette date and Article 2's next-day commencement.
  The host news page's 2022-11-06 timestamp is not the enactment/effective date.
- **State:** amendment text verified visually; later-amendment sweep remains a legal-review gate.
- **SHA-256:** `0a76945934720532c3ae4b12b76097d99e52fc4fd831c95b927dac7678b89ae7`.

### S14

- **Publisher:** Egyptian Ministry of Foreign Affairs (MFA).
- **Title / URL:** [Passport issuance/renewal](https://www.mfa.gov.eg/ar/ConsularServicesAndTransactions/Details/73).
- **Locations:** first-issuance section; age/sex renewal sections; lost/damaged section and notes.
- **Anchor:** `للتقديم على جواز سفر بدل فاقد/تالف`
- **State:** full page inspected; undated, site labeled experimental. First-issuance wording concerns
  children; it does not establish a complete adult first-issuance checklist. Some age headings leave
  exactly 15 ambiguous, and the combined replacement section includes loss-only documents.
- **Scope:** consular guidance. Requires reconciliation with the applicable mission, not domestic reuse.

### S15

- **Publisher:** MFA.
- **Title / URL:** [National ID renewal](https://www.mfa.gov.eg/ar/ConsularServicesAndTransactions/Details/94).
- **Location:** five document/procedure bullets.
- **Anchor:** `فى حال طلب تغيير المهنة`
- **State:** full page inspected; undated. No mission-wide fee, turnaround, or first-issuance promise.

### S16

- **Publisher:** MFA.
- **Title / URL:** [Temporary travel document](https://www.mfa.gov.eg/ar/ConsularServicesAndTransactions/Details/88).
- **Location:** general documents and passport-loss subsection.
- **Anchor:** `محضر رسمي بفقد جواز السفر`
- **State:** full page inspected; undated. Mission-specific validity and acceptance must be checked separately.

### S17

- **Publisher:** MFA.
- **Title / URL:** [Newborn temporary travel document](https://www.mfa.gov.eg/ar/ConsularServicesAndTransactions/Details/2).
- **Location:** ten numbered bullets.
- **Anchor:** `طلب إصدار وثيقة سفر للأطفال`
- **State:** full page inspected; undated. Distinct output from a full passport; custody/nationality exceptions unresolved.

### S18

- **Publisher:** Egyptian Consulate General in London.
- **Title / URL:** [Passport](https://egyptconsulate.co.uk/consular-services/egyptian-passport/).
- **Locations:** general information, requirements, fees; page says updated **2024-09-12**.
- **Anchor:** `Updated 12 September 2024`
- **State:** full page inspected; conflicts/scope differences with S14 require mission confirmation.
- **Scope:** London only; no worldwide extrapolation.

### S19

- **Publisher:** same London consulate.
- **Title / URL:** [Temporary return document](https://egyptconsulate.co.uk/consular-services/travel-document/).
- **Locations:** general information and requirements.
- **Anchor:** `return to Egypt ONLY`
- **State:** full page inspected; undated. Photo count differs from S16; transit acceptance is explicitly conditional.

### S20

- **Publisher:** Egyptian Consulate General in Sydney.
- **Title / URL:** [First National ID](https://egyptconsulatesydney.com/en/national-id-card-first-issuance/).
- **Locations:** opening availability paragraphs, age sentence, identity/residence/occupation sections.
- **Anchor:** `specialized committees`
- **State:** full page inspected; undated. Contains an age-16 rule inconsistent with S13; do not import
  its entire checklist as a current domestic rule. No live committee date was verified.

### S21

- **Publisher:** Egyptian Consulate General in Dubai.
- **Title / URL:** [National ID renewal](https://dubai.egyptconsulates.org/id-card.html).
- **Locations:** required documents, fee, approximate processing duration.
- **Anchor:** `الهوية الاماراتيه`
- **State:** full page inspected; undated. Named mission example requiring fresh operational verification.

### S22

- **Publisher:** Ministry of Interior.
- **Title / URL:** [Public services directory](https://moi.gov.eg/home/directoryservices).
- **Location:** Civil Status / National ID entry, linking to https://cso.moi.gov.eg/NetServices?ServiceId=9
- **State:** directory HTML inspected. Target GET returned a minimal shell; the public web reader
  returned an access rejection. No transaction eligibility, price, or complete online journey was verified.

### S23

- **Publisher:** Ministry of Interior.
- **Title / URL:** [Privacy policy](https://moi.gov.eg/content/PPAr.htm).
- **Location:** opening privacy heading and stated policy date 2019-01-25.
- **Anchor:** `سياسة الخصوصية`
- **State:** full response inspected, Windows-1256 encoding. **Wrong current locator** for passport
  requirements; no assertion is made about what this URL served at an earlier research date.
- **SHA-256:** `3d6dd6ecd74449e07652046ae5e9b67f259e5d35e2ff9a71e0769e7b21e507a7`.

### S24

- **Publisher:** Egyptian Consulate General in London.
- **Title / URL:** [National ID renewal](https://egyptconsulate.co.uk/consular-services/renewing-national-id/).
- **Location:** document list, changed-data branches, fee and appointment instructions.
- **State:** full direct GET inspected; public reader intermittently challenged. Undated. BRP wording
  and fee/appointment details require present-day confirmation.
- **Related official notice:** https://egyptconsulate.co.uk/ — homepage announces a fee change from
  2026-03-01 with listed exceptions, and a passport appointment update. It is not a corrected ID tariff.

### S25

- **Publisher:** Egyptian Public Services Guide (PSM).
- **Discovery locators:** [Civil Status](https://psm.gov.eg/providers/1/services),
  [Passports](https://psm.gov.eg/providers/65/services),
  [ID residence change](https://psm.gov.eg/services/17),
  [ID profession change](https://psm.gov.eg/services/122),
  [ID marital-status change](https://psm.gov.eg/Services/11),
  [damaged passport](https://psm.gov.eg/services/360).
- **State:** titles recovered from current search results and/or the retained renewal packs;
  full detail requests failed. **Discovery-only**, not current documentary or fee evidence.
  C-S-03 identifies exactly what can be inferred from these titles.

## Excluded evidence and retrieval limits

- A [Cairo Governorate article](https://www.cairo.gov.eg/ar/news/2025/3ddd7f9e597042a9808999bbbbabb62f)
  dated 2025-05-22 republishes a newspaper story. Government hosting does not make its online-ID
  instructions a competent-authority transaction specification; not used to authorize that route.
- Digital Egypt's https://digital.gov.eg/ response exposed a shell, not the applicable ID-service
  terms. Do not infer first issuance, all data changes, or passport issuance can be completed online.
- The old SIS consular locator could not be re-opened. S14–S17 provide direct MFA sources instead.
- Commercial agents, news how-tos, social posts, and foreign governments' descriptions of Egyptian
  documents were discovery leads only. No unsupported numerical fee, penalty, or processing time
  is adopted from them.
- Gazette PDF text extraction was unreliable. The cited pages were rendered and read visually.
  The originals were inspected, but this research has not certified a complete consolidated law.
