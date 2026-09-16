# Production backend architecture

**Status:** Authoritative  
**Effective:** 2026-09-01

## Purpose

Build a maintainable production backend for sourced, bilingual Egyptian administrative guidance without losing the determinism, evidence discipline, local uncertainty, and privacy boundaries established during the research-prototype phase.

The first production system is a **Django/PostgreSQL modular monolith**. Django Admin is the initial research/editorial interface. Django Ninja exposes a small application interface to a separate Next.js web client.

## System boundary

```text
Browser: bilingual pages and tab-scoped Anonymous Case
        |
        | same-origin public HTTP interface
        v
Next.js web application (pages and public API route handlers)
        |
        | fixed Django Ninja endpoints; server-only upstream origin
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

### Draft authoring transport

`knowledge.draft_packs` owns the strict versioned JSON parser, relational mapping, atomic
import/dry-run, coherent pack export and distinct non-importable vocabulary context; Django
management commands are thin adapters. See
[ADR 0020](../adr/0020-use-versioned-draft-pack-authoring-contract.md) and the
[operator contract](../draft-packs/README.md). This is staff-only knowledge authoring, not a new
public HTTP/API boundary or an opaque JSON persistence model. External-LLM preparation is
untrusted research assistance, not runtime inference, automatic ingestion or verification.

The service reloads a persisted active staff actor and checks version add/change or export view
permissions, plus add permissions for new shared catalog/setup rows. Updates require an explicit
draft target and complete-live-state fingerprint; shared definitions are compare-only. Initial
Questions/selection/contradictions may only accompany a Service created in that transaction,
never modify an existing Service even inactive. New Services/Facts remain inactive/unpublished.

Ordinary writers do not uniformly lock the owning version, so a fixed allowlist of knowledge
tables is locked in `SHARE ROW EXCLUSIVE NOWAIT` mode for imports and coherent exports. Ordinary
reads continue; writers may wait while authoring transactions hold locks. A local 750 ms
implicit-lock timeout covers outermost commit but does not bound total operation duration.
Nonblocking knowledge-row key-share locks and a fresh actor lock protect deferred foreign-key
checks; nested calls retain locks until the caller's transaction ends, so callers must keep it
short. Conflicts return retryable `concurrent_edit`. Conservative fingerprints include shared/global state, relevant dependency
aggregates, trust, seals and workflow/review/audit history. A per-version internal hash receipt
proves exact unchanged last-request retries; no raw uploaded packs are stored. This intentionally
trades concurrency for MVP correctness against existing model/Admin writes.

### Publication

Owns draft lifecycle, validation, review/approval records, atomic publication, withdrawal, re-verification workflow, and creation of immutable published snapshots. Publishing is a service operation, not a casual model-field edit.

[ADR 0019](../adr/0019-use-explicit-solo-and-independent-publication-review-modes.md) defines the
deployment-wide environment variable/Django setting `PROCEDURE_VERSION_REVIEW_MODE`: exactly
`solo` or `independent` (default), invalid values fail closed. It replaces the unsupported
`PROCEDURE_VERSION_REVIEWS_REQUIRED` toggle. Solo skips mandatory general approvals, permitting
one accountable author/publisher with existing permissions. Independent requires the applicable
fresh general approvals independent of author and publisher. Both require truthful Review Policy
risk flags and fresh, eligible specialist approvals distinct from author and publisher for each
configured risk; all other publication gates remain mandatory. Publish audits record applied mode
and only actual eligible approvals consumed by it. Legacy events and withdrawal rows retain
null/unrecorded mode; future mode changes never rewrite history or snapshots.

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

The production schema must be designed from the domain model rather than copied from historical prototype dataclasses.

## Public application interface

Version 1 exposes `GET /v1/services` and `POST /v1/planning`; the exact contract is in [`../api/v1.md`](../api/v1.md). Navigation includes only explicitly active Services (`Service.is_active` is the sole activation criterion) and bilingual titles. Planning consumes the caller's current source Facts, exact locale, and calendar evaluation date without a persisted Case. One complete read-only, repeatable-read PostgreSQL snapshot is materialized before pure planning starts.

The four public discriminators are `next_question`, `plan`, `inconclusive`, and `invalid`. Deterministic Fact derivation and contradiction rejection always precede Procedure selection, version resolution, version applicability, and Checklist Item assembly. A resolved applicable version returns a plan containing only factually applicable material permitted by shared trust/freshness semantics. Clients receive compact Source/freshness metadata but no rule ASTs, raw Facts, Evidence Links, internal discrepancies or rationale, publication actors, or Evaluation Traces.

The web client keeps in-progress answers client-side and resubmits the current Fact set. A future saved-profile feature requires a separate privacy/product decision; it is not part of the initial backend contract. The first deployment assumes same-origin or reverse-proxied Next.js; cross-origin CORS policy is a separate deployment decision.

## Next.js web boundary

The application under `frontend/` implements the client seam accepted in
[ADR 0004](../adr/0004-do-not-persist-case-facts.md),
[ADR 0005](../adr/0005-use-nextjs-with-django-ninja.md) and
[ADR 0006](../adr/0006-expose-one-stateless-planning-operation.md). It owns Arabic-default
RTL and English LTR pages, public Service navigation/introduction pages, SEO metadata, the
interactive questionnaire and presentation/printing of every public planning result. It
does not implement administrative rules, infer eligibility, rank Bases/offices, recursively
plan dependencies or replace unknown guidance with a closest match.

Navigation is loaded from the active-Service API, never a bundled fake catalog. Authored
knowledge enters through manual Admin authoring, existing deterministic draft imports or the
generic draft-pack CLI, followed by deployment-mode review and canonical publish as separate
operations. PR2 adds no Admin pack-upload/preview screen; that remains PR3 work. Service
activation remains explicit and independent of publication. Empty navigation and unavailable services remain honest states, not demo
fallbacks.

### Same-origin transport

The browser uses only `GET /v1/services` and `POST /v1/planning` for the public application
interface. Next's Node route handlers proxy those exact operations; the server-rendered
Service loader uses the same validated upstream client directly. There is no generic URL
proxy or proxy for Django Admin, authentication, health or authoring endpoints.

- `BARDI_API_ORIGIN` is a server-only HTTP(S) origin and must be configured for production
  API access. Credentials, queries, fragments and non-root paths are rejected. It must
  never be exposed through a `NEXT_PUBLIC_` variable. Missing/invalid configuration fails
  closed; only development has an unconfigured localhost fallback.
- `BARDI_SITE_ORIGIN` is the exact trusted public origin for browser POST validation as
  well as canonical/alternate-language and sitemap/robots URLs. Planning fails closed if
  it is absent/invalid outside development. It accepts no trailing slash, path, credentials,
  query or fragment; listener and forwarded host/scheme metadata are not trust anchors.
  Hosting must set the actual public site origin; the implementation otherwise falls back
  to `http://localhost:3000`. This does not select or invent a production domain.
