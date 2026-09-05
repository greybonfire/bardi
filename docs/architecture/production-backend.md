# Production backend architecture

**Status:** Authoritative  
**Effective:** 2026-09-01

## Purpose

Build a maintainable production backend for sourced, bilingual Egyptian administrative guidance without losing the determinism, evidence discipline, local uncertainty, and privacy boundaries proven by the prototype.

The first production system is a **Django/PostgreSQL modular monolith**. Django Admin is the initial research/editorial interface. Django Ninja exposes a small application interface to a separate Next.js web client.

## System boundary

```text
Next.js web application
        |
        | Django Ninja HTTP interface
        v
Django application layer
        |
        +--> planning application service --> pure planning domain
        |
        +--> knowledge/publication services --> PostgreSQL
        |
Django Admin --> research/review/publication services
```

The PostgreSQL/ORM layer stores authored knowledge and publication/audit state. The planning domain evaluates an immutable in-memory snapshot and must not query the ORM while evaluating rules.

## Logical backend modules

The exact Python package layout may evolve, but these ownership boundaries are authoritative:

### Knowledge

Owns persisted domain knowledge: Services, Procedures, Procedure Versions, Fact definitions, authored Questions, claims, Eligibility Bases, Sources/Evidence Links, Service Points, dependencies, and related stable identities.

### Publication

Owns draft lifecycle, validation, review/approval records, atomic publication, withdrawal, re-verification workflow, and creation of immutable published snapshots. Publishing is a service operation, not a casual model-field edit.

### Planning

Owns typed Facts, derivations, rules-contract implementations, three-valued evaluation, consequential-unknown selection, Procedure and Procedure-Version resolution, Basis evaluation, plan assembly, trust application, and public planning result DTOs. Its core evaluation code remains independent of Django models and request objects.

### API

Owns authentication/authorization boundaries for public and staff endpoints, request validation, application-service calls, and stable response schemas. It does not contain administrative rule semantics.

## Request-time planning flow

1. Validate source Facts against immutable Fact definitions; null and invalid types are errors, not UNKNOWN.
2. Derive deterministic Facts using the pinned rules-contract implementation.
3. Evaluate Service-owned cross-Fact contradictions and reject only TRUE invariants; UNKNOWN contradiction branches do not feed Question routing.
4. Select a concrete Procedure from the requested Service's curated candidate set.
5. Resolve the applicable immutable published Procedure Version for the evaluation date.
6. Evaluate the Procedure Version and its Eligibility Bases using the rules contract.
7. Ask the deterministic next consequential Question, or assemble the reliable portions of the Personalized Plan.
8. Apply evidence/trust consequences locally; routing uncertainty or one stale claim must not erase unrelated reliable guidance.
9. Return one discriminated public result: next Question, plan, inconclusive result, or invalid diagnostics.

No server-side Anonymous Case record is required for this flow.

## Persistence strategy

PostgreSQL is the source of truth for production knowledge.

- Stable semantic identities and evidence-bearing/version-owned claims are relational records.
- Typed rule ASTs are schema-validated JSONB, not executable code and not normalized node tables.
- Published Procedure Versions are immutable semantic snapshots.
- Sources are preserved reusable records; Evidence Links remain claim-specific.
- Evidence Discrepancies are lightweight internal/editorial records and are not public plan objects.
- Service Point identity, versioned material details, and Procedure-specific routing associations remain separate records.

The production schema must be designed from the domain model rather than copied from prototype dataclasses.

## Public application interface

Version 1 exposes `GET /v1/services` and `POST /v1/planning`; the exact contract is in [`../api/v1.md`](../api/v1.md). Navigation includes only explicitly active Services (`Service.is_active` is the sole activation criterion) and bilingual titles. Planning consumes the caller's current source Facts, exact locale, and calendar evaluation date without a persisted Case. One complete read-only, repeatable-read PostgreSQL snapshot is materialized before pure planning starts.

