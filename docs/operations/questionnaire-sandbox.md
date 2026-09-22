# Local questionnaire sandbox

Use a trusted [local database backup](local-backups.md) to run a reusable copy beside the
normal authoring stack. Run from the same checkout root with Python 3.14+, `uv`, Docker Compose
and the local Unix Docker socket (`/var/run/docker.sock`). No authoring `.env` is copied or
loaded, and the authoring stack need not be stopped. Normal authoring commands are unchanged.

## Initialize, resume and refresh

Use the exact private archive path from the backup output:

```bash
archive=/absolute/path/from/backup/output.dump
uv run python tools/local_sandbox.py start --archive "$archive"
```

Default endpoints, all bound only to loopback:

- Questionnaire: **http://127.0.0.1:13000/ar** or **http://127.0.0.1:13000/en**
- Django Admin: **http://127.0.0.1:18000/admin/**
- PostgreSQL: `127.0.0.1:15432`

The default private state directory is `~/.local/state/bardi/questionnaire-sandbox`.
For a different directory, ports or review policy, use this **instead of** the first command:

```bash
uv run python tools/local_sandbox.py --state-directory "$HOME/.local/state/bardi/review-sandbox" \
  start --archive "$archive" --frontend-port 13001 --backend-port 18001 \
  --postgres-port 15433 --review-mode independent
```

Ports must be distinct, valid and available. Directory selection precedes the subcommand;
repeat the same `--state-directory` on every subsequent command when using a nondefault path.
Ports and review mode are immutable after first initialization, even on a retry.

For the default sandbox:

```bash
# Inspect without provisioning, restoring or changing data.
uv run python tools/local_sandbox.py status

# Resume the committed database, retaining sandbox edits; do not supply --archive.
uv run python tools/local_sandbox.py start

# Stop verified sandbox services, retaining the volume and private state.
uv run python tools/local_sandbox.py stop

# Explicitly replace the active copy with a newly restored generation.
archive=/absolute/path/to/a/trusted/replacement.dump
uv run python tools/local_sandbox.py refresh "$archive" --confirm
```

`refresh` requires confirmation and an existing active generation. It stops the applications
before restoring into a fresh `bardi_restore_<uuid>` database, checks compatibility, then commits
the new active generation. Old generations and failed candidates are retained, not overwritten
or deleted. A successfully refreshed running sandbox restarts its apps; a stopped sandbox stays
stopped. Refresh does not merge local edits. There is no generation-selection or cleanup CLI.

## Copied data, unchanged publication policy

Log in with a copied staff account and its existing password; permissions and password hashes
are restored, and no user is created. The sandbox generates its own PostgreSQL credentials and
fresh Django secret. Session and CSRF cookie names are namespaced by sandbox identity because
ports alone do not isolate cookies. Expect to log in separately. Admin says
**LOCAL QUESTIONNAIRE SANDBOX**; Arabic and English pages show a small copied-data notice,
including in print. Use the separate URLs to distinguish environments.

