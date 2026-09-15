# National ID sources and retrieval record

All retrievals recorded here were made on **2026-09-12**. These observations are moved from
the original PR #138 research, not newly verified on the documentation-split date. A Source
supports a scoped claim, not an entire Procedure Version. Preserve original dated Source rows
on import; do not confuse editable Markdown with immutable published database provenance.

Short anchors are navigation aids, not complete transcriptions or approved translations.
A digest identifies an inspected response but does not preserve its full bytes. Reviewers must
reopen sources and retain the relevant material in the editorial evidence system before publication.
Source IDs retain the original S01–S25 aliases; missing numbers belong to the other suite.

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

### S15

- **Publisher:** MFA.
- **Title / URL:** [National ID renewal](https://www.mfa.gov.eg/ar/ConsularServicesAndTransactions/Details/94).
- **Location:** five document/procedure bullets.
- **Anchor:** `فى حال طلب تغيير المهنة`
- **State:** full page inspected; undated. No mission-wide fee, turnaround, or first-issuance promise.

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

### S24

- **Publisher:** Egyptian Consulate General in London.
- **Title / URL:** [National ID renewal](https://egyptconsulate.co.uk/consular-services/renewing-national-id/).
- **Location:** document list, changed-data branches, fee and appointment instructions.
- **State:** full direct GET inspected; public reader intermittently challenged. Undated. BRP wording
  and fee/appointment details require present-day confirmation.
- **Related official notice:** https://egyptconsulate.co.uk/ — homepage announces a fee change from
  2026-03-01 with listed exceptions, and a passport appointment update. It is not a corrected ID tariff.

## Narrow cross-family references

The original PSM discovery record is [S25](../passport-suite/sources.md#s25); use only its
Civil Status/data-change locators for this suite. The passport age comparison can consult
[S02](../passport-suite/sources.md#s02) and [S14](../passport-suite/sources.md#s14), not transplant
their passport requirements into ID issuance. S25 is one shared discovery record, not a joint catalog.

## Excluded evidence and retrieval limits

The public web reader rejected several Ministry URLs; ordinary unauthenticated GETs returned
S22 and S24 public HTML. No login, cookies, access-control changes or private endpoints were used.
A [Cairo Governorate article](https://www.cairo.gov.eg/ar/news/2025/3ddd7f9e597042a9808999bbbbabb62f)
dated 2025-05-22 republishes newspaper material; government hosting does not make its online-ID
instructions a competent-authority specification. Digital Egypt's https://digital.gov.eg/ response
was a shell, not applicable service terms: no online first issuance/all-data-changes promise follows.
The old SIS consular locator could not be reopened; direct MFA sources replace it as new research,
not an in-place Source-row rewrite. Commercial/news/social/foreign-government material is discovery
only. Gazette text extraction was unreliable; cited pages were inspected visually in the original
research. That inspection did not certify the complete consolidated law.
