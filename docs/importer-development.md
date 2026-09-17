# Developing deterministic editorial importers

**Audience:** Developers supporting reviewed, code-backed research imports

For ordinary editing use the [editorial workflow](editorial-process.md); for generic JSON use
[draft packs](draft-packs/README.md). A custom importer is useful when reviewed research must be
constructed reproducibly and checked exactly across environments. It is not an alternate
publication path. Follow the [production contracts](architecture/README.md), especially
[publication](architecture/knowledge-publication.md), [review policy](architecture/procedure-version-review-roles.md)
and [Admin authorization](architecture/django-admin-lifecycle.md).

## Existing examples

The development guide owns commands and fixture-specific research limits for
[passport renewal](development.md#passport-renewal-knowledge-import-and-review),
[national-ID renewal](development.md#national-id-renewal-knowledge-import-and-review), and
[temporary family exemption](development.md#temporary-family-exemption-knowledge-import-and-review).
Each uses a real staff `--author`, distinct from the generic draft-pack CLI's `--actor`.

Read the matching modules under `backend/knowledge/importers/`, their `*_integrity.py` verifiers,
and thin commands under `backend/knowledge/management/commands/` before extending this pattern.
The temporary-family-exemption importer returns multiple versions; do not assume all importers
have a single-version return shape.

## Rules for a new importer

A production importer should be:

- **deterministic** — identical researched input produces identical semantic state;
- **idempotent** — reruns verify/return intended rows rather than duplicate them;
- **atomic** — writes and final integrity verification succeed or roll back together;
- **fail-closed** — reject unexpected existing semantic drift rather than overwrite it;
- **actor-accountable** — use a real saved staff author;
- **draft-only** — never manufacture approvals or publication;
- **evidence-preserving** — construct explicit Sources and claim-specific evidence; and
- **contract-aware** — use current production models/services, not raw SQL or retired prototype shapes.

The public importer owns the outer atomic importer-plus-verifier boundary. For a single-version
importer, the pattern is:

```python
@transaction.atomic
def _import_example(*, author: models.Model) -> ProcedureVersion:
    # Create or verify the researched draft and related records.
    ...
    return version


@transaction.atomic
def import_example(*, author: models.Model) -> ProcedureVersion:
    version = _import_example(author=author)

    from .example_integrity import verify_example_import

    verify_example_import(version)
    return version
```

Run the verifier exactly once on every public invocation, including idempotent existing-row paths.
Verification failure must roll back the entire call. Test both first import and rerun, semantic
drift rejection, and rollback when the verifier fails.

## Add a management command

Keep argument handling thin:

1. Require `--author`.
2. Resolve an existing staff user; reject unknown/non-staff authors.
3. Call the public importer, not its private construction helper.
4. Print the resulting semantic ID/state.

Domain construction and verification belong in importer/integrity code, not the command.

## Direct importer use

A Django-aware script or shell can resolve the real author and call the same public entry point:

```python
from django.contrib.auth import get_user_model
from knowledge.importers.passport_renewal import import_passport_renewal

author = get_user_model().objects.get(username="editor", is_staff=True)
version = import_passport_renewal(author=author)
print(version.semantic_id, version.state)
```

Prefer management commands for routine operations: they are easier to reproduce and audit.
Never use one-off ORM `.update()` calls to bypass validation, immutability or publication services.

## Lifecycle services and authorization

Canonical lifecycle functions include `approve_review_dimension()`, `approve_specialist_risk()`,
`publish_procedure_version()`, `withdraw_procedure_version()`, `record_evidence_reverification()`
and `clone_published_procedure_version()`.

These preserve domain and transactional invariants, but custom tooling still needs an explicit
authorization boundary around who may invoke them. Django Admin supplies that boundary and is the
preferred staff interface. Do not call services under a generic superuser to bypass review mode,
specialist independence or permissions. Solo author/publication uses normal permission-controlled
operations, not a superuser workaround. Future bulk-editor tools must use the canonical services
rather than reimplement transitions.