The generated configuration explicitly defaults to `solo`, but inherits **all base publication
gates**, including required selection questions and planning scenarios. Solo is not a bypass:
high-risk content still needs eligible specialists independent of author and publisher. Keep
risk flags truthful and such content unpublished without those specialists. See the
[review policy](../architecture/procedure-version-review-roles.md#deployment-review-mode).

Startup and refresh do not publish, approve, activate Services, import draft packs or migrate.
Existing copied publication/activation state remains as archived. Empty questionnaires may be
correct: launching a copy does not prove that real authored content is ready for a full journey.

## Compatibility and failure recovery

Every start/refresh builds current checkout code with normal Docker cache; there are no source
bind mounts or host `.next`/`node_modules` writes. Read-only Django system and migration-history
checks run before applications start; pending, inconsistent and applied-but-unknown migrations
are rejected. **Use code matching the restored schema.** Do not run migrations merely to hide a
mismatch. Retain the archive and its matching code revision; changing code requires `start`,
not a host reload. This is not an image-pinning or update-management system.

Successful commands emit JSON with status, project, active database and application URLs.
Status is `not-initialized`, `stopped`, `running` or `interrupted-or-unavailable`.
Runtime failures currently collapse to `sandbox_operation_failed` (exit 1), not detailed
per-cause diagnostics; do not infer a particular failure or commit outcome from that message.

- **Before the active-generation commit:** the previous generation remains authoritative;
  refresh failures after quiescing leave apps stopped. Resolve the cause and use `start` to
  resume the old generation with compatible code.
- **After commit, including app-start failure:** the new generation remains authoritative;
  `start` retries it. There is no automatic rollback. Inspect `status` when available; the
  on-disk manifest is authoritative even after an ambiguous interruption.
- **Initial restore failed before any active generation:** retry `start --archive "$archive"`
  without first-init options; it uses a new candidate. Once a generation is active, omit
  `--archive` on `start` and use confirmed `refresh` for replacement.
- **Unsafe state, unexpected resources, missing/replaced initialized volume or unavailable
  Docker:** operations fail closed. Preserve state and resources for private investigation;
  do not delete the manifest/lock or recreate an empty volume to force a retry. A concurrent
  operation also fails rather than waiting; let it finish before retrying.

## Retention and trust boundary

The independent `compose.sandbox.yaml` uses a persistent random `bardi-sandbox-<id>` project,
its own PostgreSQL 17 volume/network and application images, no shared/external volumes, no
source/secret/Docker-socket bind mounts, and no restart policy. The launcher verifies resource
identities and ignores ambient authoring/Compose/Docker/database overrides. Use the launcher,
not ordinary `docker compose` commands, to operate it. Sandbox Docker log persistence is disabled.

Private state must be outside Git worktrees, owned by you with mode `0700`, without symlink
components; its regular files are `0600`. It contains credentials in **plaintext**, not encrypted
storage. Copied databases and archives also contain private staff/editorial data. Follow the
[backup confidentiality and archive rules](local-backups.md#take-a-backup); do not upload state,
SQL, screenshots or archives as artifacts. Use synthetic cases for testing.

Only restore trusted archives: PostgreSQL archives contain **executable SQL**. This topology
prevents accidental mixing with authoring resources; it is **not containment of malicious SQL
or privileged Docker users**. Retention is intentional: stop is not deletion and volumes are
not backups. No automatic pruning or cleanup is provided. Any later removal needs separate,
careful identification of only the intended sandbox resources; never use authoring `down -v`
or broad Docker pruning as sandbox cleanup.

## Regression scope

Database-free launcher and probe guards can be checked without touching authoring data:

```bash
(cd backend && uv run python -m unittest core.tests.test_local_sandbox -v)
uv run python -m unittest tools.test_probe_local_sandbox -v
```

The separate [Questionnaire sandbox CI track](../ci-cd.md#continuous-integration) runs
`uv run python tools/probe_local_sandbox.py --disposable --with-browser`. It creates only owned synthetic
projects and checks restored rows/sequences/constraints/triggers before writes, all publication
gates, real Admin login/cookies, localized notices, the Next proxy question/publish/plan/withdraw
path, resume persistence, generation retention and rejected refreshes. It verifies its synthetic
source remains unchanged and removes only its owned disposable resources. This is tooling
coverage, not proof of real archive recoverability, researched-content readiness or visual quality.

The optional browser phase requires `--disposable`; it never targets authoring or a persistent
sandbox. It imports and canonically publishes the ordinary National ID renewal fixture only in
the restored disposable database, with normal publication/scenario gates and solo review enabled.
Three real Django/PostgreSQL browser tests cover Arabic/English directory-to-plan journeys and
English possession correction (held → lost → held), including downstream-answer clearing,
inconclusive recovery, unknown fees, unresolved routing and the blocked previous-card exclusion.
Database snapshots check that the browser phase makes no database changes.

This reuses the probe's Next **development** server, not a production build. With `BARDI_SANDBOX=1`,
Next explicitly allows the `127.0.0.1` development origin so its browser runtime can initialize
through the published loopback port. This does not widen API origins or CSP, and ordinary
(non-sandbox) configuration remains unchanged. Browser time and evaluation date are fixed at
**2026-08-26**; passing tests do not establish present-day evidence
freshness. These three representative tests complement, rather than repeat, the 78 synthetic
production-build browser tests. New Procedures need their own editorial checks and scenarios,
not another full browser suite unless they introduce a new interaction pattern. Normal CI gates
remain in force. The probe uses the existing researched fixture, not an authoring backup.

### Real-backend browser command

Prerequisites: Python 3.14+, uv, Docker with Compose and a running daemon, Node 22/npm, and
Chromium with its Linux system dependencies. From the repository root:

```bash
uv sync --locked --extra dev
npm --prefix frontend ci
(cd frontend && node node_modules/@playwright/test/cli.js install --with-deps chromium)
(cd frontend && node node_modules/vitest/vitest.mjs run --config e2e-real/vitest.config.ts)
uv run python tools/probe_local_sandbox.py --disposable --with-browser
```

The focused Vitest command runs 16 database-free configuration/reporter regressions. On Linux,
an existing compatible Chromium can replace the managed browser installation (system libraries
must already be installed):

```bash
PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/absolute/path/to/chromium \
  uv run python tools/probe_local_sandbox.py --disposable --with-browser
```

No authoring `.env`, archive or manually supplied target URL is needed. The probe supplies the
loopback origin and disposable marker, invokes local pinned Playwright, limits browser environment
and network access, and emits data-free results without retained browser artifacts. Browser
failure fails the probe and triggers owned-resource cleanup. Omit `--with-browser` for the
original tooling-only probe.
