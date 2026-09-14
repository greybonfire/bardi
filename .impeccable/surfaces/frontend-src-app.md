---
version: 1
slug: "frontend-src-app"
primary_target: "frontend/src/app"
related_targets: ["frontend/src/components"]
---

# Frontend

Primary target: frontend/src/app
Related targets: frontend/src/components
Mode: Operate for service selection and questionnaire; Read for the plan.

Applicants and families should choose an available Service, answer only Django's current Question, correct previous answers, and understand both reliable guidance and its limits. Arabic-first, conversational Egyptian interface copy, exact authored administrative content, full English support. GOV.UK and NHS are the user-confirmed clarity and accessibility benchmarks, not branding to copy.

## Direction contract

THESIS: A conversational helper, not AI chat: one clear question and one useful next action. Refuse promotional heroes, simulated progress, and a grid of decorative service cards.

OWN-WORLD: Restrained deep green (#215c50), ink green (#20362f), pale green (#eff5f2), and white; plain humanist Arabic and Latin type, continuous service-link rows, spacious radio choices, understated rounded controls, and no chat-avatar fiction.

STORY: Choose a Service, answer source circumstances, review and correct answers, then read a sourced preparation plan. Uncertainty stays visible and never looks like completion.

FIRST VIEWPORT: Compact bilingual-switch masthead, a short human introduction, and the available service list as the main action. The questionnaire has a narrow reading column with the authored question and large choices; answer review is secondary. Signature interaction: correcting an earlier answer returns focus to the consequential question and discards downstream answers. State transitions use a short background-color change, not theatrical entry motion; reduced motion is respected.

FORM: Conversational helper, grounded candidate 6 (familiar phone conversation flow), selected by the user in the safer re-roll, seed 476034e2. Code-led; no image-generation tool is available. It uses familiar GOV.UK/NHS-quality forms rather than an invented interaction grammar.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Finish handoff — 2026-09-12

- **Review scope:** the public client in `frontend/src/app`, `frontend/src/components` and `frontend/src/planning`. The parent reports a fresh isolated finish review with `disposition: ship`, all five sections (`persistence`, `fidelity`, `ceiling`, `material_fixes`, `keep`) and no material fixes. The final technical review is reported **PASS**, with all three findings closed. The optional top-of-plan answer-review jump was advisory, not required and not implemented.
- **Reported verification:** 504 unit tests and 74 browser tests passed, along with frontend lint, types and build; one valid six-capture batch and detector result `[]`. These are parent-reported results, not checks rerun or captures inspected by this documentation pass. They do not establish a cross-browser matrix or performance/accessibility certification.
- **Documentation:** root `DESIGN.md` and `.impeccable/design.json` now record the implemented palette, type, layout and component patterns. The named documenter was unavailable in this Pi distribution, so the installed degraded documenter role ran inline. `PRODUCT.md` and the direction contract above remain unchanged.
- **Assets and authority:** code-led, with no approved comp or style-benchmark images. GOV.UK/NHS remain the user's quality bar, not government branding. Fontsource assets are font files; the decorative 24px arrow is authored SVG code. There are no shipping rasters needing provenance.
- **Limits and delivery:** this handoff inspected source CSS, font imports and component behavior only; it made no frontend changes and ran no browser, screenshot, detector, rebuild or application-test pass. Review/documentation are complete at the stated scope; the parent-owned full backend gate is still pending/running. No staging or commits are part of this handoff.
