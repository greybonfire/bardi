# Egypt Paperwork Guidance

This glossary defines the shared domain language used by production design, implementation, research, and review. When a short definition here needs more detail, the authoritative documents under `docs/architecture/` and accepted ADRs control.

## Language

**Fact**:  
A typed source circumstance supplied about a person or a status explicitly recorded by an authority. A published Fact key has immutable meaning, type, and allowed values; changed semantics require a new key. Omission is UNKNOWN during value comparison, while invalid/null values are diagnostics.
_Avoid_: Questionnaire answer, eligibility conclusion, UI state

**Derived Fact**:  
A typed value calculated deterministically from other Facts by the pinned rules-contract implementation, such as age or document expiry. Rules consume Derived Facts but do not author arbitrary formulas.
_Avoid_: User assertion, editor-authored script

**Question**:  
A bilingual prompt authored under a Service that resolves one source Fact (or an explicitly declared small set representing the same submitted information). Questions are available before or after Procedure selection. They provide wording and priority; they do not duplicate business-rule visibility logic.
_Avoid_: Procedure-Version-owned rule, eligibility conclusion, custom mapper

**Missing-Fact Picker**:  
The deterministic mechanism that asks the highest-priority Service Question needed to resolve a consequential UNKNOWN rule. If no authored Question covers a consequential source Fact, the knowledge configuration is defective.
_Avoid_: AI interviewer, optimal-question planner

**Applicability Rule**:  
A typed structured predicate over Facts whose result is TRUE, FALSE, or UNKNOWN under strong Kleene logic. Invalid inputs and malformed rules are separate diagnostics, not truth values.
_Avoid_: Script, workflow action, questionnaire logic

**Evaluation Trace**:  
A transient explanation of predicate results and whether each branch affected the final result. It may record non-consequential unknowns, but only consequential unknowns drive Questions. It is not persisted as a general application log or returned in the public plan.
_Avoid_: Application log, error stack, public response

**Service**:  
A stable bilingual grouping of closely related Procedures around a broad administrative objective, such as getting a passport, obtaining a National ID, or handling military paperwork. It is the user entry point and owns the curated Procedure candidate set and Service Questions. It is not a government transaction and does not own Procedure-specific requirements, fees, steps, routing, evidence, or Eligibility Bases.
_Avoid_: Procedure, government transaction, rule bundle

**Procedure**:  
A stable identity for one concrete administrative transaction and output. First passport issuance, ordinary renewal, lost-passport replacement, and damaged-passport replacement are separate Procedures that may belong to the same Service.
_Avoid_: Service, broad paperwork category, status

**Service–Procedure Candidate**:  
The stable membership from a Service to a Procedure plus the typed selection predicate used before a Procedure Version is chosen. It is authored independently from any current Procedure Version so historical or future versions remain reachable.
_Avoid_: Copy of current version applicability

**Procedure Version**:  
A coherent immutable published snapshot of one Procedure's version-specific rules, bilingual guidance, and public provenance. Publication workflow is separate from calculated trust; at most one published version is applicable per Procedure and evaluation date. Withdrawn versions remain available only for explicit historical evaluation.
_Avoid_: Mutable procedure, revision-history row, live evidence overlay

**Eligibility Basis**:  
A version-owned legal or administrative ground on which a person may qualify for a Procedure. Each Basis has a reachability (`applicability`) stage and a required qualification stage. FALSE reachability makes qualification irrelevant for Missing-Fact purposes; UNKNOWN reachability can ask only reachability Facts; TRUE reachability allows qualification Facts to become consequential. Multiple matched Bases remain alternatives rather than recommendations.
_Avoid_: Flat predicate, route ranking, Procedure variant

**Authority**:  
A government body with stable identity and jurisdiction that issues Sources, receives submissions, or makes administrative decisions.
_Avoid_: Service Point, office address, publisher text

**Service Point**:  
A stable physical office or digital destination identity. Time-varying material details belong to a Service Point Version, while Procedure-specific jurisdiction/availability rules belong to Procedure–Service Point Associations.
_Avoid_: Procedure rule, unstructured address

**Service Point Version**:  
A time-bounded snapshot of a Service Point's material details such as address and availability.
_Avoid_: Stable office identity, Procedure-specific routing rule

**Procedure–Service Point Association**:  
A Procedure-Version-owned, evidence-backed relationship to a Service Point Version with its own routing/jurisdiction rule, trust state, and applicability interval.
_Avoid_: Nearest-office ranking, global office eligibility

