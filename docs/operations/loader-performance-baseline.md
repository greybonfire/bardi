# Service-scoped loader performance baseline

Historical issue #119 measurement, retained separately from local onboarding.
Run commands from the repository root after the
[host-run setup](../development.md#backend-setup-host-run-workflow), with `.env`
values exported and PostgreSQL running. Use only the disposable database below,
never a shared or production catalog.

Issue #119 includes a self-contained disposable PostgreSQL probe. It creates its own namespaced
requested published graph, unrelated published graphs, authoring-draft graphs with evidence,
and unrelated semantic-preserving workflow history; no pre-existing `issue119.requested`
service or custom Fact is required.

```bash
# Create and migrate a disposable database using the local PostgreSQL service.
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
  -c 'CREATE DATABASE bardi_issue119_repair_probe'
POSTGRES_DB=bardi_issue119_repair_probe uv run python backend/manage.py migrate \
  --settings=bardi.settings.test --noinput

# Seed, compare, and clean each unchanged generated dataset.
PYTHONPATH=backend POSTGRES_DB=bardi_issue119_repair_probe \
  uv run python tools/measure_service_scoped_snapshot.py \
  --facts '{"application_location":"inside_egypt"}' --locale en \
  --evaluation-date 2026-12-31 --scales 0,100,500 \
  --settings bardi.settings.test
```

The probe reports exact queryset-equivalent global validation row sets, SQL count, detached
object counts, elapsed time, full/scoped workflow rows, shared Fact-registry rows, requested
Graph rows, unrelated materialized rows, and full/scoped response equality. Each generated
published anchor carries two discrepancy-transition rows (open/resolved) and two repeated
re-verification rows, so event rows are distinguishable from unique workflow owners. It removes
the namespaced generated rows after each scale and vacuums/analyzes the disposable database so
sequential scales do not measure deleted-row bloat. If interrupted, drop the disposable database
rather than running it against a shared catalog:

```bash
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
  -c 'DROP DATABASE bardi_issue119_repair_probe'
```

The 2026-09-10 run produced:

| unrelated published / draft graphs | workflow event rows | validation rows | full SQL / scoped SQL | full detached rows | scoped detached rows | full workflow rows / scoped workflow rows | responses match | full ms / scoped ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: | ---: |
| 1 / 1 | 0 | 56 | 23 / 48 | 56 | 46 | 0 / 0 | yes | 123.241 / 214.902 |
| 101 / 101 | 400 | 1556 | 23 / 49 | 1056 | 46 | 400 / 0 | yes | 261.890 / 229.722 |
| 501 / 501 | 2000 | 7556 | 23 / 49 | 5056 | 46 | 2000 / 0 | yes | 554.380 / 333.168 |

For the 101/101 and 501/501 rows, the validation event breakdown is respectively
`200/200/100` and `1000/1000/500` for transition rows/re-verification rows/unique owner rows.

These are single-run elapsed observations, not a capacity benchmark or a query-count-only
performance claim. Global validation remains intentionally row-linear and is reported honestly;
draft graph
and evidence rows are excluded from published/withdrawn validation and scoped DTO materialization.
The validation event counts include every matching history row, while `workflow_owner_rows` is the
unique anchor-owner read used for owner resolution.
The generated workload is synthetic and does not replace imported-family acceptance coverage.
The complete raw result, including per-queryset counts and limitations, is preserved at
[`docs/operations/issue-119-loader-measurement-2026-09-09.json`](issue-119-loader-measurement-2026-09-09.json).
