# DataWrangler UI — Enterprise-TDM-Inspired Design Guide

Reference target: the enterprise-TDM reference. Goal of this guide is to capture the visual
system, layout conventions, and interaction patterns observed in reference UX so the
DataWrangler UI can converge on a familiar enterprise-TDM look-and-feel
**without removing any existing capability**. See `UX-FEATURE-MAPPING.md`
for the per-feature mapping and gap analysis.

## 1. Information architecture

### 1.1 Two-level navigation

Reference UX separates **product-global** from **workspace-scoped** navigation:

```
┌─ Global top bar (dark) ─────────────────────────────────────────────┐
│  [logo] Workspaces | Generator Presets | Sensitivity Rules | …     │
│  search · help · user                                               │
├─ Workspace tab bar (when inside a workspace) ───────────────────────┤
│  Privacy Hub · Database View · Table View · Foreign Keys · Jobs    │
│  · Schema Changes · Subsetting · Post-Job Actions · Settings        │
│  ────────────────────────────  [ Generate Data ▾ ] (right-aligned)  │
└─────────────────────────────────────────────────────────────────────┘
```

In DataWrangler terms a **workspace ≈ project**. Adopt the same two-bar pattern:

- **Global bar:** Projects · Generator Presets · Sensitivity Rules · Admin · (search · help · user)
- **Project bar:** Privacy Hub · Database View · Discovery · Masking · Synthetic · Subsetting · Workflows · Jobs · Compliance · Settings — with a primary **Generate Data** action pinned far right.

The current DW shell uses a left sidebar; convert to a top-bar dock with the project tab bar appearing only when scoped to a project route.

### 1.2 The primary action — "Generate Data"

Every workspace screen in Reference UX keeps **Generate Data** as a stable, right-side,
slightly-elevated button (gradient/teal background). It's the workspace's main
verb, available regardless of which sub-tab you're on. DW should pin the same
affordance — wired to the existing synthetic generation / workflow execution
path.

## 2. Visual system

### 2.1 Theme & surface

- **Default theme: dark application chrome (global bar) with light content surface.**
- Workspace tab bar is a slightly lighter slate than the global bar.
- Content cards are white in light mode / `slate-900` in dark mode, with
  `1px` neutral borders and `8px` radius.
- Section dividers are subtle (`border-border` at 30% opacity).

### 2.2 Color tokens

Map Tailwind tokens to roles; do not introduce new raw colors in components.

| Role | Token | Notes |
| --- | --- | --- |
| Brand primary | `violet-500` / `violet-600` | Used for logos, primary CTAs, selected nav |
| Accent / "Generate Data" | gradient `teal-500 → violet-500` | Single hero CTA |
| Success (completed) | `emerald-500` | Pills, status dots |
| Running / info | `sky-500` | Animated dot, progress bars |
| Warning (unprotected, low confidence) | `amber-500` | Privacy Hub deficit counters |
| Danger (high confidence PII, failed) | `rose-500` / `red-500` | "High Confidence" pill, failed jobs |
| Neutral pill | `slate-500/10` bg + `slate-700` fg | Tags like "Postgres", "the enterprise-TDM reference Sample" |
| Linked indicator | `violet-500` chain icon + `violet-50` chip | Visual association between columns |

Confidence pills inherit two visual axes: filled color = sensitivity confidence,
icon = generator state (`shield` = protected, `circle` = ignore, `link` = linked).

### 2.3 Typography

- App font: Inter (already in `globals.css`).
- Page title: `text-2xl font-semibold` with a leading 32px icon.
- Section header: `text-sm font-semibold uppercase tracking-wider text-muted-foreground`.
- Table headers: `text-xs font-medium text-muted-foreground`.
- Table body: `text-sm`.
- Monospace (UUIDs, expressions, generator names in code blocks): `font-mono text-xs`.

### 2.4 Spacing & density

Reference UX runs **dense**. Use compact padding for tables:
- Row height: `48px` (current DW uses `56px`).
- Column padding: `12px / 8px`.
- Drawer width: `420–520px` for config drawers (current `600px` is too wide).

## 3. Layout patterns

### 3.1 List-detail with side drawer

Almost every reference UX screen follows: **left table / right slide-in drawer**.

