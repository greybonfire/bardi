# Local database backup and recovery

For the existing **local development Compose stack**. Run commands from the repository root
with Python 3.14+, `uv`, Docker Compose and the `postgres` service already running. The tool
uses PostgreSQL's clients inside that container; host `pg_dump` is not required. It does not
start services, modify `.env`, import packs, publish guidance or apply migrations.

The named PostgreSQL volume persists across restarts and ordinary `docker compose down`.
It is not a backup: `docker compose down -v` deletes it, and host/storage failure can lose it.
Draft-pack JSON is an authoring format, not a replacement for a database backup.

## Take a backup

```bash
uv run python tools/local_database.py backup
```

The JSON response supplies the archive's absolute `path`, source database and byte count.
By default archives are under `~/.local/state/bardi/backups/`. To choose another location:

```bash
uv run python tools/local_database.py backup --directory /absolute/private/backup-directory
```

The directory must be outside Git worktrees, owned by you with mode `0700`, and have no symlink
components. Ancestors must be owned by you or root and protected from replacement by other users;
trusted sticky directories such as `/tmp` are allowed. A missing directory is created; an unsafe
existing directory is rejected, not silently changed. Archives have mode `0600`, unique names and PostgreSQL custom format.
Dumping is read-only and uses PostgreSQL's consistent snapshot. A private partial file becomes
a completed archive only after the dump and archive-read checks succeed. Failure removes the
partial file; existing archives are never overwritten or pruned.

Take a backup before substantial bulk edits or migrations and regularly while authoring.
Archive readability alone does **not** prove recovery: perform the restore drill below.

**Confidentiality:** archives include staff accounts/password hashes, permissions, editorial
records and audit history. They are private **unencrypted** files; `.gitignore` is only a
secondary precaution. Do not commit or upload them as CI artifacts. Keep additional protected,
encrypted copies off the machine; this tool provides neither encryption, scheduled backups nor
retention management. It is not the [production backup policy](private-pilot.md#backup-policy).

## Restore into a fresh, separate database

Use only trusted archives you created or obtained from a trusted administrator. PostgreSQL
archives contain executable SQL; restoration is not a sandbox for untrusted files.

Copy the successful backup's exact path into `archive`:

```bash
archive=/absolute/path/from/backup/output.dump
target="bardi_restore_check_$(date -u +%Y%m%d_%H%M%S)"
uv run python tools/local_database.py restore "$archive" --database "$target"
```

The tool uses the running local Compose PostgreSQL server and rejects remote Docker endpoints.
The target must be a lowercase `bardi_restore_` name (letters, digits and underscores; at most
63 characters), must differ from the configured source, and **must not already exist**, even
if empty. Concurrent target creation also fails closed. There is no force, overwrite, reset or
delete option, and restoration never uses `--clean` or the archive's database-creation command.

A new database is created from `template0`. Restoration runs in one transaction with errors
fatal; original ownership/ACLs are omitted so restored objects belong to the local restore role.
If creation/restoration fails or is interrupted, any created target is retained for inspection.
Do not assume it is usable; retry with a new target name. The tool does not automatically drop
or disconnect databases.

Success reports **`restored_unverified`**: the restore completed, but recovery still needs the
following checks. No application is started or redirected to it.

## Verify recovery without changing either database

Use matching application code and PostgreSQL 17. With the normal backend container running,
run read-only checks against the explicit restored target:

```bash
docker compose exec -T -e POSTGRES_DB="$target" \
  -e PGOPTIONS='-c default_transaction_read_only=on' backend \
  python backend/manage.py migrate --check --settings=bardi.settings.development

docker compose exec -T -e POSTGRES_DB="$target" \
  -e PGOPTIONS='-c default_transaction_read_only=on' backend \
  python backend/manage.py check --settings=bardi.settings.development
```

Compare representative drafts and their guidance, staff accounts/permissions, publication
reviews and audit history with the source. Compare account password hashes privately, never in
logs. Counts alone are not proof that contents survived. If the source was edited after the
backup snapshot, account for those changes rather than expecting current counts to match.

A migration mismatch is a failed recovery check for that code version: do not run migrations
just to conceal it. Database dumps do not include `.env`, application code, Docker configuration
or cluster-wide roles; retain the matching code revision and protect required configuration
separately. The restore is not intended to reproduce production role grants.

After verification, keep the clearly named copy for inspection or deliberately remove only
that disposable database using PostgreSQL administration. Do not use `down -v` to clean up a
restore drill: the source shares that volume. A separate questionnaire sandbox launcher is not
part of this tool.

## Regression checks

Database-free guards and failure-path tests:

```bash
(cd backend && uv run python -m unittest core.tests.test_local_database -v)
uv run python -m unittest tools.test_probe_local_database -v
```

The real regression creates its **own random disposable Compose project**, fresh PostgreSQL
volume and synthetic records. It verifies row/sequence preservation, constraints and triggers,
read-only Django checks, source preservation and rejection guards, then removes only its own
resources. It never seeds or restores over the authoring database:

```bash
uv run python tools/probe_local_database.py --disposable
```

This probe also runs in the Development Compose CI track. It tests the recovery tooling, not
recoverability of every archive; periodically drill an actual authoring backup too.
