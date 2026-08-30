# CI/CD

The repository uses GitHub Actions for continuous integration and conservative continuous delivery of the framework-independent prototype.

## Continuous integration

`.github/workflows/ci.yml` runs on:

- every pull request;
- every push to `main`;
- manual `workflow_dispatch` runs.

The workflow uses Ubuntu and tests Python 3.11, 3.12, and 3.13. Each matrix job:

1. checks out the repository;
2. installs the selected Python interpreter;
3. byte-compiles the `prototype/` tree;
4. runs the complete unittest suite with:

   ```bash
   python -m unittest discover -s prototype/tests -v
   ```

The workflow needs no repository secrets and has read-only repository permissions.

After this workflow is merged and has produced a successful check, `main` should be protected so the CI test job is required before merge.

## Continuous delivery

There is no production application or hosting target yet, so the repository does not pretend to deploy one. Instead, `.github/workflows/release.yml` provides a release-only delivery boundary for immutable prototype snapshots.

The release workflow runs only when a tag matching `prototype-v*` is pushed. For example:

```bash
git tag prototype-v0.1.0
git push origin prototype-v0.1.0
```

Before publishing anything, the workflow:

1. checks out the tagged commit;
2. uses Python 3.12;
3. byte-compiles the prototype;
4. reruns the complete unittest suite;
5. creates `bardi-<tag>.tar.gz` containing `README.md`, `CONTEXT.md`, `docs/`, and `prototype/`;
6. creates a SHA-256 checksum;
7. creates a GitHub Release from the existing tag and attaches both files.

The release job uses only the automatically provided `GITHUB_TOKEN` with `contents: write`. No external deployment credentials are required.

## Future production deployment

When the Django/PostgreSQL backend and deployable frontend actually exist, add deployment jobs behind an explicit GitHub Environment such as `staging` or `production`. Keep environment credentials scoped to that environment and preserve the same rule: tests must pass before deployment.

Do not overload the prototype release workflow with infrastructure assumptions before a deployment target is selected.
