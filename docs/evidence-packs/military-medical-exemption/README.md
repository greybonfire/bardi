# Medical unfitness: military-service exemption

Research snapshot: **2026-09-12**\
Status: **research draft; independent legal, military and bilingual review pending**\
Production baseline: `e79bd4e5c3ca67fdc2785d00013ae86681f8e1be`

This pack researches one Egyptian military branch: exemption for the applicant's own medical
unfitness, including psychiatric, neurological and physical conditions. It supports production
authoring; it does not diagnose an applicant, determine fitness, grant an exemption, or publish
new guidance. The PR changes documentation only.

| Document | Purpose |
| --- | --- |
| [Sources](sources.md) | Inspected legal texts, official operational material, dates and retrieval limits |
| [Claims and gaps](claims.md) | Claim-level evidence, discrepancies and exact research closure requirements |
| [Workflow and Facts](workflow-and-facts.md) | Administrative stages, bilingual questions, supported content and selection boundaries |
| [Scenarios](scenarios.md) | Future production acceptance cases, including mental-health and physical-health boundaries |
| [Implementation](implementation.md) | Ordered, bounded follow-up tasks and compatibility gates |

## Research outcome

The foundation is Article 7/First(a) of Law 127/1980, read with the competent medical authorities
and procedures in Article 12 and Decision 195/2020 as amended. The reviewed text distinguishes
medical assessment from the administrative certificate service. The physical and mental-health
provisions belong to this same branch; they are not independent exemptions inferred from a
diagnosis supplied to Bardi. See C01-C09 in the [claim ledger](claims.md).

The research is sufficient to define an administrative-assistance draft and its boundaries.
It is **not sufficient to publish a complete first-application checklist, current fee, appointment,
appeal workflow, or automated disease/measurement eligibility rule**. The missing evidence is
itemized as G01-G08, rather than delegated to applicants as questions about government policy.

## Scope

The initial implementation target is an Egyptian citizen handling their own pre-service medical
assessment and exemption paperwork inside Egypt. Existing authority decisions, pending assessment,
and requests for a certificate after a decision are separate stages. The draft must distinguish
them even if final transaction identities require further review.

| Boundary | Treatment |
| --- | --- |
| Mental-health and physical-health conditions | Same administrative branch; no diagnostic interview or clinical scoring |
| Person who cannot travel to an examination | Research documented committee arrangements; no guaranteed home visit or invented booking |
| Already medically exempt, certificate lost or another copy needed | Adjacent certificate transaction; not a new medical determination |
| Disputed fitness, new examination instruction, or changed health after a decision | Authority-review boundary; no automatic reversal or assumption that a decision is unreviewable |
| Already serving, reserve service, medical discharge, injury compensation or pension | Separate legal/administrative scope; not implemented by this branch |
| Family member unable to earn | Existing family-exemption research, not the applicant's medical unfitness |
| Overseas assessment, consular handling, late-status settlement, nationality disputes | Not established here; no copied domestic/other-exemption procedure |
| Military academy admission or volunteering | Different admission context; do not import its standards into conscription |

Scope exclusions are product coverage boundaries, not declarations of legal ineligibility.
An existing medical decision and a family circumstance may both be true. They are not a
contradiction, and the planner must not silently choose whichever branch is first.

## Production integration and review

Use the existing Service `handle_military_service_paperwork` / التعامل مع أوراق الخدمة العسكرية.
The proposed Procedure is `medical_unfitness_exemption_from_military_service` /
التعامل مع إجراءات الإعفاء من الخدمة العسكرية لعدم اللياقة الطبية /
Handle medical-unfitness exemption paperwork. This is a proposal, not a registered identity.

The [production architecture](../../architecture/README.md), accepted ADRs and
[editorial process](../../editorial-process.md) are authoritative. The
[temporary family-exemption pack](../temporary-family-exemption/README.md) remains a historical,
separate scope. The retired prototype is not an implementation target.

The existing family Procedure selector matches `application_location=inside_egypt` alone.
Adding a domestic medical selector would overlap it. Adding Service Questions also changes
stored behavior signatures. Task I02 defines the prerequisite design and regression work;
this research does not authorize changing old signatures, weakening import seals, or silently
rewriting historical selectors.

Accountable human author, independent Arabic/English reviewer, legal/military specialists and
clinical terminology reviewer are **unassigned**. Publication requires the existing independent
review process. The clinical review need does not create a new Django permission or substitute
for legal/military approvals. Reverify operational evidence before any draft import/publication.
No applications, payments, authority contacts or personal medical data were submitted in this research.
