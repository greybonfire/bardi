# Passport renewal sources and Evidence Links

> Successor research (2026-09-12): see the [passport and National ID suite](../passport-national-id-suite/README.md)
> and its [discrepancy register](../passport-national-id-suite/claims.md). This file remains a historical snapshot. The old
> `PPAr.htm` locator currently serves a privacy policy; use the reviewed successor-source workflow, not an in-place historical rewrite.

Research snapshot: 2026-08-25

This file preserves the research provenance used by the ordinary domestic passport-renewal evidence pack. The pack prefers current first-party Ministry of Interior material. Older government pages and low-context web reports are retained only to expose temporal conflicts or research leads.

`Source`, `Evidence Link`, and lightweight `Evidence Discrepancy` are distinct persistence concepts for the eventual admin/research system. A Source preserves the publication or report once; an Evidence Link records how an evidence-bearing semantic claim uses that Source; an Evidence Discrepancy preserves a small internal editorial record when relevant evidence materially conflicts or has uncertain applicability. Their internal storage shape does not prescribe how citations appear in the public UI.

Not every piece of product copy needs an Evidence Link. This file records provenance only for claims that materially assert an external administrative fact, such as requirements, quantities, procedure-selection conditions, fees, validity/turnaround, material process steps, dependencies, routing/jurisdiction, or Field Guidance. Goal/Procedure labels, Question wording, Derived Fact explanations, UI grouping, summaries that add no new administrative assertion, and product safety warnings do not need their own evidence records.

## Source records

### `SRC-MOI-PASSPORT-REQ`

- **Type:** official government source
- **Authority/publisher:** Egyptian Ministry of Interior — General Administration of Passports, Immigration and Nationality
- **Context:** Ministry passport requirements/instructions page
- **Preserved locator:** https://moi.gov.eg/content/PPAr.htm
- **Retrieved:** 2026-08-25
- **Use:** identity branch, student document, military-status document, photographs, originals/copies, passport validity/nature, Form 29, base fee
- **Current authority:** high for ordinary domestic passport requirements as published by the competent authority

Relied-upon Arabic fragments recovered from the Ministry material include the following short passages:

- `بطاقة الرقم القومي لمن بلغت أعمارهم 15 سنة`
- `شهادة الميلاد المميكنة لمن هم دون 15 سنة`
- `شهادة القيد الدراسي للعام الحالي`
- `مستند التجنيد`
- `ثلاث صور شخصية ملونة حديثة خلفية بيضاء مقاس 4×6`
- `أصول المستندات وصورة منها`
- `نموذج 29 جوازات مميكن مجاناً`
- `سبع سنوات`
- `705 جنيه`

The pack uses reviewed English paraphrases rather than presenting these fragments as standalone translations.

### `SRC-MOI-ACCELERATED`

- **Type:** official government source
- **Authority/publisher:** Egyptian Ministry of Interior
- **Context:** Ministry passport service announcements describing urgent and premium processing
- **Preserved locator:** https://moi.gov.eg/News/Index?sectionId=1
- **Retrieved:** 2026-08-25
- **Use:** accelerated-service fees, timing and jurisdiction behavior
- **Current authority:** high for the service categories as published

Relied-upon concepts:

- urgent passport service: delivery on the next working day, additional fee 100 EGP;
- premium passport service: same-day delivery, additional fee 500 EGP;
- identified mall delegations and mobile units provide the named accelerated services without territorial-jurisdiction restriction;
- premium service is also described at the General Administration headquarters and selected office types.

The exact effective-from date was not exposed in the retrieved text, so fee/service claims are verified-on rather than assigned an invented legal effective date.

### `SRC-MOI-OFFICE-DIRECTORY`

- **Type:** official government source
- **Authority/publisher:** Egyptian Ministry of Interior
- **Context:** passport-office/police-directory entries
- **Preserved locator:** https://moi.gov.eg/home/directorypolice
- **Retrieved:** 2026-08-25
- **Use:** stable Service Point identities, locations and example territorial coverage

Recovered directory facts include:

