# ADR 0014: Use Service as the production Procedure grouping

"
    "**Status:** Accepted  
"
    "**Date:** 2026-09-02

"
    "## Context

"
    "The frozen prototype calls the stable bilingual user-entry grouping of related Procedures a `Goal`. Production persistence and application design are now being implemented, and the entity's actual responsibility is a government-service catalog grouping rather than an abstract user objective. `Service` / `خدمة` is clearer and more natural in both English and Arabic, and it leaves `Goal` available for a future cross-service user-intent concept if one is ever needed.

"
    "The prototype is frozen and remains an executable reference. Renaming its code, fixtures, evidence packs, or historical terminology would create churn without changing the production contract.

"
    "## Decision

"
    "Production uses `Service` as the stable bilingual grouping and user-entry point for closely related Procedures. A Service owns its curated Procedure candidate set, Service Questions, and Service-owned contradiction/case-invariant definitions. Each Procedure has one primary Service in version 1. Service-specific selection remains independent from Procedure-Version applicability.

"
    "This is a terminology change, not a semantic change. A Service is not itself a concrete government transaction and does not own Procedure-specific requirements, fees, steps, routing, evidence, or Eligibility Bases. `Service Point` remains the distinct concept for a physical office or digital destination.

"
    "Production code, schema, API contracts, current architecture documents, and active production issues use `Service`. The frozen prototype and prototype evidence retain `Goal`. When comparing production behavior with the prototype, prototype `Goal` maps directly to production `Service`.

"
    "This ADR supersedes the production terminology of ADR 0008 and ADR 0013 while preserving their substantive decisions about grouping related Procedures and owning pre-selection Questions.

"
    "## Consequences

"
    "- Production model names use `Service`, `ServiceProcedureCandidate`, `ServiceQuestion`, and `ServiceContradiction`, with `primary_service` and `service_id` relationships.
"
    "- Public navigation can use Service / خدمة without translating an internal `Goal` concept for users.
"
    "- The word `Goal` is no longer consumed by the production catalog model and may later describe a genuine user intent spanning multiple Services if research proves that layer necessary.
"
    "- Historical ADRs and the frozen prototype may still contain `Goal`; those references are historical/reference terminology rather than the current production model.
"
    "- No planner truth semantics, candidate-selection behavior, publication rule, or evidence requirement changes as a result of this rename.
"
    