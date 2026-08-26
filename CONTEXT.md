# Egypt Paperwork Guidance

This context describes how the platform organizes Egyptian administrative Procedures and produces sourced, personalized guidance from a person's current circumstances.

## Language

**Fact**:
A raw circumstance supplied about a person or a status explicitly recorded by an authority. A published Fact key has immutable meaning, type, and allowed values; changed semantics require a new key.
_Avoid_: Questionnaire answer, eligibility conclusion, UI state

**Derived Fact**:
A typed value calculated deterministically from other Facts, such as age or document expiry. Rules consume Derived Facts but do not calculate them.
_Avoid_: User assertion, arbitrary formula

**Question**:
A bilingual prompt owned by a Procedure Version that writes exactly one source Fact. Questions may be grouped on a screen, but they do not contain procedural conclusions or custom Fact-mapping logic.
_Avoid_: Fact, rule, compound mapper

**Missing-Fact Picker**:
The deterministic mechanism that asks the highest-priority applicable Question needed to resolve a consequential unknown rule. If no such Question exists, the case is inconclusive and the knowledge configuration is defective.
_Avoid_: AI interviewer, optimal question planner

**Applicability Rule**:
A typed, structured predicate over Facts whose result is TRUE, FALSE, or UNKNOWN under strong Kleene logic. Invalid inputs and malformed rules are separate diagnostics, not truth values.
_Avoid_: Script, workflow action, questionnaire logic

**Evaluation Trace**:
The explanation of each predicate result and whether it affected the final result. It may record non-consequential unknowns, but only consequential unknowns drive Questions.
_Avoid_: Application log, error stack

**Goal**:
A stable, bilingual grouping of closely related Procedures around a broad administrative objective, such as getting a passport, obtaining a National ID, or handling military paperwork. A Goal is primarily an organizational and user-entry concept: it keeps a large Procedure catalog navigable and identifies the curated Procedures that may achieve the objective. It is not itself a government transaction and does not own procedure-specific requirements, fees, steps, routing rules, or evidence.
_Avoid_: Procedure, government transaction, rule set

**Procedure**:
A distinct administrative transaction performed with an authority for a defined output and one concrete way of reaching a Goal. First passport issuance, ordinary passport renewal, lost-passport replacement, and damaged-passport replacement are separate Procedures that may all belong to the same passport Goal.
_Avoid_: Goal, broad paperwork category, status, procedure variant

**Procedure Version**:
A coherent, published snapshot of one Procedure's rules, bilingual guidance, and public provenance. Publication workflow is separate from calculated trust; one version is applicable per Procedure and date, and withdrawn versions remain available only for explicit historical evaluation.
_Avoid_: Revision history, mutable procedure, live evidence overlay

**Eligibility Basis**:
A legal or administrative ground on which a person qualifies for a Procedure, such as an only-son basis for military exemption. A matched Basis contributes its own Procedural Claims in addition to shared Procedure claims.
_Avoid_: Route, channel, procedure variant

**Authority**:
A government body with stable identity and jurisdiction that issues Sources, receives submissions, or makes administrative decisions.
_Avoid_: Service point, office address, source publisher text

**Service Point**:
A verified physical office or digital destination at which a Procedure is available. It has stable identity and location context so guidance and Field Reports can refer to the same place.
_Avoid_: Procedure Channel, unstructured address

**Procedure Dependency**:
A versioned, conditional relationship from one Procedure to a stable target Procedure. The initial relation vocabulary is fixture-driven; cycles among blocking prerequisites prevent publication.
_Avoid_: Embedded instruction, recursive plan

**Supported Case**:
A combination of circumstances for which a published Procedure Version can produce reliable guidance. Recognized but unsupported exceptions receive explicit escalation rather than a best-match plan.
_Avoid_: Every possible case, closest match