- General Administration of Passports, Immigration and Nationality at Abbassia / El-Sikka El-Bayda Street;
- Giza Passport Office at the Giza Police Department building on Bahr El-Azam Street, with a published list of covered police jurisdictions;
- Dandy Mall passport delegation in 6th of October City.

The evidence pack intentionally does not create a comprehensive nationwide directory.

### `SRC-PSM-RENEWAL-SERVICE`

- **Type:** official government service-directory source
- **Publisher:** Egyptian Public Services / service directory
- **Context:** service titled as obtaining a passport in place of an expired or page-full passport
- **Preserved locator:** https://psm.gov.eg/providers/1/services
- **Retrieved:** 2026-08-25
- **Use:** confirms that expired/page-full replacement is a distinct Procedure within the broader passport Goal
- **Limit:** service-directory content contains older administrative details in places and must not outrank newer competent-authority material on changed thresholds or fees

### `SRC-HISTORIC-GOV-PASSPORT`

- **Type:** stale official government source
- **Publisher:** older Egyptian government/public-service material
- **Context:** historical passport requirements
- **Retrieved:** 2026-08-25
- **Use:** discrepancy/history only
- **State:** stale

This material used the former age threshold of 16 and contained older fee values. It is retained to prove that those attributes are temporal and must not be hard-coded as timeless rules.

Historical domestic guidance also identified the old passport as part of renewal. Because current domestic Ministry exact wording for that item was not recovered in this research pass, it is corroborative history rather than sufficient present support.

### `SRC-MFA-CONSULAR-PASSPORT`

- **Type:** official government source, wrong jurisdiction for direct domestic use
- **Authority/publisher:** Egyptian Ministry of Foreign Affairs / consular service
- **Context:** passport issuance/renewal outside Egypt
- **Preserved locator:** https://sis.gov.eg/ar/بوابة-معلومات-للمصريين-بالخارج/الخدمات-الحكومية/دليل-المعاملات-القنصلية/
- **Retrieved:** 2026-08-25
- **Use:** research corroboration for previous-passport and parent/guardian concepts only
- **Applicability:** consular / overseas; not sufficient on its own to support a domestic claim

Current consular guidance requires the previous passport for renewal and describes parental/legal-guardian handling for minors. Issue #1 explicitly excludes diaspora/consular workflows, so these facts remain leads unless current domestic authority material confirms them.

### `SRC-FIELD-2026-LOW-CONTEXT`

- **Type:** contextual web account / field-style report
- **Date:** 2026
- **Place context:** insufficiently precise
- **Use:** internal lead only
- **Publication status:** not eligible for Field Guidance

The account described practical passport-renewal experience and a fee inconsistent with the current Ministry-published base fee. Because the account does not provide enough precise Service Point context and conflicts with current official material, the discrepancy is not promoted into public Field Guidance. It is evidence that fee claims deserve frequent re-verification.

## Evidence Links

Evidence Links are stored for evidence-bearing semantic claims, not for each sentence that may later render those claims. A future UI may combine several claims under one visible source summary or expose the individual Evidence Links behind a “view sources” affordance; this file intentionally records the finer internal provenance.

### `EL-MOI-REQ-01` — adult National ID

- Source: `SRC-MOI-PASSPORT-REQ`
- Claim: applicants age 15 or older use a valid National ID whose recorded details are current
- Original fragment: `بطاقة الرقم القومي لمن بلغت أعمارهم 15 سنة`
- Retrieval context: current Ministry passport requirements page, retrieved 2026-08-25
- Applicability: domestic ordinary passport path; exact effective-from date unknown
- Verification state: current

### `EL-MOI-REQ-02` — under-15 birth certificate

- Source: `SRC-MOI-PASSPORT-REQ`
- Claim: applicants under 15 use a machine-readable birth certificate carrying the national number
- Original fragment: `شهادة الميلاد المميكنة لمن هم دون 15 سنة`
- Retrieval context: current Ministry passport requirements page, retrieved 2026-08-25
- Verification state: current

### `EL-MOI-REQ-03` — student enrollment certificate

