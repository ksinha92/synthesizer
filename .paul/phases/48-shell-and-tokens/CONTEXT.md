# Phase 48 Context — Shell + Design Tokens (v0.8 kickoff)

> Discuss-phase output. This document is the handoff into `/paul:plan` for
> Phase 48 of a proposed new milestone **v0.8 — UX Refactor**.

## Vision

Adopt the enterprise-TDM-aligned visual + interaction system as DataWrangler's
default chrome and key workflow surfaces, **without removing any feature
shipped through v0.7**. Enterprise-TDM tools are the recognized enterprise TDM UX in the
market; aligning DW with that pattern shortens the perceived learning curve
for QA / dev users coming from Enterprise-TDM tools and elevates DW's polish without
rebuilding capability we already have.

Supporting references in `docs/`:
- `UX-DESIGN-GUIDE.md` — visual system, layout patterns, interaction rules
- `UX-FEATURE-MAPPING.md` — every UX concept ↔ DW concept, gap list,
  rename table, proposed migrations

Phase 48 is the **foundation chrome** that subsequent v0.8 phases build on.
It is intentionally scoped narrow so later phases can ship feature work
against a stable shell.

## Goals (Phase 48)

1. **Two-bar app shell**: dark global bar (Projects · Generator Presets ·
   Sensitivity Rules · Settings · search · help · user · AI assistant
   trigger) + workspace tab bar (Privacy Hub · Database View · Discovery ·
   Masking · Synthetic · Subsetting · Workflows · Jobs · Compliance ·
   Settings) with a right-pinned **Generate Data ▾** primary action.
2. **Design tokens & primitives**: Tailwind theme tokens for the UX color
   palette, typography scale, compact table density. New common components:
   `TopShell`, `ContextDrawer`, `StatusPill`, `ConfidencePill`, `LinkedChip`
   (see Design Guide §4).
3. **Migration of existing screens to the new shell**, behavior-preserving.
   Every screen still works; only chrome/layout changes. Sidebar
   (`app-shell.tsx`) is replaced; routes are unchanged.
4. **Standardize on the right-side drawer** for column / generator /
   connection edits. Replace any remaining full-screen modal config flows.

Out of scope for Phase 48 (deferred to later v0.8 phases):
- Privacy Hub dashboard (Phase 49).
- Database View unified surface (Phase 50).
- Generator Presets backend + UI (Phase 51).
- Sensitivity Rules admin UI (Phase 52).
- Recommended Generators bulk apply + linked-column consistency (Phase 53).
- Destination connections / virtual FKs / schema-changes diff (Phase 54).

## Approach options considered

| Option | Summary | Recommendation |
| --- | --- | --- |
| A. Full shell rewrite in one phase | Replace sidebar with two-bar shell + apply tokens + standardize drawer in one sweep. ~3 plans. | **Recommended.** The chrome is interconnected; landing it half-done creates visual inconsistency across screens. Sized small (no business-logic changes) so the risk is contained to layout regressions. |
| B. Feature-flagged dual chrome | Ship the new shell behind a flag, old sidebar remains default. Cut over once verified. | Adds a second layout system to maintain. Reasonable safety net; only worthwhile if stakeholder demo risk is high. |
| C. Bottom-up component replacement | Build TopShell, gradually adopt per screen. | Slowest; leaves the app in a mixed state for weeks. Reject. |

Selected: **Option A**, with a `quality-gate` plan that exercises every route
through Playwright to catch layout regressions before the loop closes.

## Constraints

- **No feature loss.** Every v0.7-shipped capability remains reachable; the
  feature map in `docs/UX-FEATURE-MAPPING.md` is the contract.
- **No breaking API changes** in Phase 48. The shell is frontend-only.
- **DDD boundaries preserved.** No domain-layer changes; this is presentation.
- **Theme compatibility.** Dark/Light/System theme triple stays working
  (one of the original product constraints from `PROJECT.md`).
- **Accessibility.** WCAG 2.1 AA was achieved in Phase 32; the new shell
  must hold the line — keyboard nav, ARIA landmarks, focus management.
