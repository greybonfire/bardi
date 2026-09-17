---
version: 1
slug: "backend-knowledge-templates-admin-knowledge"
primary_target: "backend/knowledge/templates/admin/knowledge"
related_targets: ["backend/knowledge/draft_pack_admin.py","backend/knowledge/static/knowledge"]
---

# Staff draft-pack workflow

Mode: Operate. Audience: a staff researcher preparing and reviewing administrative knowledge, initially one editor. Target: existing Django Admin, not the public applicant interface.

User approved a focused native Admin extension: upload → inspect actual changes and publication blockers → confirm draft import; stored-scenario previews on the draft page. Preserve all lifecycle actions and manual editing. No dashboard or free-form case simulator.

## Direction contract

**THESIS:** Make a proposed import inspectable before it writes. Avoid a separate CMS or decorative dashboard.

**OWN-WORLD:** Inherit Django Admin’s system typography, theme variables, breadcrumbs, modules, forms, tables and submit rows. Preserve light/dark theme behavior and native focus. No public-client rebranding.

**STORY:** Choose a file once, inspect additions/changes/deletions and trust consequences, explicitly save only the draft. Review blockers and bilingual scenario results without implying publication or approval.

**FIRST VIEWPORT:** Admin breadcrumbs and plain page heading; the explicit target and “not saved” status; retained file input and Inspect button. Inspection adds a clear change summary followed by expandable values, publication blockers and unchecked deletion consent before Confirm import. Draft tools expose downloads/readiness/scenarios without executing expensive checks on ordinary page loads.

**FORM:** Approved native Admin extension, not a new visual world; no concept seed needed. Progressive enhancement retains the file; without JavaScript, reselect the same file. Arabic preview is RTL, English LTR. Tables scroll locally on narrow screens.

**FINISH:** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

No shipping rasters or new fonts. DESIGN.md remains the public-client reference, unchanged. Acceptance: real upload/confirm controls, accessible errors/empty states, separated stale seals versus matches, safe escaped content, and desktop/mobile visual checks.

## Verification

Disposition: **SHIP** for the native Admin extension; evidence checked against the finished
pack/procedureversion templates, local CSS and incumbent Django Admin conventions. Existing
light-theme synthetic captures reviewed: [desktop inspection](../review/task3-desktop-inspection.png),
[mobile inspection](../review/task3-mobile-inspection.png),
[desktop scenario](../review/task3-desktop-scenario.png) and
[mobile scenario](../review/task3-mobile-scenario.png), at 1440px and 390px widths.
Native chrome, disclosures, advisory blockers, draft-only confirmation and Arabic RTL/English
LTR previews remain distinct from the public green interface. Browser JavaScript/no-JavaScript
passes are parent-reported, not rerun in this documentation handoff. No dark-theme or accessibility
certification is claimed. DESIGN.md and its preexisting stale sidecar remain untouched; no new
visual tokens, fonts or shipping rasters were introduced.
