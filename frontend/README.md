# Bardi web

The Next.js App Router frontend for Bardi's Django Ninja public API. Arabic (`/ar`, RTL)
is the default; the header switches to English (`/en`, LTR) on the corresponding page.
The web app presents authored guidance, not government decisions or an application service.

## Local development

Use **Node 22** (`frontend/.nvmrc`) and npm. The development guide owns runnable
[full-stack Compose setup](../docs/development.md#full-stack-docker-compose-setup),
[host-run frontend setup](../docs/development.md#frontend-setup) (including dependency
upgrades), and [shutdown](../docs/development.md#teardown).
Open **http://localhost:3000/ar**; the host-run dev server binds to `127.0.0.1`.

Next reads `frontend/.env.local`, not the backend's root `.env`.
Do not copy Django/database secrets into the frontend environment.

### Real knowledge, not a demo catalog

Navigation comes only from `GET /v1/services`, whose sole activation criterion is the
editorial `Service.is_active` flag. Publication dates or a published Procedure Version
do not implicitly activate a Service.

Use the researched imports and mode-aware Admin review/publish workflow described
in [`docs/development.md`](../docs/development.md#solo-now-independent-when-the-team-joins)
to prepare usable guidance. `solo` skips general approvals; `independent` requires them.
Both modes still require independent specialists for flagged high-risk content. Imports
create drafts, not approvals or publication. Keep Service activation and Procedure-Version
publication explicit. Empty navigation and unavailable services have honest recovery states;
production navigation never substitutes bundled fake data, a demo plan, or a closest match.
Synthetic fixtures and the browser-test API stand-in are test-only.

## Current application scope

The server owns questionnaire rules and progression. Unanswered Facts stay omitted, never
implicitly No. Correction discards the affected and subsequent answers; failures retain
answers for manual retry, without automatic POST retries. Locale/date changes and clearing
cancel obsolete requests.

Plans distinguish Official Requirements from Practical Preparation. Unknown fees are not
invented or totaled; Eligibility Bases are non-ranked, and routing is not a nearest-office
recommendation. Regenerate guidance immediately before acting, including printed guidance.
Questionnaire `noindex`, `nofollow` and `noarchive` directives are not access control.

## Configuration and the public API boundary

| Variable | Use |
| --- | --- |
| `BARDI_API_ORIGIN` | Server-only Django HTTP(S) origin. The example uses `http://127.0.0.1:8000`. Required for working API access outside development, including production. |
| `BARDI_SITE_ORIGIN` | Exact trusted public origin for browser POST validation and SEO. Required for planning outside development. Development alone defaults to `http://localhost:3000`; no production domain is assumed. |
| `NEXT_TELEMETRY_DISABLED` | Set to `1` in the example and Next scripts. |

`BARDI_API_ORIGIN` must be an origin only: no credentials, query, fragment or path other
than `/`. Never use a `NEXT_PUBLIC_` prefix. Missing/invalid production API configuration
fails closed to an unavailable result, not a localhost or demo fallback. Development alone
has an unconfigured `http://localhost:8000` fallback.

`BARDI_SITE_ORIGIN` must be the canonical serialized HTTP(S) origin, with **no trailing
slash**, credentials, path, query, fragment, whitespace or explicit default port. Browser
Origin values must match it exactly. Missing or invalid configuration outside development
makes planning unavailable. The check does not trust the listener hostname or forwarded
scheme/host headers. Metadata alone falls back to localhost when misconfigured; that is
not a production API fallback. Set this value when using a different public hostname/port.

The browser uses same-origin public routes only: `GET /v1/services` and
`POST /v1/planning`. The Next Node route handlers and server-side Service loader use fixed
Django endpoint paths and strict public response schemas. There is no general proxy,
Admin/authentication proxy, health proxy or cross-origin CORS configuration.

- Requests use `credentials: "omit"`, `cache: "no-store"` and no referrer; inbound cookies,
  authorization, query strings, forwarded headers, request IDs and client IP headers are
  never forwarded to Django. Cross-site planning POSTs are rejected; redirects are not
  followed upstream.
- The planning request stream is bounded to **512 KiB (524,288 bytes)**, independently of
  `Content-Length`. A **10-second deadline** covers request reads, upstream fetch and
  response-body consumption; disconnects cancel pending work.
- Responses must match the strict public JSON allow-list, including nested fields. Upstream
  debug/error bodies and exceptions are not passed through. Proxy responses are `no-store`
  with locally constructed headers; only validated delta-seconds `Retry-After` values
  (0–86400) can be retained from upstream headers. Cookies and other upstream headers are
  not propagated.

This requires a Next server, not a static export. Before deployment, retain the trusted
backend ingress requirements in [`private-pilot.md`](../docs/operations/private-pilot.md).
Django sees the **shared Next proxy IP**, not the browser IP, unless a separately hardened
trusted ingress establishes another identity boundary. Its process-local limiter can
therefore share a bucket across users. Do not forward untrusted IP headers to bypass it.
Edge rate limits, TLS/proxy-header trust, body/connection limits and privacy-safe access
logging still require hardened deployment configuration; application limits cannot prevent
earlier platform buffering. This frontend does not deploy anything or change infrastructure.

## Case privacy and browser security

`sessionStorage` holds exactly **one active Service case per tab** under
`bardi.active-case.v1`: format version, Service ID, source Facts, minimal answer history
(Question IDs/keys) and evaluation date. Starting another Service questionnaire replaces
the old case rather than archiving it. Plans, responses, Derived Facts and localized
Question text are not stored. Restoring submitted answers triggers a fresh evaluation;
unsubmitted field drafts are not guaranteed to survive refresh. Storage failure permits
memory-only continuation with a notice. A browser-only, single-Service owner preserves source
answers, the cleared/idle marker and manual-retry deadlines across language-route remounts,
including when tab storage is blocked. It never retains a plan or allocates a server-side case.

There are no case saves in `localStorage`, cookies, URLs, server sessions or a server-side
Case record. Tab storage is not a deletion guarantee: browsers may restore/duplicate tabs
or restore sessions. On a shared device use **Clear answers and start again** before
leaving; if clearing fails, remove the site's browser data. Printing or saving a PDF creates
a separate potentially sensitive copy: keep it safe and dispose of it separately. Clearing
Bardi answers does not delete printouts or downloaded files.

Do not send **Facts, Fact keys, request bodies, planning responses, exceptions, stacks or
Evaluation Traces** to Next logs, APM, ingress analytics, session replay, error reporting or
other telemetry. There is no planning analytics integration. Any future planning
observability must use only the explicit coarse allow-list: HTTP method, fixed
`/v1/planning` route, status and coarse error code. Do not build a richer event and redact
known keys. Ingress/platform logging must be configured separately not to capture bodies,
responses, query strings or private request metadata; Next's settings are not a platform
logging policy.

These settings in `next.config.ts` are mandatory privacy controls, not optional tuning:

```ts
logging: false,
experimental: { serverComponentsHmrCache: false, /* other options unchanged */ },
```

Next's development HMR fetch cache otherwise caches POST requests even with `no-store`.
Do not enable request/fetch logging or remove either control during debugging.

Fonts are self-hosted from the installed Fontsource packages; the app embeds no third-party
tracking. The static CSP restricts connections and fonts to self, blocks framing and objects,
and accompanies no-referrer/nosniff/permissions headers. It currently allows script/style
`'unsafe-inline'` for Next hydration and styles (`'unsafe-eval'` for development only).
This is a documented tradeoff, not a claim of a complete production CSP or ingress policy;
a nonce-based CSP needs separate production hardening and verification. External source
links are explicit user navigation with `noopener noreferrer`, not embedded tracking.

## Checks and generated API contract

The complete unit suite also invokes the real Python schema exporter, so **Python 3.14
and uv are required even for `npm test`**. PostgreSQL is not required for the frontend
checks or schema export.

Run the [frontend checks and API schema commands](../docs/development.md#frontend-checks-and-api-schema)
for lint, types, unit tests, build and generated-contract drift. That section also owns
intentional schema regeneration; include both generated files with contract changes and
never hand-edit generated types. Type checking checks runtime Zod schemas against the
generated public types in both directions.

### Production-build browser checks

Use the [browser setup and visual inspection commands](../docs/development.md#frontend-checks-and-api-schema)
with synthetic data only. Playwright owns both loopback ports and never reuses servers.
Its stand-in is not a production fallback or a replacement for backend acceptance tests.
Trace, screenshot and video recording are disabled, and CI uploads no browser artifacts.
Do not upload reports or captures containing real cases.

### Regression scope

Unit/component tests cover the public contract, transport/privacy boundaries, case state,
recovery and bilingual rendering. Browser tests exercise the production Next same-origin
boundary with synthetic responses, not Django/PostgreSQL or researched-family parity.
Desktop Chromium and mobile Chromium emulation are not a full cross-browser or
accessibility audit.

See [`docs/ci-cd.md`](../docs/ci-cd.md) for the independent Frontend CI job and required
verification aggregate. The architectural boundaries remain governed by
[ADR 0004](../docs/adr/0004-do-not-persist-case-facts.md),
[ADR 0005](../docs/adr/0005-use-nextjs-with-django-ninja.md),
[ADR 0006](../docs/adr/0006-expose-one-stateless-planning-operation.md),
[`production-backend.md`](../docs/architecture/production-backend.md) and
[`docs/api/v1.md`](../docs/api/v1.md). No production deployment or migration is part of
frontend setup or these database-free checks.