```
┌─ Database View / Sensitivity Rules / Generator Presets ─────────────┐
│ ┌───────────────┬─────────────────────────────┐  ┌─ drawer ──────┐ │
│ │ schema tree   │ table of items (filterable) │  │ Edit Preset   │ │
│ │ [public ▾]    │ ──────────────────────────  │  │ [Config]      │ │
│ │  customers ☐  │ Name | Status | Generator   │  │ [Occurrences] │ │
│ │  orders   ☐   │ row…                        │  │ Generator ▾   │ │
│ │  …            │ row…                        │  │ Consistency ⏿ │ │
│ └───────────────┴─────────────────────────────┘  └───────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

Pattern rules:
- Click a row → drawer opens on the right; row stays selected (highlight).
- Drawer is **non-blocking**: list remains scrollable.
- Drawer has its own internal tabs when the entity has multiple facets
  (Configuration | Occurrences | History).
- Drawer footer always pins **Cancel** + **Save and Apply** to the right.

DW currently does drawers inconsistently — `AccessibleDialog` is used as a full
modal in some places. Standardize to the right-drawer pattern for
column-config, generator-edit, preset-edit, masking-rule-edit, connection-edit.

### 3.2 Privacy-Hub-style goal dashboard

the reference's "Privacy Hub" is a one-screen status check: it counts unprotected
sensitive columns and walks the user toward zero. DW's current dashboard is
metric-heavy. Add a Privacy Hub-style view at the **project level**:

```
┌─ Privacy Hub ──────────────────────────────────────────────────────┐
│                                                                    │
│         42                  0          ⚠ 8                         │
│   Sensitive columns   Protected   Unprotected (action needed)      │
│   ─────────────────  ──────────  ─────────────────────────────     │
│                                                                    │
│   Recommended generators                       [Apply all 8]       │
│   ▸ Address (3 columns, 2 linked)       [Ignore] [Apply]           │
│   ▸ Email (2 columns)                   [Ignore] [Apply]           │
│   ▸ Date of birth (3 columns)           [Ignore] [Apply]           │
│                                                                    │
│   Recent activity        Last generation: 2h ago — Completed       │
└────────────────────────────────────────────────────────────────────┘
```

The "Apply all" bulk action is the **central UX win** Reference UX offers over DW's
current per-column manual configuration.

### 3.3 Database View — schema tree + column table

A single page that lists every column across every table the project sees,
with applied generator and protection status inline. This is the reference's working
surface. DW currently splits this between Discovery and Masking; the design
guide proposes **merging the read-only Discovery results and the editable
masking-policy view into a single Database View**, with two write modes:

- "Apply generator" → writes a masking rule.
- "Mark not sensitive" → overrides PII classification.

The underlying data is already there (discovery + masking are both project-scoped).

### 3.4 Subsetting — graph + per-table drawer

Reference UX shows a hub-and-spoke graph (root table radiating to related tables) and
opens a **Configure Table** drawer per node with: table type (Target % / WHERE
clause / Lookup / Remove), inbound/outbound foreign-key tables, virtual FK
creation. DW already has a subsetting graph (Phase 27); align the per-table
drawer copy + control set with the reference's.

## 4. Component library

These components should be promoted/added to `frontend/src/components/common/`
and used everywhere:

| Component | Purpose | Status |
| --- | --- | --- |
| `TopShell` | Two-bar dark global + light workspace nav | **new** — replaces `app-shell.tsx` sidebar |
| `ContextDrawer` | Right slide-in, header + internal tabs + sticky footer | extend `AccessibleDialog` |
| `StatusPill` | Fixed-vocab status badge (completed, running, failed, draft, protected, not-sensitive) | refactor existing pills |
| `ConfidencePill` | "High / Medium / Low Confidence" with optional icon | **new** |
| `LinkedChip` | Chain icon + tooltip for linked columns | **new** |
| `GeneratorPicker` | Searchable dropdown of generator types, grouped by family (Random / Categorical / Date / Address / …) | **new** |
| `SensitivitySummary` | The Privacy-Hub trio of counters | **new** |
| `RecommendedGeneratorsPanel` | Grouped recommendations with Ignore / Apply per group + bulk "Apply all" | **new** |
| `ColumnPreviewTable` | Tiny 2–5 row table showing original vs replacement | **new** |
| `SchemaTree` | Left-rail tree with collapsible schemas/tables, checkboxes | extend `schema-selector.tsx` |
| `FilterableTable` | AntD `Table` wrapper with per-column filter, sort, and search header | already exists — standardize usage |

## 5. Interaction conventions

- **Single right-side drawer**, never stack drawers; opening a new one replaces
  the current one.
- **Esc** always closes the active drawer/modal. Already partially done via
  `AccessibleDialog`; enforce everywhere.
- **`⌘K` global search** opens a command palette scoped to: workspaces,
  generators, columns, tables. Reuse the existing palette plumbing in
  `command-palette.tsx`.
- **Bulk actions** appear above the table when ≥ 1 row is selected (sticky bar).
- **Apply / Ignore** for recommendations is two-tap: confirmation snackbar with
  Undo, never destructive without an undo affordance.
- **Pinned primary CTA** ("Generate Data" / "Run Workflow") is always
  reachable from any sub-tab.

## 6. enterprise-TDM patterns DW should adopt — quick list

1. Two-bar nav (global + workspace-scoped tabs).
2. Privacy Hub goal dashboard at the project level.
3. **Generator Presets** as a reusable abstraction over masking rules.
4. **Recommended Generators by Sensitivity Type** with one-click bulk apply.
5. Linked columns / consistency toggles (cross-column joint generation).
6. Database View as the single working surface for column-level config.
7. **Sensitivity Rules** admin page for column-name/value-pattern detectors.
8. Right-side context drawer instead of full-screen modals for config edit.
9. Inline status pills with a fixed, small vocabulary.
10. Compact density (smaller row heights, tighter padding).

## 7. Out of scope for the design guide

These are deliberately **not** prescribed here and will be picked up either
by the feature-mapping doc or per-phase plans:

- Visual identity / Ameritas branding decisions.
- Specific Tailwind theme overrides (will be implemented per component).
- Accessibility audit results (a separate phase already covers a11y).
- Mobile breakpoints — reference UX is desktop-first; DW continues to be.
