# Bardi web

The Next.js App Router frontend for Bardi's Django Ninja public API. Arabic (`/ar`, RTL)
is the default; the header switches to English (`/en`, LTR) on the corresponding page.
The web app presents authored guidance, not government decisions or an application service.

## Local development

Use a current **Node 22** release (`frontend/.nvmrc`) and npm. Run commands from the
repository root unless a command explicitly changes directory.

1. Set up PostgreSQL and Django using [`docs/development.md`](../docs/development.md).
   Keep Django running separately at `http://localhost:8000`; Admin is at `/admin/`.
2. On first frontend setup:

   ```bash
   cp frontend/.env.example frontend/.env.local
   npm --prefix frontend ci
   npm --prefix frontend run dev
   ```

3. Open **http://localhost:3000/ar**. Visiting `/` redirects to `/ar`; use **English**
   in the header to switch languages. The dev server binds to `127.0.0.1`.

Next reads `frontend/.env.local`; it does not use the backend's root `.env` as its
configuration contract. Do not copy Django/database secrets into the frontend environment.

Use `npm ci` for reproducible installs from `frontend/package-lock.json`. An npm 10
Arborist dependency-update bug was encountered while updating this lock; npm 11 installed
the current lock. Use npm 11 for dependency upgrades if updating the lock, for example
`(cd frontend && npx --yes npm@11 install <package>@<version>)`. No global npm installation
or upgrade is required for this workflow; routine setup uses the committed lock, not
`npm update`.

### Real knowledge, not a demo catalog

Navigation comes only from `GET /v1/services`, whose sole activation criterion is the
editorial `Service.is_active` flag. Publication dates or a published Procedure Version
do not implicitly activate a Service.

Use the researched imports and normal independent Admin review/publish workflow described
in [`docs/development.md`](../docs/development.md) to prepare usable guidance. Imports
create drafts, not approvals or publication. Keep Service activation and Procedure-Version
publication explicit. Empty navigation and unavailable services have honest recovery states;
production navigation never substitutes bundled fake data, a demo plan, or a closest match.
Synthetic fixtures and the browser-test API stand-in are test-only.

## Current application scope

- Server-rendered bilingual Service directory, Service introduction and privacy pages;
  canonical/alternate-language metadata, sitemap and robots metadata. Questionnaire pages
  are marked `noindex`, `nofollow`, and `noarchive`; those directives are not access control.
- A backend-driven questionnaire for all public answer kinds: boolean, enum, integer,
  Gregorian date and string, including multi-Fact Questions. Unanswered Facts stay omitted;
  nothing is implicitly answered No. The server owns administrative rules and progression.
- All four planning outcomes: `next_question`, `plan`, `inconclusive`, and `invalid`.
  Review/correction discards the affected and subsequent answers. Locale/date changes and
  case clearing cancel obsolete requests; failures retain answers for manual retry, including
  bounded `Retry-After` handling without automatic POST retries.
- Plans show identity/evaluation date, warnings, direct prerequisites, Official Requirements
  separately from Practical Preparation, quantities, ordered steps, fee value states,
  non-ranked Eligibility Bases, local routing uncertainty, and compact sources/freshness.
  Unknown fees are not invented or totaled; routing is not a nearest-office recommendation.
  Browser printing includes sources and the reminder to regenerate immediately before acting.

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

```bash
uv sync --locked
uv run python tools/export_web_api.py --check
npm --prefix frontend run api:generate
# Generated files must already be tracked and current when checking drift.
git diff --exit-code -- frontend/api-schema.json frontend/src/api/generated.d.ts
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

`tools/export_web_api.py` builds OpenAPI from Django Ninja's declarations in memory without
a database connection, migrations or production secrets. `--check` fails on a missing or
stale `frontend/api-schema.json`. When intentionally changing the backend public contract,
regenerate from the **repository root**:

```bash
uv run python tools/export_web_api.py
npm --prefix frontend run api:generate
```

Review and include both `frontend/api-schema.json` and `frontend/src/api/generated.d.ts`
with the contract change; do not hand-edit generated types. CI checks the snapshot, then
regenerates types and checks those exact paths for drift. Type checking also checks runtime
Zod schemas against the generated public types in both directions.

### Production-build browser checks

Install Playwright's managed Chromium locally, then test the production build:

```bash
(cd frontend && npx playwright install chromium)
BARDI_API_ORIGIN=http://127.0.0.1:8451 BARDI_SITE_ORIGIN=http://localhost:3010 \
  npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

