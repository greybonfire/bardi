# Production domain model

**Status:** Authoritative  
**Effective:** 2026-09-01

This document defines semantic ownership and identity. It is not a literal Django-model checklist: some concepts are relational records, some are JSON rule values, and some deliberately remain transient.

## Stable identities

### Service

A stable bilingual user-entry grouping of closely related Procedures around one broad administrative objective. A Service owns catalog/navigation membership, authored Questions, and contradiction/case-invariant definitions used while planning that Service. It does not own Procedure-specific requirements, fees, steps, routing, evidence, or legal Bases.

### Procedure

A stable identity for one concrete administrative transaction and output. A Procedure belongs to one primary Service in version 1. Meaning-changing guidance is not edited directly on the Procedure; it lives in immutable Procedure Versions.

### Service–Procedure candidate

The stable membership from a Service to a Procedure includes the Service-level typed selection predicate used before a concrete Procedure Version is chosen. This selector must not be copied from the current Procedure Version. A historical/future version must remain reachable even when its version-specific applicability differs from today's version.

### Fact definition

A stable typed vocabulary entry. A published Fact key never changes meaning, type, enum vocabulary, or source/derived role. Changed semantics require a new key.

Source Facts are supplied by the caller. Derived Facts are computed deterministically by code owned by the pinned rules-contract implementation; version 1 does not store arbitrary editor-authored derivation scripts.

### Question

A bilingual Service-owned prompt that resolves one source Fact (or an explicitly declared small set when one answer deterministically supplies the same source information). Question wording contains no administrative conclusion. Questions are available before Procedure selection, so they are not owned exclusively by a Procedure Version.

The Missing-Fact Picker determines whether a Question is needed; Question records do not duplicate business-rule visibility conditions.

### Contradiction / case invariant

A Service-owned catalog rule that identifies a combination of circumstances that cannot coherently describe one case. It has a stable identifier, the source-Fact keys that should be named in a public correction diagnostic, and a validated typed predicate that becomes invalid only when it evaluates TRUE.

Contradiction definitions live at Service level because they may reject an incoherent case before a concrete Procedure has been selected. They are not Procedure-Version guidance and do not create administrative conclusions.

UNKNOWN contradiction conditions do not drive the Missing-Fact Picker. A contradiction check only rejects an already-submitted case when the invariant is established as TRUE; missing information remains ordinary UNKNOWN planning input.

### Authority

A stable government-body identity used to distinguish issuing, deciding, publishing, or receiving institutions from individual offices.

### Document Type

Reusable identity for a document/item only. Requirement status, quantity, wording, applicability, and evidence belong to the Procedure-Version claim that asks for it.

### Service Point

Stable identity for a physical office or digital destination. Mutable/material details are versioned separately.

### Source

A preserved official publication, secondary source, or contextual Field Report. Sources are reusable evidence records and retain retrieval/publication/observation context; they are not themselves claims.

## Procedure Version: immutable semantic snapshot

A Procedure Version is the publication unit for one Procedure. Once published, its public meaning is immutable. Meaning-changing edits are made in a draft successor and published as a new coherent version.

A Procedure Version owns or snapshots the following semantic material:

- version-specific Procedure applicability;
- checklist/Procedural Claims;
- Steps;
- Fees;
- Warnings;
- Eligibility Bases;
- direct Procedure Dependencies;
- Procedure–Service Point associations;
- Evidence Links for its evidence-bearing material;
- bilingual public text required to render the version;
- rules-contract version and temporal/publication metadata.

Stable child keys may be reused across versions to express semantic continuity, but the version-owned records themselves are not mutated in place after publication.

## Eligibility Basis

An Eligibility Basis is a version-owned legal/administrative qualification ground. It has two separate rule stages:

1. **reachability (`applicability`)** — whether the Basis remains relevant enough to investigate for this case;
2. **qualification** — whether a reachable case actually matches the Basis.

Qualification is required. Reachability may be absent, meaning always reachable.

Evaluation must obey the stage boundary:

- FALSE reachability: the Basis is unreachable; qualification is not evaluated for Missing-Fact purposes;
- UNKNOWN reachability: only Facts needed to resolve reachability may become Questions;
- TRUE reachability: qualification may be evaluated and its consequential missing Facts may become Questions.