- Source: `SRC-MOI-PASSPORT-REQ`
- Claim: students provide a current-academic-year enrollment certificate
- Original fragment: `شهادة القيد الدراسي للعام الحالي`
- Retrieval context: current Ministry passport requirements page, retrieved 2026-08-25
- Verification state: current

### `EL-MOI-REQ-04` — military-status document

- Source: `SRC-MOI-PASSPORT-REQ`
- Claim: the Ministry publishes a military-status-document requirement for the applicable male branch, including the stated birth-date/age qualification used in the research pack
- Original fragment anchor: `مستند التجنيد`
- Retrieval context: current Ministry passport requirements page, retrieved 2026-08-25
- Verification state: current for the ordinary mechanical branch; legal interpretation of exceptional military statuses remains unsupported

### `EL-MOI-REQ-05` — photographs

- Source: `SRC-MOI-PASSPORT-REQ`
- Claim: three recent colour photographs, white background, 4×6
- Original fragment: `ثلاث صور شخصية ملونة حديثة خلفية بيضاء مقاس 4×6`
- Retrieval context: current Ministry passport requirements page, retrieved 2026-08-25
- Verification state: current

### `EL-MOI-REQ-06` — originals and copies

- Source: `SRC-MOI-PASSPORT-REQ`
- Claim: supporting documents are presented as originals with a copy for verification
- Original fragment: `أصول المستندات وصورة منها`
- Retrieval context: current Ministry passport requirements page, retrieved 2026-08-25
- Verification state: current

### `EL-PSM-SERVICE-01` — renewal service identity

- Source: `SRC-PSM-RENEWAL-SERVICE`
- Claim: expired/page-full replacement is exposed as a distinct passport Procedure within the broader passport Goal
- Retrieval context: government public-service directory, retrieved 2026-08-25
- Verification state: current enough for service identity; individual old requirements are not adopted without newer corroboration

### `EL-HIST-OLDPASS-01` — previous passport historical domestic requirement

- Source: `SRC-HISTORIC-GOV-PASSPORT`
- Claim candidate: old passport is brought for renewal
- Applicability: historical domestic guidance
- Verification state: stale / insufficient for current publication

### `EL-MFA-CONSULAR-01` — previous passport in current consular renewal

- Source: `SRC-MFA-CONSULAR-PASSPORT`
- Claim candidate: previous passport is required for renewal
- Applicability: overseas consular service, not domestic
- Verification state: current source but wrong jurisdiction for direct use

### `EL-MOI-PROCESS-01` — Form 29

- Source: `SRC-MOI-PASSPORT-REQ`
- Claim: machine-readable Passport Form 29 is obtained free of charge
- Original fragment: `نموذج 29 جوازات مميكن مجاناً`
- Verification state: current

### `EL-MOI-PROCESS-02` — complete form

- Source: `SRC-MOI-PASSPORT-REQ`
- Claim: the applicant completes the relevant first-page information in the passport form
- Retrieval context: current Ministry instructions, retrieved 2026-08-25
- Verification state: current

### `EL-MOI-FEE-01` — base passport fee

- Source: `SRC-MOI-PASSPORT-REQ`
- Claim: Ministry-published base machine-readable passport fee is 705 EGP at retrieval
- Original fragment: `705 جنيه`
- Retrieved: 2026-08-25
- Effective-from: unknown
- Verification state: current as retrieved; intentionally short review interval recommended

### `EL-MOI-URGENT-01` — urgent service

- Source: `SRC-MOI-ACCELERATED`
- Claim: next-working-day urgent service carries an additional 100 EGP fee and may be available at identified non-jurisdictional points
- Retrieved: 2026-08-25
- Effective-from: unknown
- Verification state: current as retrieved

### `EL-MOI-PREMIUM-01` — premium service

- Source: `SRC-MOI-ACCELERATED`
- Claim: same-day premium service carries an additional 500 EGP fee and is available at identified premium-capable points
- Retrieved: 2026-08-25
- Effective-from: unknown
- Verification state: current as retrieved

### `EL-MOI-ROUTING-01` — territorial routing

