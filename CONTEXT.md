# Egypt Paperwork Guidance

Shared domain language for sourced, bilingual Egyptian administrative guidance. Detailed contracts live in the [architecture guide](docs/architecture/README.md); [accepted ADRs](docs/adr/README.md) record architectural decisions.

## Language

**Fact**:  
A typed source circumstance about a person or a status explicitly recorded by an authority.
_Avoid_: Questionnaire answer, eligibility conclusion, UI state

**Derived Fact**:  
A typed value calculated deterministically from other Facts, such as age or document expiry.
_Avoid_: User assertion, editor-authored script

**Question**:  
A bilingual Service-owned prompt for source Facts, available before or after Procedure selection; wording is distinct from the rules that make those Facts consequential.
_Avoid_: Procedure-Version-owned rule, eligibility conclusion, custom mapper

**Missing-Fact Picker**:  
The deterministic selector of the next authored Question needed to resolve consequential missing information.
_Avoid_: AI interviewer, optimal-question planner

**Applicability Rule**:  
A typed predicate over Facts with a TRUE, FALSE, or UNKNOWN result; invalid input is distinct from uncertainty.
_Avoid_: Script, workflow action, questionnaire logic

**Evaluation Trace**:  
A transient explanation of predicate results and which branches affected the result.
_Avoid_: Application log, error stack, public response

**Service / خدمة**:
A stable bilingual user-entry grouping of related Procedures around a broad administrative objective, with shared Questions and a curated candidate set. Historical research calls this a **Goal**; it is not a concrete transaction or destination.
_Avoid_: Goal in current production terminology, Procedure, Service Point, rule bundle

**Procedure**:  
A stable identity for one concrete administrative transaction and output, such as first passport issuance, renewal, or lost-passport replacement.
_Avoid_: Service, broad paperwork category, status

**Service–Procedure Candidate**:  
Membership of a Procedure in a Service, with its selection condition distinct from version-specific applicability.
_Avoid_: Copy of current version applicability

**Procedure Version**:  
A coherent immutable published snapshot of one Procedure's rules, bilingual guidance, and public provenance; publication state is distinct from evidence trust.
_Avoid_: Mutable procedure, revision-history row, live evidence overlay

**Eligibility Basis**:  
A version-owned legal or administrative qualification ground with separate reachability and qualification stages. Matched Bases are alternatives, not recommendations or authoritative decisions.
_Avoid_: Flat predicate, route ranking, Procedure variant

**Authority**:  
A government body with stable identity and jurisdiction, distinct from its offices.
_Avoid_: Service Point, office address, publisher text

**Service Point**:  
A stable physical office or digital destination identity, distinct from its changing material details and Procedure-specific routing conditions.
_Avoid_: Procedure rule, unstructured address

**Service Point Version**:  
A time-bounded snapshot of a Service Point's material details, such as address and availability.
_Avoid_: Stable office identity, Procedure-specific routing rule

**Procedure–Service Point Association**:  
A Procedure-Version-owned, evidence-backed relationship to a Service Point Version, with its own routing/jurisdiction condition, trust, and applicability interval.
_Avoid_: Nearest-office ranking, global office eligibility

**Procedure Dependency**:  
A version-owned conditional relationship to a stable target Procedure, such as a blocking prerequisite.
_Avoid_: Recursive hidden plan, embedded instruction

**Supported Case**:  
Circumstances for which a published Procedure Version can produce reliable guidance, distinct from recognized but unsupported exceptions requiring escalation.
_Avoid_: Every possible case, approximation

**Personalized Plan**:  
A deterministic, version- and date-specific result for a person's Service and current Facts, including prerequisites, checklist, next steps, limits, and unresolved information.
_Avoid_: Definitive ruling, canonical database record, generic guide

**Procedural Claim**:  
A reviewable administrative assertion used in guidance, distinct from presentation text that introduces no new external assertion.
_Avoid_: Page copy, one claim per sentence, unsourced material assertion

**Source**:  
A preserved official publication, secondary source, or contextual Field Report that may support or challenge a claim, independently of citation presentation.
_Avoid_: Claim, bibliography entry only, UI marker

**Evidence Link**:  
Internal claim-specific provenance connecting evidence-bearing material to preserved Sources, with the relied-upon passage and retrieval/applicability context.
_Avoid_: Procedure-level bibliography, presentation component

**Evidence Discrepancy**:  
An internal editorial record of conflicting, stale, or wrong-applicability evidence and its disposition, distinct from the resulting public uncertainty.
_Avoid_: Public warning, confidence score, generalized evidence graph

**Verification/Trust State**:  
The evidence state of material: current, needs re-verification, stale, disputed, or unknown; distinct from publication state.
_Avoid_: Confidence percentage, publication status

**Unverified Claim**:  
Material that cannot currently be asserted as authoritative. Unverified material is not necessarily established historical context.
_Avoid_: Current requirement, stale-but-assumed-valid

**Document Type**:  
A reusable document/item identity, distinct from a Procedure Version's claim about its necessity, quantity, or applicability.
_Avoid_: Complete requirement, procedure-specific claim

**Checklist Item**:  
An actionable claim-backed plan item classified as an Official Requirement, Practical Preparation, or explicit non-current/candidate material.
_Avoid_: Unlabeled requirement

**Official Requirement**:  
A Checklist Item asserting a government requirement supported by current authoritative evidence.
_Avoid_: Tip, Field Report

**Practical Preparation**:  
An item intended to reduce operational failure, supported by contextual Field Guidance but not established as government-mandated.
_Avoid_: Official requirement, guarantee

**Step**:
An ordered bilingual action for a Procedure Version or Eligibility Basis; a material administrative action is a Procedural Claim.
_Avoid_: Mutable workflow state, unsourced administrative instruction

**Warning**:
A version-owned bilingual caution, either an evidence-bearing administrative assertion or product safety/limitation wording without a new external assertion.
_Avoid_: Evidence discrepancy, undifferentiated disclaimer

**Fee**:  
A monetary claim with currency, applicability, evidence, and a known, range, unknown, or unverified value state; unknown asserts no current amount.
_Avoid_: Invented estimate, platform price

**Field Report**:  
A person's contextual account of an attempt; without adequate date/place context it is only a research lead.
_Avoid_: Official Source, verified rule

**Field Guidance**:  
Labeled practical information supported by moderated, sufficiently recent/contextual Field Reports, not established as an Official Requirement.
_Avoid_: Official requirement, guarantee

**Anonymous Case**:  
A transient set of source Facts supplied for evaluation, not a User Profile or saved administrative record.
_Avoid_: Saved case, deidentified Fact warehouse

**Contradictory Case**:  
Submitted Facts that cannot coherently describe one case, distinct from incomplete information.
_Avoid_: Incomplete case, closest match

**Successful Attempt**:  
An attempt in which a person follows a Personalized Plan and reaches the intended government service without a preventable missing requirement in the Plan.
_Avoid_: Procedure completion guarantee, questionnaire completion