Therefore a Fact used only by an unreachable Basis can never become a user Question.

Matched Bases are alternatives, not rankings or authoritative decisions. Untrusted `needs_reverification` Bases may remain visible as candidate matches but cannot unlock Basis-scoped current guidance.

## Procedural claims and plan material

Evidence-bearing administrative assertions remain separate semantic records even when the UI groups them.

### Checklist claim

Represents an Official Requirement, Practical Preparation, or explicitly unverified/candidate material. It may reference a Document Type while owning its own quantity, applicability, scope, wording, evidence, and verification state.

### Step

A material action with deterministic phase/order metadata, applicability, scope, evidence, and trust state.

### Fee

A structured monetary claim with currency and explicit value state: known, range, unknown, or unverified. Unknown means no current amount is asserted.

### Warning

Administrative or product limitation text. Only material external administrative assertions require evidence; product safety wording does not become a claim solely because it is rendered.

### Procedure Dependency

A direct version-owned edge to a stable target Procedure. Version 1 supports the fixture-proven `blocking_prerequisite` relation and evaluates only one edge deep. Blocking cycles are invalid knowledge.

## Service Point model

Service routing uses three layers:

1. `ServicePoint` — stable destination identity;
2. `ServicePointVersion` — time-bounded material details such as address/availability;
3. `ProcedureServicePointAssociation` — Procedure-Version-specific availability/jurisdiction rule connecting the Procedure Version to a Service Point Version.

A rule about who may use an office belongs to the Procedure association, not to the Service Point identity. Routing may resolve zero, one, or multiple points and remains locally inconclusive when necessary.

## Evidence, discrepancy, and trust

### Evidence Link

Internal claim-specific provenance connecting one evidence-bearing item to one or more preserved Sources, including the exact relied-upon passage and retrieval/applicability context.

### Evidence Discrepancy

Lightweight internal/editorial record of conflicting, stale, or wrong-applicability evidence. It records the affected claim, evidence, concise rationale, status, and optional resolution. It is not a public plan object and must not evolve into a generalized evidence graph in version 1.

### Publication state vs trust state

Publication lifecycle (`draft`, `published`, `withdrawn`) is separate from calculated trust (`current`, `needs_reverification`, `stale`, `disputed`, `unknown`). A published version can contain locally untrusted material; that does not automatically invalidate unrelated trusted guidance.

## Steps, Warnings, and claim provenance

Steps and Warnings are immutable Procedure-Version-owned bilingual guidance. Steps have stable per-version IDs, phases, deterministic `(phase_order, slot, semantic_id)` ordering, applicability, temporal trust, and procedure or Eligibility-Basis scope. `EligibilityBasis` is presently only a relational scope anchor; qualification is intentionally deferred. Basis Steps fail closed unless matched Basis IDs are supplied.

Warnings use deterministic `(display_order, semantic_id)` ordering. Administrative warnings make external assertions and require claim evidence. Product safety, regeneration, and limitation wording is presentation policy and must not carry Evidence Links. Every Evidence Link has exactly one Checklist Item, Step, or Warning owner; shared Sources and Authorities remain preserved provenance.

## Transient concepts that are not persistence requirements

### Anonymous Case / current Facts

The current source-Fact set is request/session input. Version 1 does not persist it as a server-side Case or Profile.

### Derived Facts

Computed per evaluation. They may appear in traces/tests but do not require case persistence.

### Evaluation Trace

Transient diagnostic tree used by tests/editor inspection. It is not an ORM model, audit log, or public API response.

### Personalized Plan

A deterministic projection/result DTO assembled from a Procedure Version and current Facts. It is not a canonical knowledge record and need not be persisted to evaluate a case.

## Relational vs JSON boundary

Relational storage is preferred for identities, version-owned claims, evidence, relationships, temporal metadata, review state, and objects that editors need to query or validate individually.

Typed predicate ASTs are stored as validated JSONB values owned by their semantic record. Rule nodes are not normalized into generic database rows, and executable Python/JavaScript expressions are forbidden as authored rules.