- Fetches omit credentials and use `no-store` with no referrer. Next constructs fixed
  upstream paths and headers; it forwards no incoming query, cookie, authorization,
  request ID, forwarded request headers or browser IP. Upstream redirects are not followed.
- Planning request streams are bounded to 512 KiB (524,288 bytes), including absent or
  understated `Content-Length`. A 10-second deadline covers request reads, upstream fetch
  and response-body consumption, with cancellation on disconnect. This does not prevent
  earlier platform/server buffering or replace ingress body/connection limits.
- Public JSON responses are checked against strict nested field allow-lists. Proxy replies
  use locally constructed `no-store` headers; the only retained upstream header value is
  a validated bounded delta-seconds `Retry-After`. Unexpected bodies, debug pages, private
  fields and exception details do not pass through to the browser.

Django therefore normally sees a **shared Next proxy IP**, not each browser's IP. Its
process-local rate limiter may share a bucket across users. A different client-identity
boundary requires a separately hardened trusted ingress; do not forward untrusted IP
headers to evade limits. Preserve the backend's private application port, trusted HTTPS
proxy-header handling, hardened edge rate limits and privacy-safe logging requirements in
[`../operations/private-pilot.md`](../operations/private-pilot.md). Next is not a replacement
for those controls. This integration adds no production deployment, migration or infrastructure.

### Tab-scoped case and browser protections

