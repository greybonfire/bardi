# Sources and retrieval record

Retrieved/researched on **2026-09-12**. S01-S10 are local research aliases; use new dated semantic
Source/Evidence Link identities for future authoring. Do not rewrite the family importer's Source
rows. A source's legal author and its archive host are different provenance fields.

`inspected` means the relevant content was actually read, not independently approved or certified
as the complete current law. `search-rendered` identifies text supplied by search while direct
opening failed. `lead`/`unavailable` is insufficient for publication. Unknown dates stay unknown.
Short anchors locate a passage; the [claim ledger](claims.md) contains the scoped interpretation.

## S01

- **Document:** Law 127/1980 issuing the Military and National Service Law.
- **Author:** Egyptian legislature/presidency; Official Gazette original, archived by Manshurat.
- **Metadata:** [Law record](https://manshurat.org/node/12230).
- **Original scan:** [Gazette PDF](https://manshurat.org/file/22756/download?token=l3KnP5M8).
- **Published:** 1980-07-10, Official Gazette 28 supplement.
- **Inspected:** scan PDF pages 1, 5, 10-15; original printed pages 9, 13, 18-23.
- **Relevant passages:** Article 7/First(a), Article 11, Article 12, Article 14's document identity,
  Article 18's grievance framework; issuing-law Articles 1 and 3.
- **Anchor:** `من لا تتوافر فيهم اللياقة الطبية لتلك الخدمة`.
- **Date distinction:** metadata gives 1980-07-11, but issuing Article 1 commences the attached
  law on 1980-12-01; Article 3 gives the earlier date to the preceding transitional article.
  Do not assign the metadata date indiscriminately to every substantive claim.
- **Limit:** the archive labels the law amended; its relations listing is not a certified complete
  amendment chain. Current consolidation and implementing rules remain G01.
- **SHA-256, downloaded PDF:** `f1cfc648c4b600d75581e5bef7421102575703d69b088b97e2e251fffe126f50`.

## S02

- **Document:** Minister of Defense and Military Production Decision 195/2020, medical fitness
  for military and national service.
- **Author:** Minister of Defense; Al-Waqa'i al-Misriyya text hosted by the Egyptian Bar Association.
- **Discovery:** [Bar Association publication](https://egyls.com/الجريدة-الرسمية-تنشر-قرار-وزير-الدفاع/).
- **Primary text:** [Decision PDF](https://egyls.com/wp-content/uploads/2020/11/قرار-وزير-الدفاع-والإنتاج-الحربى-رقم-195-لسنة-2020.pdf).
- **Issued/effective under Article 7:** 2020-10-13. **Published:** 2020-11-15, issue **257**.
  These dates and the issue number were read from the document, not inferred from news metadata.
- **Locations:** PDF page 1 / printed 3 (Articles 1-2); PDF 18 / printed 20 (Article 2/X(1),
  psychiatric provisions); PDF 19 onward / printed 21 onward (X(2), neurological provisions);
  PDF 29-30 / printed 31-32 (other fitness classification, Articles 4-7).
- **Anchor:** `الأمراض النفسية والعصبية`.
- **Inspected:** text extraction, visual review of PDF pages 1, 18 and 30. The clinical list is a
  source for specialist interpretation, not an endorsed modern diagnostic taxonomy.
- **Limit:** read with S03. No claim that searching found every subsequent amendment.
- **SHA-256, PDF:** `0aabf42de40ae23ce877dea5003860e05ea9ffae08f179ec369fce22e9d25f64`.

## S03

- **Document:** Minister of Defense Decision 166/2022 amending Decision 195/2020.
- **Primary text:** two published-page images hosted by Al-Ahram, visually inspected in full.
- [Host article](https://gate.ahram.org.eg/News/3632277.aspx),
  [printed page 3](https://gate.ahram.org.eg/Media/News/2022/8/9/2022-637956468384536067-453.jpg),
  [printed page 4](https://gate.ahram.org.eg/Media/News/2022/8/9/2022-637956468462386577-238.jpg).
- **Issued/effective under Article 4:** 2022-07-04. **Published:** 2022-08-08, issue 171.
- **Locations:** Article 1 replaces specified orthopedic wording; Article 2 repeals old Article 4;
  Article 4 states commencement. Do not confuse the amendment's Article 4 with the repealed one.
- **Anchor:** `تلغى المادة الرابعة`.
- **SHA-256, page 3:** `2fd21e6f5f458c7974246d03b16553de813b94a98d1d7676fdac860d8f20a3b6`.
- **SHA-256, page 4:** `a54d43291b95b08aedda661927a2ad057a9a2489ab148e2fbdbe2a4fb83ef902`.

## S04

- **Publisher:** Ministry of Defense, Recruitment and Mobilization.
- **Title/date:** opening of electronic recruitment-services center, 2018-12-28.
- **Locator:** [Official announcement](https://www.mod.gov.eg/ModWebSite/NewsDetailsAr.aspx?id=35698).
- **Location:** enumerated online services, including medical-unfitness exemption certificates.
- **Anchor:** `بدل فاقد - إصدار تالى`.
- **Retrieval:** official article body was search-rendered; direct public GET/open returned 502.
- **Use:** historical existence and stated transaction scope only, C10. Not evidence of the
  current fee, a functioning online assessment, or first-time adjudication through a web form.

## S05

- **Publisher:** Ministry of Defense.
- **Title:** April 2026 recruitment intake.
- **Locator:** [Official intake announcement](https://www.mod.gov.eg/modwebsite/NewsDetailsAr.aspx?id=45727).
- **Locations:** intake-specific document list; exemption/postponement/exception instruction;
  official inquiry contact section.
- **Retrieval:** article body search-rendered; direct opening failed. Publication date not independently
  established here. The batch's appointments are historical, not available September appointments.
- **Anchor:** `بالمستندات التى تؤيد أحقيته`.
- **Use:** C11's limited general instruction. The batch checklist is not a complete medical-exemption
  checklist. Do not import its dates or amounts into a new version.
- The older pack's October-intake locator
  [45878](https://www.mod.gov.eg/modwebsite/NewsDetailsAr.aspx?id=45878) also returned 502;
  the previous research snapshot is not fresh verification by this pack.

## S06

- **Publisher:** Ain Shams University, reporting its own collaboration with Recruitment and Mobilization.
- **Title:** exemption-certificate delivery under the Forsan al-Erada initiative.
- **Locator:** [University event report](https://www.asu.edu.eg/ar/7950/news/delivering-the-military-service-exemption-certificates-to-the-disabled-students-as-part-of-the-forsan-al-erada-initiative-in-cooperation-between-ain-shams-university-and-the-armed-forces-recruitment-and-mobilization-department).
- **Inspected:** full article body; opening medical-committee paragraph and director's statement
  about special committees at residences. Publication/event date not visible in the inspected body;
  search recency and footer year are not an event date.
- **Use:** C12-C13, evidence of arrangements and authority assessment, not a standing appointment offer.

## S07

- **Publisher:** Ministry of Defense.
- **Locators:** [Arabic accessibility announcement](https://www.mod.gov.eg/modwebsite/NewsDetailsAr.aspx?id=45684),
  [English version](https://www.mod.gov.eg/modwebsite/NewsDetails.aspx?id=45684).
- **Retrieval:** search excerpts only; direct requests failed. Arabic search date 2025-11-12 versus
  English search date 2025-12-11 is unresolved metadata, not an established event-date difference.
- **Disposition:** corroborating lead for local/mobile committees; do not base current booking,
  coverage or a universal zero fee on these snippets. Use S06 only for its limited inspected scope.

## S08

- **Publisher:** Recruitment and Mobilization Administration.
- **Locators:** [Certificate instructions](https://tagned.mod.gov.eg/16militaryServiceExemptionC.aspx),
  [regions](https://tagned.mod.gov.eg/tagneedPlaces.aspx), [portal](https://tagned.mod.gov.eg/).
- **Retrieval:** public requests failed (502); no forms completed, login, payment or case lookup.
- **Disposition:** unavailable. Existing family-pack descriptions are historical leads. Medical-specific
  eligibility, first issue versus reissue, payment, collection and current routing remain G03-G05.

## S09

- **Subject:** Law 2/2026 and the complete amendment history of Law 127/1980.
- **Locators:** [SIS Gazette record](https://mediadr.sis.gov.eg/xmlui/handle/123456789/125126?locale-attribute=en),
  [Parliament history](https://www.parliament.gov.eg/News_Show.aspx?frm=5692),
  [MKS mirror](https://mksegypt.org/ar/laws/24662),
  [archive relations](https://manshurat.org/node/12230/relations).
- **Retrieval:** SIS/Parliament unavailable, MKS returned 403. Archive relations page retrieved;
  it does not establish a complete consolidated current law.
- **Disposition:** explicit reverification gap. Earlier family-pack text and news reports identify
  an amendment lead; this pass does not newly certify its complete scope or apply it to medical
  exemption. Obtain the enacted text and relevant later regulations, not just parliamentary approval.

## S10

- **Publisher:** Egyptian Consulate General in London.
- **Locator:** [Exemption from military service](https://egyptconsulate.co.uk/consular-services/exemption-from-military-service/).
- **Inspected:** official page text returned in search, including its 2024-11-01 resumption notice.
- **Use:** scope exclusion only. Its enumerated family/nationality/student branches do not establish
  a London medical-assessment route. None of its charges or checklists is a medical-exemption tariff.

## Evidence preservation and excluded material

PDFs/images were downloaded from public locators for visual verification. Digests identify the
inspected bytes but are not preservation of those bytes in the repository. Before publication,
the accountable author must preserve the relevant passages in the editorial evidence workflow
and recheck current applicability. No full source books, patient records or media images are
committed by this PR.

Newspaper summaries, forum accounts, social posts and other countries' medical standards were
discovery material only. Gazette images hosted by a newspaper are primary text; the newspaper's
paraphrase is not the medical authority. Foreign asylum-country reports are not Egyptian operating
instructions. The Ministry's military-academy admissions pages concern a different process.
