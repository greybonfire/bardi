---
name: Bardi
description: Arabic-first, bilingual paperwork guidance in a familiar conversational-helper interface.
colors:
  accent: "#215c50"
  accent-hover: "#174a3f"
  accent-active: "#10392f"
  ink: "#20362f"
  muted: "#4f665c"
  paper: "#ffffff"
  tint: "#eff5f2"
  tint-active: "#dcebe3"
  line: "#c7d8cf"
  detail-line: "#b7cfc3"
  control-line: "#77958a"
  focus: "#a54917"
  error-line: "#963d29"
  error-text: "#873522"
typography:
  body-ar:
    fontFamily: '"Noto Sans Arabic", "Source Sans 3", sans-serif'
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.75
  body-en:
    fontFamily: '"Source Sans 3", "Noto Sans Arabic", sans-serif'
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.75
  display:
    fontSize: "clamp(2rem, 3.3vw, 3.25rem)"
    fontWeight: 700
    lineHeight: 1.45
  headline:
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.55
  question:
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.6
  plan-headline:
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.5
  plan-subheading:
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.6
  lead:
    fontSize: "1.3rem"
    fontWeight: 400
    lineHeight: 1.85
  body-small:
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.75
  button:
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.6
rounded:
  text-action: "0.125rem"
  control: "0.375rem"
  note: "0.5rem"
spacing:
  compact: "0.5rem"
  inline: "0.75rem"
  stack: "1rem"
  roomy: "1.25rem"
  group: "1.5rem"
  section: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.paper}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0.65rem 1.4rem"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
    textColor: "{colors.paper}"
  button-primary-active:
    backgroundColor: "{colors.accent-active}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.accent}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0.65rem 1.4rem"
  button-secondary-hover:
    backgroundColor: "{colors.tint}"
  button-secondary-active:
    backgroundColor: "{colors.tint-active}"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.accent}"
    rounded: "{rounded.text-action}"
    padding: "0.5rem 0"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0.5rem 0.75rem"
  radio-choice:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0.75rem 1rem"
  radio-choice-selected:
    backgroundColor: "{colors.tint}"
  notice:
    backgroundColor: "{colors.tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "1.25rem 1.5rem"
  service-row:
    textColor: "{colors.accent}"
    padding: "1.4rem 0.25rem"
  navigation:
    textColor: "{colors.accent}"
    typography: "{typography.body-small}"
  evidence-disclosure:
    textColor: "{colors.accent}"
    typography: "{typography.body-small}"
---

# Design System: Bardi

## Overview

**Creative North Star: "The familiar conversational helper"**

A clear, spacious green-and-white interface for applicants and family helpers preparing Egyptian paperwork. Humanist Arabic and Latin type, ordinary controls and direct language support completing the task, not selling the product. GOV.UK and NHS are the user-chosen clarity and accessibility quality bar, not branding to reproduce.

Recorded on **2026-09-12** from the implemented CSS, font imports and components, not browser-computed measurements. This is a code-led world with no approved comp or style-benchmark images. The bilingual text wordmark is not an approved logo asset; the shipped art is limited to an authored, decorative 24px arrow SVG. Fontsource WOFF/WOFF2 files are fonts, not rasters; no shipping raster assets require provenance.

**Key Characteristics:**
- One clear question and useful next action, without chat simulation.
- Arabic-first reading and controls, with a complete English experience.
- Visible sources and uncertainty, with official requirements distinct from practical preparation.

Authority: [PRODUCT.md](PRODUCT.md) preserves product and voice decisions; the [surface brief](.impeccable/surfaces/frontend-src-app.md) owns route strategy and review scope. [Accepted ADRs and production architecture](docs/architecture/README.md) govern semantics, privacy and the Next.js/Django boundary. This reference does not redefine planning rules.

The frontmatter records reused source values, including repeated CSS literals rather than claiming a centralized token library. The [sidecar](.impeccable/design.json) adds component previews, focus/state CSS, motion and breakpoints; it does not introduce an unshipped tonal scale. Keep both aligned with the source paths below.

## Colors

Restrained deep green carries interaction on white, with pale green for supporting information and state.

### Primary
- **Deep green** (`accent`): actions, links, selected controls and the masthead rule; `accent-hover` and `accent-active` deepen real interaction states.

