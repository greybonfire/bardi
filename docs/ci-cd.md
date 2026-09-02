# CI/CD

The repository uses GitHub Actions for continuous integration and conservative continuous
delivery of the framework-independent prototype.

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request, every push to `main`, and manual
`workflow_dispatch` runs. It has two deliberately separate tracks:

- The frozen prototype matrix remains unchanged on Python 3.11, 3.12, and 3.13. Each
  version byte-compiles `prototype/` and runs the complete unittest suite.
- A separate Python 3.14 production-backend job runs against PostgreSQL 17. It installs
  only from the committed `uv.lock`, then runs Ruff lint and format checks, Mypy, compile
  checks, Django deploy checks, migration consistency checks, and whole-project
  PostgreSQL-backed Django test discovery. The production import-boundary test ensures
  backend code cannot import the frozen prototype.

Production CI intentionally uses the same Python runtime family as local production
backend development. The prototype matrix is historical reference coverage and does not
expand the supported production runtime surface.

The final `CI required` job depends on both tracks and succeeds only when both dependency
results are exactly `success`. This stable aggregate name is the branch-protection check;
it does not weaken or replace frozen prototype coverage.

The workflow uses read-only repository permissions. CI supplies explicit test-only
PostgreSQL credentials, a strong Django secret, allowed hosts, and a valid HTTPS CSRF
origin. No production credentials are committed.

After this workflow is merged and has produced a successful `CI required` check, protect
`main` and require `CI required` before merge.

## Continuous delivery

Release automation remains prototype-only. There is no production application deployment
in this issue. `.github/workflows/release.yml` provides a release-only delivery boundary
for immutable prototype snapshots; its checkout/runtime action versions are kept current,
but its release behavior is unchanged by the backend scaffold.

The release workflow runs only when a tag matching `prototype-v*` is pushed. For example:

```bash
git tag prototype-v0.1.0
git push origin prototype-v0.1.0
```

Before publishing anything, it checks out the tagged commit, uses Python 3.12, compiles
the prototype, reruns its complete unittest suite, packages `README.md`, `CONTEXT.md`,
`docs/`, and `prototype/`, and publishes the archive and SHA-256 checksum on a GitHub
Release using the existing tag.

When a deployable Django/Next.js application and hosting target exist, deployment jobs
can be added behind an explicit GitHub Environment. Issue #31 introduces no backend
deployment assumptions or credentials.