- Sources: `SRC-MOI-OFFICE-DIRECTORY`, `SRC-MOI-ACCELERATED`
- Claim: ordinary passport offices can have territorial jurisdiction, while the Ministry explicitly describes some accelerated locations/services without territorial-jurisdiction restriction
- Verification state: current and sufficient to prove Procedure-Version–Service-Point association rules

### `EL-MOI-HQ-01`

- Source: `SRC-MOI-OFFICE-DIRECTORY`
- Claim: General Administration headquarters is in Abbassia / El-Sikka El-Bayda Street context
- Verification state: current directory record as retrieved

### `EL-MOI-GIZA-01`

- Source: `SRC-MOI-OFFICE-DIRECTORY`
- Claim: Giza Passport Office location and published territorial coverage
- Verification state: current directory record as retrieved

### `EL-MOI-DANDY-01`

- Source: `SRC-MOI-OFFICE-DIRECTORY`
- Claim: Dandy Mall passport delegation exists at the listed 6th of October City location
- Verification state: current directory record as retrieved

### `EL-MOI-PASSPORT-NATURE-01`

- Source: `SRC-MOI-PASSPORT-REQ`
- Claim: machine-readable passport is personal and does not add spouse/children
- Verification state: current

### `EL-MOI-VALIDITY-01`

- Source: `SRC-MOI-PASSPORT-REQ`
- Claim: standard published passport validity is seven years
- Original fragment: `سبع سنوات`
- Verification state: current

## Internal Evidence Discrepancy records

These records are for research/admin use only. They are intentionally small and should remain closer to an editorial issue record than an evidence-graph model. The minimum useful shape is the affected claim/subject, the relevant Sources or Evidence Links, a small status vocabulary such as `open` / `resolved` / `needs_reverification`, a concise rationale, and an optional resolution.

The public plan must never render these records or their editorial adjudication text directly. It may expose only the user-relevant consequence, such as a claim being unavailable as current guidance, needing re-verification, or having an unresolved value.

### `DISC-AGE-15-VS-16`

- Status: `resolved`
- Current authority: `SRC-MOI-PASSPORT-REQ` says 15
- Stale authority: `SRC-HISTORIC-GOV-PASSPORT` says 16
- Adjudication: use current competent-authority material for the 2026-08-25 research snapshot; retain old material as historical evidence that the threshold changed
- Consequence: age threshold must be Procedure-Version data, not timeless application code

### `DISC-FEE-CURRENT-VS-HISTORIC-AND-FIELD`

- Status: `resolved_for_snapshot`
- Current authority: Ministry publishes 705 EGP base fee at retrieval
- Historical government material: lower old amounts
- Low-context 2026 web account: materially different reported amount
- Adjudication: current Ministry amount controls; field account is not contextual enough for Field Guidance
- Consequence: Fee needs amount, currency, verification date, effective interval if known, and stale/unverified state

### `DISC-PREVIOUS-PASSPORT-APPLICABILITY`

- Status: `needs_reverification`
- Historical domestic and current consular sources support bringing the previous passport
- Current domestic exact-passage support was not recovered
- Adjudication: exclude from current authoritative checklist until domestic source confirmation
- Consequence: evidence applicability is jurisdiction-specific and cannot be inherited merely because the Authority is Egyptian government

### `DISC-MINOR-SUBMISSION-AUTHORITY`

- Status: `needs_reverification`
- Current consular source describes parent/legal guardian behavior
- older domestic material also addressed parents acting for minors
- current domestic exact passage was not recovered
- Adjudication: identity-document branch is supported; who may submit for the minor remains inconclusive in this pack
- Consequence: do not conflate a minor’s checklist with representation/guardianship rules that lack current domestic support

### `DISC-STANDARD-TURNAROUND`

- Status: `open`
- current first-party source recovered here does not publish a standard turnaround time
- older government and newer secondary reports vary
- Adjudication: current standard time is unknown; only urgent/premium timing is rendered
- Consequence: unknown Fee/time fields must be explicit rather than synthesized from secondary consensus
