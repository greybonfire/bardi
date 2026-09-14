# Production cross-family parity

**Status:** Acceptance contract for issue #53  
**Scope:** Passport renewal, National ID renewal, and temporary family exemption from military service

## Purpose

Production parity is proven through the production stack itself. The acceptance suite imports researched production records, publishes them through the production publication service, loads production snapshots, exercises the production planning domain, and verifies the public Django Ninja API contract.

The research prototype was retired from `main` after this coverage became authoritative. Its final executable state remains available in Git history at commit `95128e22767edf8ffb9f3db838178b327b079aa0`. CI runs the focused production acceptance suite explicitly; the remaining production backend tests run separately so the focused acceptance suite is not executed twice.

## Acceptance coverage

`backend/api/tests/test_cross_family_production_parity.py` proves the following across one published catalog containing all three researched Procedure families:

- all three active Services are exposed with stable Service IDs;
- Service-level selection reaches each researched Procedure;
- `next_question`, `plan`, `inconclusive`, and `invalid` are reachable for every Procedure family in both Arabic and English;
- locale changes preserve semantic identifiers, ordering, diagnostics, routing identities, Basis identities, and result families while allowing localized prose to differ;
- identical requests against the same catalog and evaluation date return identical public JSON;
- the passport version boundary is enforced at 2026-08-25;
- the military Law No. 2 of 2026 boundary changes behavior exactly between 2026-03-24 and 2026-03-25;
- the National ID three-calendar-month deadline preserves exact-date and month-end-clamping behavior;
- all six researched military Eligibility Basis branches are executable as non-ranked candidates;
- Service contradictions are rejected before selection where applicable;
- untrusted or candidate material does not unlock authoritative guidance;
- researched Giza, Mansoura, and Zagazig routing is asserted only where current production evidence supports it;
- unresolved National ID routing remains unresolved while retaining the sourced verification step;
- editorial Evidence Link fields are not projected through the public API.

## Intentional non-parity and unsupported behavior

Production does not copy prototype behavior merely to make outputs look identical. The following boundaries are intentional:

- **Passport renewal:** production models only ordinary domestic renewal/replacement for an expired or page-full passport. Outside-Egypt applications, other passport classes, first issuance, lost/damaged routes, or other unresearched branches remain unsupported rather than inferred.
- **National ID renewal:** production models ordinary domestic renewal of a held expired card with no recorded-data change. First issuance, lost/damaged cards, changed-data routes, and outside-Egypt handling remain separate or unsupported. The ordinary fee is explicitly unknown, and no nationwide office mapping is invented.
- **Temporary family exemption:** production preserves six researched family Bases as `needs_reverification` candidates rather than treating them as binding eligibility decisions. The incapable-brother wording remains unresolved beyond the researched father-support sub-route. Only the researched Giza, Mansoura, and Zagazig jurisdiction mappings are asserted; there is no nearest-office, ranking, or nationwide-routing inference.
- **Historical military evaluation:** material first verified or retrieved on 2026-08-26 is not backdated into March 2026. Historical planning therefore fails closed for routing and question behavior that would require future evidence, even when a historical Procedure Version exists.
- **Retired prototype implementation details:** historical prototype dataclasses, loaders, internal traces, helper abstractions, and serialization shapes are not production contracts. Production parity is semantic and API-level, not an implementation clone.

These differences are deliberate evidence and product boundaries, not missing parity work.
