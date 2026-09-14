# Bardi

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js web application with TypeScript, consuming the existing Django Ninja public interface. Django and PostgreSQL own knowledge, publication, and deterministic planning. See the accepted [architecture](docs/architecture/README.md).

## Users

Applicants preparing their own Egyptian administrative paperwork and family members helping them. The user confirmed that the initial experience should work particularly well on a phone, with clear questions, practical plans, and visible uncertainty. Professional case-management workflows are not the initial priority.

## Product Purpose

Help someone prepare for an administrative attempt without preventable missing requirements. The product returns sourced guidance for supported circumstances, not a government decision or a guarantee of completion.

## Positioning

Bardi asks only consequential source-circumstance questions, then assembles reliable guidance from immutable, researched Procedure Versions. It preserves local uncertainty instead of guessing an answer, amount, qualification, or destination.

## Operating Context

A visitor chooses a Service, answers the questions returned by Django, and reviews the resulting plan or explicit limits. Answers can be corrected and the current facts resubmitted. A plan should be regenerated immediately before acting. The initial browser client is bilingual and Arabic-first.

## Capabilities and Constraints

- Implement the complete public client: Service pages, questionnaire, every public result family, and every plan section.
- Preserve the API's authored question and guidance text verbatim in the requested locale. The frontend must not implement administrative rules or infer a closest match.
- Keep in-progress source Facts in tab-scoped browser storage only. No accounts, saved server Cases, uploads, analytics, or third-party error reporting.
- Keep Facts out of URLs, cookies, localStorage, server caches, logs, and metadata.
- Show official requirements separately from practical preparation. Display compact sources, freshness, unknown fees, non-ranked Eligibility Bases, prerequisites, and unresolved routing honestly.
- Deployment topology is undecided; the existing interface assumes same-origin or reverse-proxied access. Do not introduce a paid dependency or deploy infrastructure.
- The architecture and accepted ADRs remain authoritative over this product summary.

## Brand Commitments

The name is Bardi / بردي. The user chose conversational Egyptian Arabic for frontend interface copy, with precise formal administrative terms. Backend-authored bilingual content is not rewritten into a different register. English remains fully supported. The user selected a familiar conversational-helper experience, with GOV.UK and NHS as clarity and accessibility benchmarks, not government branding to copy. No existing visual identity or approved logo is present in the repository.

## Evidence on Hand

- [Public interface](docs/api/v1.md) and `backend/api/schemas.py` define the available data.
- `docs/evidence-packs/` and production importers cover researched passport renewal, National ID renewal, and temporary family exemption families. Their research limitations must remain visible.
- The frozen prototype is reference material, never a production dependency.
- There are no verified public testimonials, success metrics, commercial claims, or photography assets to invent.

## Product Principles

1. Make the next useful action obvious, especially on a small screen.
2. Show the source and limit of guidance, not an unsupported promise.
3. Let the applicant correct circumstances without exposing or saving a server Case.
4. Treat Arabic and English as equal functional experiences, including RTL layout and accessible controls.
5. Preserve terminology and deterministic backend decisions rather than duplicating them in the UI.