- **Mobile responsive web only** (out of scope: native). Top-bar collapses to
  a hamburger on narrow viewports.

## Dependencies

- **Hard:** none — Phase 48 only touches frontend chrome and Tailwind tokens.
- **Soft:** the existing `command-palette.tsx` (Phase 24) is reused as the
  global `⌘K` affordance, so its plumbing must stay intact.
- **Out of scope for this phase but needed for v0.8 to ship in full:**
  database migrations 017–021 listed in the feature map.

## Open questions (need decision before /paul:plan)

1. **Milestone start timing.** Two paths:
   - (a) Insert v0.8 immediately, parking v0.7 phases 44–47 (file writers,
     etc.) until after the new shell chrome lands.
   - (b) Finish v0.7 first, then start v0.8 Phase 48.
   Trade-off: (a) gets executive demo polish faster but delays file-based
   synthetic; (b) keeps milestone integrity. **Recommend (b)** unless
   stakeholder demand for the the new look is time-critical.
2. **"Project" vs "Workspace" label.** The feature map recommends keeping
   "Project" in DB + code, with UI labels remaining "Project". Confirm.
3. **Primary CTA scope.** "Generate Data ▾" — should this be split-button
   covering all workspace-level actions (Run Discovery, Generate Synthetic,
   Apply Masking, Execute Workflow, Run Subset), or a single-action button
   matching whichever tab is active? Enterprise-TDM references use one button per workspace.
4. **Theme defaults.** Enterprise-TDM references default to dark global chrome + light content.
   DW currently defaults to System. Keep System default but ensure the
   global bar is always dark (the new style) regardless of theme?

These are flagged for the user to answer before `/paul:plan` is run.

## Acceptance criteria (Phase 48)

- [ ] Every existing route renders inside the new TopShell with no console
      errors and no layout overflow.
- [ ] Sidebar is fully removed from the codebase (no dead code).
- [ ] All config flows that previously used a centered modal now use a
      right-side `ContextDrawer`.
- [ ] Playwright E2E suite passes on all current specs without modification
      (any required changes are limited to selectors that pinned to the old
      sidebar, and each is justified).
- [ ] Dark / Light / System theme tested across every workspace tab.
- [ ] Lighthouse a11y score ≥ 95 on the project landing page.
- [ ] No backend / API changes shipped in this phase.

## Proposed v0.8 milestone shape

| Phase | Goal | Notes |
| --- | --- | --- |
| 48 (this) | Two-bar shell + design tokens + drawer standardization | Foundation. Frontend-only. |
| 49 | Privacy Hub project landing page | Reuses existing discovery + masking queries. |
| 50 | Database View — unified column working surface | Merges discovery results + masking-rule editing into one screen. |
| 51 | Generator Presets (table, repo, API, UI) | Migration 018; masking rules gain `preset_id`. |
| 52 | Sensitivity Rules admin page + custom-detector pipeline | Migration 017; integrate into discovery scan. |
| 53 | Recommended Generators bulk apply + linked-column consistency | Migration 021 for `linked_column_ids` + `consistency_group`; masking engine update. |
| 54 | Destination connections + virtual FKs + schema-changes diff | Migration 019, 020. |
| 55 | Final unify + quality gate + v0.8 ship | E2E sweep, docs, release notes. |

## Ready-for-plan checklist

- [x] Vision articulated
- [x] Goals enumerated and scoped narrow
- [x] Approach options documented; recommendation made
- [x] Constraints listed
- [x] Open questions captured for user decision
- [x] Acceptance criteria defined
- [ ] Open question #1 (milestone start timing) answered by user
- [ ] Open question #2 (Project vs Workspace) answered by user
- [ ] Open question #3 (Generate Data CTA scope) answered by user
- [ ] Open question #4 (theme/global-bar relationship) answered by user

Once the open questions are decided, this phase is ready for `/paul:plan` to
generate `48-01-PLAN.md`.

---
*Created: 2026-05-16 — Discuss phase output, feeds /paul:plan*