### Neutral
- **Green ink / muted green** (`ink`, `muted`): content and secondary explanations, not disabled-state substitutes.
- **White / pale green** (`paper`, `tint`): page ground and notes; `tint-active` is a pressed-state fill.
- **Quiet rules** (`line`, `detail-line`): shell and plan/questionnaire separators. **Control stroke** (`control-line`) distinguishes editable fields.

Focus and errors are functional exceptions: `focus` is the shell's warm focus outline; `error-line` and `error-text` identify validation with accompanying text. Questionnaire and plan focus use `ink`, not the shell outline color. See [global styles](frontend/src/app/globals.css), [questionnaire styles](frontend/src/planning/questionnaire.css) and [plan styles](frontend/src/components/plan-view.css).

**The Visible Uncertainty Rule.** State the limit beside the affected guidance; green styling is never evidence of approval or completion.

## Typography

The locale selects the body stack above; headings and controls inherit it, with no separate display face. [The locale layout](frontend/src/app/[locale]/layout.tsx) imports Fontsource Noto Sans Arabic's Arabic subset and Source Sans 3's Latin subset at **400, 600 and 700**, normal style, with `font-display: swap`. Global CSS disables font synthesis.

The frontmatter supplies the principal size/weight/line-height roles: display for page titles, headline for shell sections, question for the current prompt, plan-headline and plan-subheading for reading hierarchy, lead for introductions, and body-small for metadata and hints. Labels, selected choices, plan item titles and language switching use **600**; body text uses **400**; headings and important warnings use **700**. This is an observed role ramp, not a fixed-ratio scale.

Source-specific adjustments stay local: questionnaire page titles use `clamp(1.7rem, 3vw, 2.25rem)` with the display line-height; global third-level headings use `1.2rem` / `1.75`, questionnaire third-level headings `1.125rem` / `1.75`. At widths up to `30rem`, the body and inherited controls become `1.0625rem` and general page titles `2rem`; the plan retains its explicit `1.125rem` body. The global lead shrinks to `1.15rem`, while the service introduction's more-specific lead remains `1.2rem`.

**The Two Registers Rule.** Write frontend interface copy in conversational Egyptian Arabic with precise administrative terms, and provide full English equivalents; render backend-authored text verbatim in the requested locale.

Use `lang` and `dir` on the document and planning surface, logical spacing, and start alignment. Arabic headings have zero tracking; Latin page titles use `-0.025em`. Preserve authored line breaks with `white-space: pre-wrap`; isolate mixed-script values with `bdi`/`dir="auto"`. Gregorian date controls and dates remain LTR; displayed quantities use locale formatting and tabular numerals. [Site copy](frontend/src/lib/site.ts), [questionnaire copy](frontend/src/planning/copy.ts) and [PlanView](frontend/src/components/plan-view.tsx) are the wording sources.

## Layout

A centered shell (`min(100% - 3rem, 72rem)`) holds the masthead, main content and footer. Reading and questionnaire pages narrow to `48rem`; questionnaire and plan content also cap at `75ch`. Reused spacing steps are in frontmatter; this is not a strict grid imposed on every value.

The current directory pairs continuous service-link rows with a supporting guidance note (`1.7fr / 1fr`), becoming one column at `48rem`. At `30rem`, shell gutters become `1rem` per side and the redundant services header link hides; the language switch remains. Questionnaire actions fill the width and plan metadata stacks at `35rem`; the plan's in-page section index uses two columns from `40rem`. These are CSS breakpoints, not a cross-browser verification claim.

The current task topology is service selection → service introduction → questionnaire → sourced plan or explicit limits. Privacy and date disclosures precede the current question/result; answer review and case tools follow it. Service composition stays in [the surface brief](.impeccable/surfaces/frontend-src-app.md), not a universal layout mandate.

## Elevation & Depth

Flat at rest: no shadows, gradients or simulated physical materials. Whitespace, borders and pale-green fills group information. Native disclosures provide progressive detail without nesting the plan inside decorative cards.

Motion only changes background color: buttons and service rows use `160ms cubic-bezier(0.16, 1, 0.3, 1)`; the question/result stage uses `180ms ease-out`. Both transitions exist only under `prefers-reduced-motion: no-preference`. Content is visible without entrance animation.

## Shapes

Understated corners: controls, choices and notices use `rounded.control`; the supporting guidance note uses `rounded.note`; text actions use `rounded.text-action`. Ordinary separators and control borders are `1px`; invalid text inputs have a `2px` error border. Native radios stay circular. The shell's horizontal `5px` green masthead rule is an existing signature, not a side stripe.