**Procedure Dependency**:  
A version-owned conditional relationship from one Procedure to a stable target Procedure. Version 1 supports direct blocking prerequisites one level deep; blocking cycles prevent publication.
_Avoid_: Recursive hidden plan, embedded instruction

**Supported Case**:  
A combination of circumstances for which a published Procedure Version can produce reliable guidance. Recognized but unsupported exceptions receive explicit escalation rather than a closest-match plan.
_Avoid_: Every possible case, approximation

**Personalized Plan**:  
A deterministic result assembled for a person's stated Service and current Facts, including the applicable Procedure, prerequisites, checklist, next steps, known limits, and local unresolved information. It identifies its Procedure Version/evaluation freshness and warns the person to regenerate immediately before acting.
_Avoid_: Definitive ruling, canonical database record, generic guide

**Procedural Claim**:  
A reviewable administrative assertion used in guidance, such as a requirement, material step, fee, warning, dependency, or routing condition. Material external assertions carry claim-specific evidence. Presentation-only text that introduces no new administrative assertion does not become a claim solely because it is rendered.
_Avoid_: Page copy, one claim per sentence, unsourced material assertion

**Source**:  
A preserved official publication, secondary source, or contextual Field Report that may support or challenge evidence-bearing material. A Source is stored independently from whether/how its citation is displayed.
_Avoid_: Claim, bibliography entry only, UI marker

**Evidence Link**:  
An internal claim-specific provenance record connecting evidence-bearing material to preserved Sources, including the exact relied-upon passage and retrieval/applicability context. Public presentation may group or progressively disclose sources without mirroring this storage shape.
_Avoid_: Procedure-level bibliography, presentation component

**Evidence Discrepancy**:  
A lightweight internal/admin record of a material conflict, stale evidence, or applicability mismatch relevant to a claim. It records affected material, evidence, status, concise rationale, and optional resolution. It is never a public-plan object; public behavior reflects only its trust/inconclusiveness consequence.
_Avoid_: Public warning, confidence score, generalized evidence graph

**Verification/Trust State**:  
The current editorial/evidence state of material: `current`, `needs_reverification`, `stale`, `disputed`, or `unknown`. It is separate from Procedure-Version publication state.
_Avoid_: Confidence percentage, publication status

**Unverified Claim**:  
Material that cannot currently be asserted as authoritative. `needs_reverification`, disputed, or unknown material is not automatically historical. Only a previously established stale value with its own dating may be shown as dated historical context with current value unknown.
_Avoid_: Current requirement, stale-but-assumed-valid

**Document Type**:  
A stable reusable identity for a requested document/item. Each Procedure Version owns the actual Checklist claim for necessity, quantity, wording, applicability, and evidence.
_Avoid_: Complete requirement, procedure-specific claim

**Checklist Item**:  
An actionable plan item backed by a semantic claim and visibly classified as Official Requirement, Practical Preparation, or other explicit non-current/candidate state.
_Avoid_: Unlabeled requirement

**Official Requirement**:  
A Checklist Item that asserts a government requirement and is supported by current authoritative evidence.
_Avoid_: Tip, Field Report

**Practical Preparation**:  
An item intended to reduce operational failure and supported by contextual Field Guidance, but not established as government-mandated.
_Avoid_: Official requirement, guarantee

**Fee**:  
A structured monetary claim with currency, applicability, evidence, and explicit value state: known, range, unknown, or unverified. Unknown means no current amount is asserted.
_Avoid_: Invented estimate, platform price

**Field Report**:  
A person's contextual report of what occurred during an attempt. A report without adequate date/place context is only an internal research lead and cannot support public Field Guidance.
_Avoid_: Official Source, verified rule

**Field Guidance**:  
Clearly labeled practical information supported by moderated, sufficiently recent/contextual Field Reports but not established as an Official Requirement.
_Avoid_: Official requirement, guarantee

**Anonymous Case**:  
A transient current set of source Facts evaluated to produce a result without becoming a User Profile or saved administrative record. Version 1 does not persist raw case Facts server-side.
_Avoid_: Saved case, deidentified Fact warehouse

**Contradictory Case**:  
A set of submitted Facts that cannot coherently describe one case. It is invalid rather than UNKNOWN and identifies the conflicting source Facts for correction.
_Avoid_: Incomplete case, closest match

**Successful Attempt**:  
An attempt in which a person follows a Personalized Plan and reaches the intended government service without a preventable missing requirement in the Plan.
_Avoid_: Procedure completion guarantee, questionnaire completion
