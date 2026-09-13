# Snapshot validation follow-ups

The shared-policy refactor deliberately preserves request-loader behavior, including malformed
persisted-data handling. These findings are not fixes included in that refactor and do not
change the authoritative loader contract.

## Explicit routing association primary key zero

**Status:** Preserved legacy edge case; separate behavior-change review needed.

A Procedure–Service Point Association explicitly persisted with primary key `0` can be
published with otherwise valid material and claim-specific evidence, but its requested graph
fails to load with `invalid_routing_evidence`.

The routing materializer chooses the association family by checking whether its ID is non-null,
then historically indexes the Evidence Link using `association_id or material_id`. For an
association-only Evidence Link with association ID `0`, this indexes under `None` instead of `0`.
Global scalar validation uses the non-null ID. This difference does **not** make the scoped
public loader succeed when that association is in its requested graph: its later materializer
uses the same legacy fallback as the full loader. Both fail in the characterization fixture.

The fallback exists in baseline commit `95128e2` and remains explicit in
`backend/knowledge/service_point_routing.py`. Generated positive IDs are not affected.
No constraint, migration, data repair, or fallback correction is part of this consolidation.

The persisted-loader regression publishes through the normal publication interface and pins
both public errors independently:

```bash
# Export the local .env values and start PostgreSQL as described in docs/development.md.
(cd backend && uv run python manage.py test \
  knowledge.tests.test_service_scoped_snapshot.ServiceScopedSnapshotTests.test_routing_pk_zero_preserves_legacy_full_loader_failure \
  --settings=bardi.settings.test --noinput)
```

A future fix must explicitly decide how zero-valued IDs should behave and test both requested
and unrelated graph cases before changing this compatibility expectation.