The four public discriminators are `next_question`, `plan`, `inconclusive`, and `invalid`. Deterministic Fact derivation and contradiction rejection always precede Procedure selection, version resolution, version applicability, and Checklist Item assembly. A resolved applicable version returns a plan containing only factually applicable material permitted by shared trust/freshness semantics. Clients receive compact Source/freshness metadata but no rule ASTs, raw Facts, Evidence Links, internal discrepancies or rationale, publication actors, or Evaluation Traces.

The web client keeps in-progress answers client-side and resubmits the current Fact set. A future saved-profile feature requires a separate privacy/product decision; it is not part of the initial backend contract. The first deployment assumes same-origin or reverse-proxied Next.js; cross-origin CORS policy is a separate deployment decision.

## Privacy and observability

- Do not persist raw Anonymous Case Facts in version 1.
- Do not log request bodies containing raw Facts.
- The application logging boundary recognizes the planning route across API and Django
  request/server/security logging. It removes request objects, exceptions, stacks, and custom
  record attributes before configured output. The only permitted fields are HTTP method, the
  fixed `/v1/planning` route, HTTP status, and a coarse error code.
- Do not expose raw Facts, Fact keys, bodies, planning DTOs, prepared Facts, predicates,
  Evaluation Traces, selection results, or exception details in logs, traces, error reporting,
  analytics payloads, APM, or any third-party observability integration.
- No planning analytics or metrics are currently emitted. A future integration must build
  events only from the same explicit coarse allow-list; merely redacting known sensitive keys
  from a richer object is not sufficient.
- Evaluation Traces are transient editor/test diagnostics, not public responses or general application logs.
- Deployment ingress, reverse-proxy, platform access logging, and tracing are outside the
  application boundary and must be configured not to capture planning request bodies. The
  application filter is not a substitute for that deployment control.
- No document upload or implied document verification is required by the core planning flow.

## Initial infrastructure constraints

Keep the first production deployment operationally simple.

- PostgreSQL is required; no separate cache, search engine, message broker, or workflow engine is required initially.
- Do not introduce a mandatory paid SaaS dependency for core application behavior in the initial release.
- Use Django's built-in authentication/authorization for staff/admin unless a demonstrated requirement justifies another system.
- Background work should be introduced only for concrete needs such as scheduled re-verification or notifications; publication itself remains a synchronous transactional operation.
- Deployment provider and production topology are intentionally not fixed by this document. They should be chosen when the deployable Django/Next.js applications exist.

## Testing strategy

Production tests replace prototype implementation tests over time, but the prototype remains a reference during parity work.

The backend requires:

- pure unit tests for rule/derivation/planning semantics without a database;
- model/constraint tests for persistence invariants;
- publication integration tests covering validation and atomic state transitions;
- API contract tests for public discriminated results;
- acceptance tests ported from the three researched prototype Procedure families, including exact temporal and conditional-question edges;
- privacy tests that ensure raw Facts do not enter persistent/logged structures.

A production implementation is not considered semantically complete merely because its ORM and endpoints work; it must reproduce the intended planning behavior captured by the authoritative rules contract and acceptance scenarios.

## Explicit exclusions for the first backend milestone

- microservices;
- event sourcing;
- generalized workflow/BPM infrastructure;
- recursive automatic planning of Procedure dependencies;
- user profiles or saved administrative cases;
- document upload/verification;
- AI-authored rules or automatic legal determinations;
- a generalized evidence knowledge graph;
- mandatory Redis/Celery/search infrastructure before a demonstrated need.

## Detached routing materialization

The repeatable-read knowledge adapter eagerly loads published/withdrawn associations, their
stable points and material versions, and both evidence/provenance graphs into immutable planning
snapshots. Rules decode only against published Fact definitions; malformed ownership, rules,
references, material, or required evidence fail closed with sanitized catalog diagnostics. No
ORM model, QuerySet, related manager, or lazy relation crosses into planning. The pure selector
evaluates every association and performs no I/O, geospatial lookup, distance calculation, or
ranking.
