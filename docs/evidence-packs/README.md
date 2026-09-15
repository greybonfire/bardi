# Evidence packs and renewal-baseline retention

Documentation organization and retention reassessed: **2026-09-14**.
Administrative evidence below retains its original research dates; this reassessment is not a
new source-verification pass, publication approval, or database migration.

## Separate research packs

| Family | Current expansion research | Existing implementation baseline |
| --- | --- | --- |
| Passport | [Passport suite](passport-suite/README.md) | [Passport renewal](passport-renewal/README.md), researched 2026-08-25 |
| National ID | [National ID suite](national-id-suite/README.md) | [National ID renewal](national-id-renewal/README.md), researched 2026-08-26 |
| Temporary family exemption | [Existing evidence pack](temporary-family-exemption/README.md) | Unchanged by this reorganization |

The two suites have separate administrative documentation and implementation workstreams.
A passport's identity prerequisite may link to a specific National ID claim or transaction;
it does not merge the two catalogs. The [shared catalog-compatibility prerequisite](catalog-compatibility.md)
is infrastructure work, not a consolidated administrative research pack.

## Decision: no blanket requirement for frozen Markdown snapshots

Do not treat `national-id-renewal/` and `passport-renewal/` as permanent immutable Markdown
archives merely because newer research exists. Git history already preserves their earlier
contents. New research belongs in the respective suite, rather than in two competing current
renewal guides. Corrective annotations and navigation changes to the older documentation do
not themselves mutate a published knowledge record.

Retain the older packs **for now as implementation baselines**, not as newly verified guidance.
The production importers still transcribe their dated contents; this documentation-only PR
neither implements nor publishes replacement versions. Their claim-to-evidence mappings,
unsupported-case boundaries and scenario rationale still explain executable behavior. This is
a maintainability/review reason for temporary retention, not a claim that runtime parses the
Markdown files or that the new research has already superseded deployed versions.

| Artifact | Treatment |
| --- | --- |
| Existing renewal Markdown packs | Keep while they explain the supported dated imports; do not require indefinite frozen copies. Reassess for retirement after successor rollout. |
| Dated importer IDs, strict integrity checks and regression fixtures | Keep reproducible while those imports remain supported. Changing a documentation link is not grounds to refresh signatures or weaken drift detection. |
| Published/withdrawn Procedure Versions, their Source/Evidence Link provenance, approvals and audit history, if present in a database | Preserve under the existing publication lifecycle. A newer research document does not authorize overwriting or deleting these records. Git is not a replacement for the database audit trail. |
| Unpublished drafts or abandoned experiments | No automatic permanent-history requirement. Cleanup/rebuild is a separate explicit editorial operation subject to actual references and lifecycle rules; this PR deletes no records. |

The retained baseline IDs are
`ordinary_domestic_passport_renewal.research-2026-08-25` and
`ordinary_domestic_national_id_renewal.research-2026-08-26`. See the actual
[passport importer](../../backend/knowledge/importers/passport_renewal.py),
[National ID importer](../../backend/knowledge/importers/national_id_renewal.py), and
[renewal API regression](../../backend/api/tests/test_national_id_renewal.py).
These are repository implementation records; this review has not inspected a deployed database.

## Known baseline limitations still requiring action

The 2026-09-12 passport research found that the old `PPAr.htm` locator serves a privacy policy.
That finding is not proof of what the locator served in August, nor permission to assert it as
current passport evidence. Follow [D01](passport-suite/claims.md#d01) and the bounded
[passport provenance task](passport-suite/implementation.md#p-i01) before using corrected
provenance in a new authoritative version; assess any affected existing publication through the
normal discrepancy/withdrawal workflow. Retaining a baseline does not endorse its freshness.

The National ID importer intentionally withholds `nid.requirement.previous_card` and keeps the
ordinary fee and exact routing unknown. New channel-scoped old-card evidence does not silently
change that baseline. Follow the [National ID renewal task](national-id-suite/implementation.md#n-i05),
including the unresolved marriage-document condition and current-law review.

## When the old Markdown can leave the active tree

Retire each renewal pack independently, after its replacement has been reviewed and rolled out,
its still-useful evidence explanations and regression requirements have a maintained home,
and live documentation/importer/test references have been checked. Record the last containing
commit and the replacement location; use Git history for obsolete prose instead of a permanent
parallel archive. Do not remove functioning importers or their test coverage merely to tidy docs.
Any retirement of a public import command needs its own supported-use and compatibility decision.

This is a bounded follow-up, not a blocker requiring the two entire suites to finish together.
The [editorial process](../editorial-process.md) and
[publication design](../architecture/knowledge-publication.md) remain authoritative.
