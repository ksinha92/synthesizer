---
phase: 48-shell-and-tokens
plan: 01
subsystem: frontend, layout
tags: [shell, design-tokens, top-nav, tab-bar, generate-data-cta]
requires: []
provides:
  - UX design tokens in globals.css (--dw-* CSS variables)
  - GlobalNavBar (dark) — Projects / Generator Presets / Sensitivity Rules / Admin
  - WorkspaceTabBar — Privacy Hub / Database View / Discovery / Masking / Synthetic / Subsetting / Workflows / Jobs / Compliance / Settings
  - GenerateDataButton split-button (5 verbs)
  - TopShell (sidebar replaced)
  - AppShell kept as a thin alias delegating to TopShell
affects: [49-privacy-hub, 50-database-view, 51-generator-presets, 52-sensitivity-rules, 53-recommended-generators, 54-destinations-vfk-schema-changes]
duration: ~20min
completed: 2026-05-16
---

# Phase 48 Plan 01: Shell Foundation

**Frontend tsc clean; dev server serves HTTP 200 across all existing routes.**

## Highlights
- **Design tokens** for the UX palette (`--dw-shell-*`, `--dw-tabs-*`,
  `--dw-brand`, `--dw-cta-*`, `--dw-pill-*`) added to `globals.css`
  under `:root`. Naming-prefixed so they don't collide with the existing shadcn tokens.
- **GlobalNavBar**: dark slate top bar (`hsl(var(--dw-shell-bg))`) with
  brand mark + Projects / Generator Presets / Sensitivity Rules / Admin links,
  command-palette trigger, help, AI assistant toggle, user menu.
- **WorkspaceTabBar**: project-scoped tabs styled with the UX tab palette,
  arrow-key navigation, `role="tablist"` + `aria-selected` semantics, sticky
  beneath the global bar.
- **GenerateDataButton**: gradient (teal → violet) split-button. Main click
  defaults to Generate Synthetic; caret opens the 5-verb dropdown
  (Discovery / Synthetic / Masking / Subset / Workflow) with Esc + click-outside
  close.
- **TopShell**: orchestrates the two bars + content + AssistantSidebar +
  OnboardingWizard. No sidebar. Uses `useAssistantStore.toggleOpen` to wire
  the global-nav assistant button.
- **AppShell**: now a 6-line alias that returns `<TopShell projectId={...}>`.
  Every existing page (page.tsx, projects/page.tsx, projects/[id]/layout.tsx,
  admin/page.tsx) migrates automatically because the import surface is
  unchanged.

## What did NOT change
- Page-level content remains visually identical inside the new shell.
- The legacy `sidebar.tsx` file is still on disk but no longer rendered — left
  for a later cleanup plan to delete cleanly.
- Theme provider, command palette, error boundary, toast container all
  unchanged.
- Backend untouched.

## Manual verification checklist
- [ ] Visit `/` — global bar visible, no sidebar; page renders.
- [ ] Visit `/projects` — same shell; no workspace tab bar.
- [ ] Visit `/projects/<id>` — tab bar appears with all 10 tabs.
- [ ] Click Generate Data caret — dropdown lists 5 verbs.
- [ ] Click any verb — navigates to the correct project sub-route.
- [ ] Switch theme (light/dark/system) — global bar stays dark; content
      reflects the user's theme.
- [ ] Tab arrow keys move focus left/right across workspace tabs.
- [ ] Cmd-K opens the command palette via the search button.

## Next plans in v0.8
- Phase 49: Privacy Hub at `/projects/[id]` landing.
- Phase 50: Unified Database View at `/projects/[id]/database`.
- Phase 51: Generator Presets table + drawer.
- Phase 52: Sensitivity Rules admin.
- Phase 53: Recommended Generators + linked-column consistency.
- Phase 54: Destination connections + virtual FKs + schema-changes diff.
- Phase 55: Final unify + quality gate.

---
*Phase: 48-shell-and-tokens, Plan: 01 — Completed 2026-05-16*
