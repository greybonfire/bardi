# Egyptian passport and National ID suite

Research snapshot: **2026-09-12**\
Status: **research draft for independent review; not publication approval**\
Repository baseline: `e79bd4e5c3ca67fdc2785d00013ae86681f8e1be`

This pack expands the two renewal-only evidence packs into a transaction inventory for Egyptian
citizens. It records supported claims, remaining research gaps, and the work needed to encode
them in production. It does not activate new public procedures, change preserved versions, or
certify every procedure as ready to publish.

Use the current **Service / Procedure / Procedure Version** vocabulary. The
[production architecture](../../architecture/README.md), accepted ADRs, and
[editorial process](../../editorial-process.md) remain authoritative. Research IDs and candidate
Facts below are proposals, not additions to the production schema or API.

## Read this pack

| File | Purpose |
| --- | --- |
| [Sources](sources.md) | Competent authorities, exact locators, retrieval limitations, dates, and preserved short anchors |
| [Claims](claims.md) | Single claim ledger, source mapping, applicability, fees, conflicts, and unknowns |
| [Procedure catalog](procedures.md) | Full transaction-family inventory, proposed identities, supported components, and readiness blockers |
| [Facts and Questions](facts-and-questions.md) | Reused and proposed typed source Facts, bilingual prompts, and selection boundaries |
| [Scenarios](scenarios.md) | Named positive, negative, UNKNOWN, contradictory, combined, temporal, and jurisdiction cases |
| [Implementation handoff](implementation.md) | Ordered, bounded tasks with acceptance criteria and production integration constraints |

## Scope and completeness

The inventory covers ordinary citizen passports and National ID cards: first issuance, renewal,
loss, damage, data changes/corrections, minors and representatives, special service channels,
overseas applications, and emergency return documents. It distinguishes loss abroad followed by
application inside Egypt from an application submitted to a consulate.

Domestic guidance is researched against the competent Ministry and government service-center
pages. Overseas research covers the MFA's general guidance and concrete London, Dubai, and Sydney
examples. Those examples **do not establish an all-consulates directory or worldwide availability**.
Diplomatic/special/service passports, refugee/stateless-person travel documents, visas, nationality
determinations, travel permissions, and underlying civil-record litigation are named boundaries
and adjacent services; this pack does not claim to have researched their full legal suites.

“Full suite” here means that each transaction family has an explicit disposition in
[the catalog](procedures.md). It does not mean all checklist details, branches, current fees, or
office schedules were recoverable. A row marked `blocked` is a research finding, not a completed
implementation specification. No new family is marked publication-ready.

## Findings that change the earlier research

1. The old passport Source locator `https://moi.gov.eg/content/PPAr.htm` currently returns the
   Ministry's privacy policy when fetched directly. The actual passport pages were recovered;
   use S01–S04 for new evidence records. Do not merely change the URL on a preserved Source.
2. The competent authority separates domestic loss from loss abroad followed by return to Egypt.
   The two routes have materially different steps (C-P-12 and C-P-13).
3. Current domestic representation and military-document exceptions are recoverable (S03).
   They require separate conditional claims and specialist review before broadening the existing
   narrow renewal version.
4. Domestic service-center evidence now supports some previous-document requirements and an
   insurance requirement (S05, S08, S10). Scope is the named service-center channel; absence from
   another page is not proof of an exemption.
5. Official material contains real discrepancies: the lost-ID checklist, consular photo counts,
   passport validity without a current ID, and old age thresholds. Resolve them by claim and
   jurisdiction; do not choose whichever page gives the easiest plan.
6. Catalog growth has a production integration consequence: new Service Questions change existing
   planning behavior signatures. The handoff makes coexistence with preserved scenarios and
   strict importer verification an explicit prerequisite.

## Research and review policy

- Retrieved-on is 2026-09-12. Unless a Source explicitly dates its rule, publication date and
  administrative effective-from are **unknown**. A copyright year is not either date.
- `supported` means the inspected text supports the stated scoped claim. It does not mean a human
  has approved publication, that a live office accepted a case, or that no newer rule exists.
- `needs_reverification` means a material conflict, scope ambiguity, or current-source gap remains.
  Do not solve that uncertainty by asking the applicant to interpret government policy.
- No staff contacts, applications, payments, or appointments were made. No personal case data was
  collected. No field reports are promoted into Field Guidance.
- Accountable human author: **unassigned**. Independent Arabic/English reviewer: **unassigned**.
  Legal, military, and custody/guardianship specialists: **unassigned**, required where the
  relevant risks in the catalog are included. These are actual publication blockers, not implied
  approvals by the researcher or PR author.
- Reverify volatile fees, office availability, and consular instructions immediately before
  importing an authoritative draft; set an explicit editorial re-verification date. This pack
  does not create an evergreen freshness window.

## Relationship to existing production content

The production importers currently encode `ordinary_domestic_passport_renewal` and
`ordinary_domestic_national_id_renewal`. Their research dates and strict seals must remain
reproducible. This pack provides successor research; merging it does not update a deployed
knowledge database or repair already-published citations. Follow task I01 before using the new
sources in production and I02 before expanding shared catalog content.

Historical packs remain available at [passport renewal](../passport-renewal/README.md) and
[National ID renewal](../national-id-renewal/README.md). Their historical assertions should be
read together with this pack's discrepancy register, not treated as newly verified here.