The client uses `sessionStorage` for one active Service case per tab: format version,
Service ID, current source Facts, minimal answer history (Question IDs and Fact keys), and
calendar evaluation date. Starting a different Service questionnaire replaces the previous
case; it does not create a case archive. Plans, response objects, Derived Facts and authored
Question text remain out of storage. Submitted answers can be restored and re-evaluated;
unsubmitted drafts need not survive refresh. Storage failures allow memory-only continuation
with an explicit notice.

Case data does not enter `localStorage`, cookies, URLs, server sessions or server-side
Case records. Browser session restoration or tab duplication can retain tab data: closing
a tab is not a secure-deletion guarantee. The interface provides confirmed clearing and
shared-device guidance; if browser storage cannot be cleared, the person must remove site
data through browser settings. Printing or saving a PDF produces a separate potentially
sensitive copy that must be protected/disposed of independently; clearing the case does not
delete exports.

Fonts are self-hosted; the application embeds no third-party tracking. Its static CSP limits
connections/fonts to self, blocks framing/objects and accompanies no-referrer, nosniff and
permissions restrictions. Script/style `'unsafe-inline'` remains a Next hydration/style
tradeoff, with script `'unsafe-eval'` limited to development. A nonce-based production CSP
requires separate hardening and verification; these application headers are not a complete
ingress policy. Questionnaire `noindex` metadata is not authentication or data protection.

## Snapshot composition

`knowledge.domain` explicitly composes each semantic snapshot in this order: stable internal
core materializer → Eligibility Basis snapshots → Procedure Dependency snapshots → Service
Point routing snapshots. Feature transformations do not replace the materializer at import
time. Runtime-local imports avoid model-registration cycles; Django's feature-model registration
order is unchanged.

The generic snapshot loaders return that complete semantic graph without latest-state workflow
overlays. The explicit `*_as_of(evaluation_date)` loaders run the same semantic pipeline, then
apply only the date-appropriate evidence-workflow overlay. Each stage executes once, eagerly,
and preserves fail-closed catalog validation. The consistent loaders enclose all semantic and
applicable workflow reads in one outermost read-only, repeatable-read transaction; they reject
nested transactions. The non-consistent loaders impose no transaction policy. No ORM objects or
lazy relations cross into planning.

## Privacy and observability

- Do not persist raw Anonymous Case Facts in version 1.
- Do not log request bodies containing raw Facts, in Django, Next or upstream infrastructure.
- Next's `logging: false` and `experimental.serverComponentsHmrCache: false` are mandatory
  privacy controls. The development HMR fetch cache otherwise caches POSTs even when
  requests specify `no-store`. Do not enable framework request/fetch logging for debugging.
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
- Next/APM, deployment ingress, reverse-proxy, platform access logging, tracing, analytics
  and error reporting must not capture Facts, Fact keys, request bodies, planning responses,
  exceptions, stacks, query strings or Evaluation Traces. Application filters and Next's
  logging/cache settings do not configure those external sinks. Use only an explicit coarse
  allow-list, never a richer payload with known keys redacted.
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

The frontend adds generated-contract/runtime-schema checks, API proxy/privacy and bounded
transport tests, typed questionnaire/state/storage tests, bilingual full/partial Plan rendering
and print tests, and production-build Playwright integration tests against a synthetic,
test-only API stand-in. The OpenAPI exporter and frontend checks require Python 3.14/uv
and Node 22 but no PostgreSQL. The committed `frontend/api-schema.json` must match Django
Ninja's declarations, and `frontend/src/api/generated.d.ts` must match type generation;
CI fails on either drift. Browser fixtures are not backend acceptance evidence or production
navigation data. Full scope and commands are in
[`../../frontend/README.md`](../../frontend/README.md).

A production implementation is not considered semantically complete merely because its ORM and endpoints work; it must reproduce the intended planning behavior captured by the authoritative rules contract and acceptance scenarios.

Test settings may explicitly omit the review gate to isolate unrelated validation tests; this is
not a production off mode. Review integration tests must exercise both modes and specialist and
audit invariants with the gate present.

## Explicit exclusions for the first backend milestone

- microservices;
- event sourcing;
- generalized workflow/BPM infrastructure;
- recursive automatic planning of Procedure dependencies;
- user profiles or saved administrative cases;
- document upload/verification;
- trusted/autonomously applied AI-authored rules or automatic legal determinations (external-LLM
  draft preparation is untrusted input to the separate human-reviewed authoring contract);
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