## Components

- **Navigation and service rows:** a bilingual text wordmark, services link and language switch, followed by ordinary linked lists rather than service cards. Links underline by default; service rows use a tinted hover and underline their text on hover. [SiteHeader](frontend/src/components/site-header.tsx) and [ServiceDirectory / Arrow](frontend/src/components/service-directory.tsx) own these patterns. The arrow is `aria-hidden` and rotates for RTL; it never replaces a text label.
- **Buttons and notes:** solid primary, outlined secondary and underlined text actions. Filled/outlined buttons have a `3.1rem` minimum height; text actions and disclosure summaries use `2.75rem`. Disabled controls retain their label and use opacity `0.65` with a not-allowed cursor. Notes group explanations or recoverable states; they are not a general card library. See global and questionnaire CSS for padding and responsive variants.
- **Forms:** [QuestionForm](frontend/src/planning/question-form.tsx) uses a labelled form, fieldsets/legends, native radios for boolean/enum choices, text inputs for string/integer answers and native dates. Choices and inputs have a `3rem` minimum height. Full choice rows are clickable; selection adds a pale fill, accent border and semibold label. No answer is selected for the visitor. Omission is distinct from No or empty text; instructions and validation must retain that distinction. The backend's current Question determines the fields, not frontend administrative logic.
- **Focus and errors:** keep the skip link, semantic headings and visible outlines. Shell focus is `3px` with `4px` offset; planning/plan focus is `3px` ink with `3px` offset. Question validation focuses a linked error summary, connects field hints/errors with `aria-describedby`, and sets `aria-invalid`; color alone is insufficient. [Questionnaire](frontend/src/planning/questionnaire.tsx) focuses the new result stage after resolution. Changing an earlier answer removes it and downstream Facts before requesting the next consequential Question; [state.ts](frontend/src/planning/state.ts) owns that correction behavior.
- **Recovery and privacy:** keep next-Question, Plan, inconclusive and invalid results distinct. Use explicit loading/status messages, sanitized failures and manual retry, respecting retry delays without automatic resubmission. Keep the no-JavaScript recovery and inline clear confirmation. [Storage](frontend/src/planning/storage.ts) retains one tab-scoped case's submitted Facts, service, date and answer order, never the plan; memory-only and failed-clear states explain their limits. Do not promise that closing a tab deletes data. [Privacy](frontend/src/app/[locale]/privacy/page.tsx) and [the error boundary](frontend/src/app/[locale]/error.tsx) are the source patterns; never expose Facts through URLs, logs, metadata or error reporting.
- **Preparation plan:** [PlanView](frontend/src/components/plan-view.tsx) provides an indexed reading document covering warnings, direct prerequisites, checklist, steps, fees, Eligibility Bases and routing. Separate official requirements from practical preparation. Keep freshness visible beside each applicable claim; sources and reference details use native disclosures. Unknown/non-current fees are not amounts or zero totals; Bases and destinations are not ranked recommendations. Local uncertainty and honest empty sections remain visible without hiding unrelated reliable guidance. Link back to the authoritative contracts rather than reimplementing these semantics.
- **Print:** browser printing hides shell navigation, question/review controls and the plan index. A non-collapsible print copy preserves sources and metadata even when screen disclosures are closed; reminders and local limits remain. Global print uses `16mm` page margins, `10.5pt` body and `18pt` page titles; the plan uses `11pt` body and `10pt` evidence. Print CSS discourages splitting items and separating headings from content, but does not promise identical pagination across engines. Warn that printed/PDF copies may contain personal information and are not erased by clearing the tab case.

## Do's and Don'ts

### Do:
- **Do** preserve locale direction, native controls, visible focus and reduced-motion behavior.
- **Do** keep authored guidance exact, sources discoverable and uncertainty adjacent to the affected content.
- **Do** reuse the code-backed roles and patterns here; update this reference and its sidecar together when an approved system change ships.

### Don't:
- **Don't** turn the task client into marketing, simulated AI chat or government-branded UI.
- **Don't** imply approval, complete coverage, known fees or guaranteed completion from an unanswered or unresolved state.
- **Don't** add invented assets, tonal scales, saved-case promises or performance/accessibility certification claims to this reference.