On Linux runners needing browser system packages, CI uses
`(cd frontend && npx playwright install --with-deps chromium)`. Alternatively, use an
existing local Chromium-compatible executable without downloading a managed browser:

```bash
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/absolute/path/to/chromium \
  npm --prefix frontend run test:e2e
```

`playwright.config.ts` starts the existing Next production build at `http://localhost:3010`
(bound to `127.0.0.1`) and the **test-only** `e2e/api-stand-in.mjs` API on
`127.0.0.1:8451`; keep both ports free. Build with the same site origin, as above, so
build-time robots/SEO metadata matches the browser origin. It does not need Django
or PostgreSQL and must never point at real cases. The stand-in is not a production fallback
or a replacement for backend acceptance tests. Servers are not reused; if the default API
port is occupied, the configuration permits `BARDI_E2E_API_PORT=8471` as a local test-only
alternative. CI uses the default 8451. Trace, screenshot and video recording are disabled,
and CI uploads no browser artifacts. Do not upload reports or captures containing real cases.

For visual inspection using **synthetic data only**, after the browser-test build above,
start these in two terminals from `frontend/`:

```bash
node --experimental-strip-types e2e/api-stand-in.mjs
```

```bash
BARDI_API_ORIGIN=http://127.0.0.1:8451 BARDI_SITE_ORIGIN=http://localhost:3010 \
  npm run start -- --port 3010
```

Open `http://localhost:3010/ar` or `/en`. Follow the synthetic fixture instructions in
`e2e/fixtures.mjs`; use `TEST-ONLY-NOTE`, never personal information. Stop these processes
before running Playwright, which needs to own the same ports.

### Regression scope

- `src/api/*.test.ts`: every public result and nested allow-list, exact generated contract,
  transport/date/Unicode limits, status/error normalization, header and origin isolation,
  request stream size/deadline/disconnect cases, retry/cancellation, no sensitive logging,
  mandatory Next privacy settings, and deterministic database-free export/missing/stale checks.
- `src/planning/state.test.ts` and `storage.test.ts`: typed values and omissions, recurring
  multi-Fact Questions, correction history, current bilingual labels, one-case isolation,
  corrupt/incompatible storage, quota/access failures and explicit storage allow-lists.
- `src/planning/questionnaire.test.tsx`: SSR/hydration, Arabic/English fields, every result,
  review/diagnostic correction, refresh, locale/date changes, cancellation/stale results,
  confirmed clearing, manual retry/cooldown, storage fallback, privacy and browser printing.
- `src/components/plan-view.test.tsx`: complete/partial plans in both languages, all guidance
  sections and states, exact dates/quantities, unknown money, non-ranked Bases, direct
  dependencies, local routing limits, safe source links and complete printable evidence.
- `e2e/*.spec.ts` (Playwright): production Next navigation and language switching, no-JavaScript
  Service pages, canonical/alternate/noindex metadata, sitemap and HTTP 404s; complete
  bilingual questionnaire-to-plan journeys and print media; review/refresh, tab/Service
  isolation, confirmed clearing; invalid/inconclusive outcomes, 429 cooldown, unavailable,
  malformed or wrong-Service responses, manual recovery and delayed-response cancellation;
  privacy checks for URLs/storage/metadata/credentials/analytics, safe external links and
  inert hostile locators/authored text; 390px Arabic RTL overflow, keyboard/focus and disclosure
  checks. Projects are desktop Chromium and mobile Chromium emulation, not a full
  cross-browser or accessibility audit. These use synthetic responses through the real
  same-origin boundary (with browser interception for selected failure cases), not
  Django/PostgreSQL or researched-family parity.

See [`docs/ci-cd.md`](../docs/ci-cd.md) for the independent Frontend CI job and the required
two-track aggregate. The architectural boundaries remain governed by
[ADR 0004](../docs/adr/0004-do-not-persist-case-facts.md),
[ADR 0005](../docs/adr/0005-use-nextjs-with-django-ninja.md),
[ADR 0006](../docs/adr/0006-expose-one-stateless-planning-operation.md),
[`production-backend.md`](../docs/architecture/production-backend.md) and
[`docs/api/v1.md`](../docs/api/v1.md). No production deployment or migration is part of
frontend setup or these database-free checks.
