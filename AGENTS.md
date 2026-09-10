# Bardi

Run commands from the repository root unless noted otherwise.

## Commands

- Requirements: Python 3.14+, `uv`, Docker Compose, and PostgreSQL. SQLite is not supported.
- Setup, server startup, teardown, and complete checks: [`docs/development.md`](docs/development.md).
- Fast planning tests (no database):
  ```bash
  (cd backend && uv run python -m unittest discover -s planning/tests -v)
  ```
- One planning test module:
  ```bash
  (cd backend && uv run python -m unittest planning.tests.test_evaluator -v)
  ```
- One Django test module (requires PostgreSQL and exported `.env` values):
  ```bash
  (cd backend && uv run python manage.py test api.tests.test_application --settings=bardi.settings.test)
  ```

## Coding conventions

Prioritize clarity and maintainability. Apply SOLID where it clarifies responsibilities and interfaces; KISS/YAGNI to meet current requirements without speculative machinery; DRY for shared domain knowledge, not merely similar code. Follow existing project patterns and prefer a little duplication over premature abstraction.

## Read when relevant

- Changing production behavior or contracts: read [`docs/architecture/README.md`](docs/architecture/README.md) and the relevant accepted ADRs in [`docs/adr/README.md`](docs/adr/README.md).
- Naming or modeling domain concepts: consult [`CONTEXT.md`](CONTEXT.md).

## Git and operations

- Preserve unrelated working-tree changes. Do not commit or push unless explicitly requested.
- Do not deploy, run production migrations, or change hosted infrastructure unless explicitly requested.
- Do not use destructive history or worktree operations (`reset --hard`, `clean`, `commit --amend`, `rebase`, force-push, or branch deletion) without explicit authorization.
- Before committing, inspect `git status` and the relevant diff, then stage only specific paths with `git add <path>`; never use `git add .` or `git add -A`.
