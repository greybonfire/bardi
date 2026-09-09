# Architecture Decision Records

ADRs record production decisions that should not be silently changed by implementation convenience. Unless an ADR explicitly says otherwise, the records below are **Accepted**.

Older ADRs predate the structured Status/Context/Decision/Consequences template; their decisions remain accepted.

## Accepted decisions

| ADR | Decision |
| --- | --- |
| [0001](0001-preserve-published-evaluation-semantics.md) | Preserve published evaluation semantics and immutable Fact meaning. |
| [0002](0002-use-claim-level-evidence.md) | Attach evidence to material semantic administrative claims. |
| [0003](0003-publish-coherent-procedure-versions.md) | Publish coherent immutable Procedure Versions. |
| [0004](0004-do-not-persist-case-facts.md) | Do not persist Anonymous Case Facts in version 1. |
| [0005](0005-use-nextjs-with-django-ninja.md) | Use a Django/PostgreSQL modular monolith, Django Ninja interface, and Next.js web client. |
| [0006](0006-expose-one-stateless-planning-operation.md) | Expose one stateless planning operation and keep internal authoring structures private. |
| [0007](0007-store-claims-relationally-and-rules-as-json.md) | Store typed claims relationally and rule ASTs as validated JSONB. |
| [0008](0008-use-goals-to-group-related-procedures.md) | Historical `Goal` terminology for the stable Procedure grouping; production naming is superseded by ADR 0014. |
| [0009](0009-separate-eligibility-basis-reachability-and-qualification.md) | Separate Eligibility Basis reachability from qualification. |
| [0010](0010-separate-service-point-identity-version-and-association.md) | Separate Service Point identity, material versions, and Procedure associations. |
| [0011](0011-keep-planning-engine-independent-of-django-orm.md) | Keep the planning engine independent of Django ORM/request objects. |
| [0012](0012-freeze-prototype-as-executable-reference.md) | Freeze the prototype as an executable reference, not a production dependency. |
| [0013](0013-own-planning-questions-at-goal-level.md) | Author planning Questions on the stable Procedure grouping so they are available before Procedure selection; current production name: Service. |
| [0014](0014-use-service-as-production-procedure-grouping.md) | Use Service / خدمة as the production name for the stable Procedure grouping; keep Goal only in the frozen prototype and historical records. |
| [0015](0015-ask-source-questions-for-version-applicability.md) | Ask consequential source Questions for UNKNOWN Procedure Version applicability; preserve pinned rule meaning and published content. |
| [0016](0016-ask-source-questions-for-checklists-and-steps.md) | Ask source Questions for usable official checklist and step applicability; preserve blocked research uncertainty. |

## Adding or superseding an ADR

Use the next numeric identifier. Include Status, Date, Context, Decision, and Consequences. If a new decision replaces an older ADR, name the superseded ADR explicitly rather than editing history to make the old decision disappear.