**Personalized Plan**:
Guidance assembled for a person's stated Goal and current circumstances, including the applicable Procedure, prerequisites, checklist, next steps, known limits, and unresolved questions. It identifies when it was generated and warns the person to regenerate it immediately before acting.
_Avoid_: Definitive ruling, generic guide, future-dated plan

**Procedural Claim**:
A reviewable administrative assertion used in personalized guidance, such as a requirement, material step, fee, warning, dependency, or routing condition. Claims that materially tell a person what the government requires, permits, charges, accepts, or where/when to act carry claim-level provenance. Derived explanations, Question wording, UI grouping, product warnings, and other presentation that introduce no new administrative assertion do not require a separate Evidence Link.
_Avoid_: Page copy, one claim per rendered sentence, unsourced material administrative assertion

**Source**:
A preserved government publication or contextual Field Report that may support or challenge one or more evidence-bearing Procedural Claims. A Source is stored independently from how or whether its citation is displayed to a user.
_Avoid_: Claim, citation list, UI citation marker

**Evidence Link**:
The internal claim-specific provenance record connecting an evidence-bearing Procedural Claim to a Source, including the exact relied-upon passage and retrieval/applicability context. Evidence attaches to the semantic claim rather than every sentence rendered from it. Public presentation may group or progressively disclose sources without changing the stored provenance.
_Avoid_: Procedure-level source list, one citation per sentence, presentation component

**Unverified Claim**:
A previously supported Procedural Claim whose current truth can no longer be asserted, such as a fee beyond its review interval. A Personalized Plan may show it only as dated context, not as current guidance.
_Avoid_: Current requirement, stale-but-valid

**Document Type**:
A stable identity for a requested document or item, such as an Egyptian passport, National ID, family registration, or photograph. It is reusable vocabulary only; each Procedure Version defines its own Checklist Item claim for quantity, necessity, applicability, wording, and evidence when the item asserts a material administrative requirement.
_Avoid_: Complete requirement, procedure-specific document claim

**Checklist Item**:
An actionable item shown in the Personalized Plan. Each item is visibly classified as an Official Requirement or Practical Preparation.
_Avoid_: Unlabeled requirement

**Official Requirement**:
A Checklist Item that asserts a government requirement and is supported by current authoritative evidence.
_Avoid_: Tip, field report

**Practical Preparation**:
A Checklist Item recommended to avoid a preventable operational failure and supported by contextual Field Guidance, but not established as government-mandated.
_Avoid_: Official requirement, guarantee

**Fee**:
A structured monetary Procedural Claim with amount or range, currency, type, applicability, effective interval, evidence, and an explicit unknown or unverified state when necessary.
_Avoid_: Estimate, platform price

**Field Report**:
A person's report of what occurred during an attempt. A report without enough date and place context may inform internal research but cannot support public guidance.
_Avoid_: Official source, verified guidance

**Field Guidance**:
Clearly labeled practical information supported by moderated, recent, contextual Field Reports but not established as an Official Requirement.
_Avoid_: Official requirement, guarantee

**Evidence Discrepancy**:
A lightweight internal/admin record of a material conflict, applicability mismatch, or unresolved difference among Sources or Evidence Links relevant to a claim. It stores only the evidence involved, status, concise research rationale, and resolution when one exists. It is never a public-plan object; public guidance reflects its consequence through claim verification state, local inconclusiveness, or a simple user-appropriate explanation.
_Avoid_: Public warning, confidence score, hidden source override, editorial essay

**Anonymous Case**:
A transient set of Facts evaluated to produce a Personalized Plan without becoming a User Profile or saved administrative record.
_Avoid_: User profile, saved case, deidentified fact set

**Contradictory Case**:
A set of Facts that cannot coherently describe one case. It is invalid rather than unknown and must identify the conflicting Facts for correction.
_Avoid_: Unknown case, best match

**Successful Attempt**:
An attempt in which a person follows a Personalized Plan and reaches the intended government service without a preventable missing requirement in the Plan.
_Avoid_: Procedure completion, questionnaire completion
