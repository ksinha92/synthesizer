# DataWrangler v0.4 — Frontend Completion

> Close all UI/UX gaps identified in the completeness assessment. Take the frontend from ~60% to production-ready (~95%).

---

## Metadata

| Field | Value |
|-------|-------|
| **Type** | Application (continuation) |
| **Status** | Ideation complete — ready for `/seed graduate` |
| **Parent** | DataWrangler (v0.1-v0.3 complete) |
| **Team** | 4+ developers |
| **Timeline** | 12-16 sprints across ~8 phases |

### Skill Loadout
| Tool | Purpose |
|------|---------|
| PAUL | Managed build — plan/apply/unify loop |

---

## Problem Statement

The DataWrangler frontend UI/UX assessment (2026-03-29) found:
- **Structural completeness**: 90% (all pages, stores, hooks exist)
- **Functional completeness**: 60% (most components are skeletons)
- **Visual completeness**: 50% (missing charts, graphs, heatmaps)
- **Competitor feature parity**: 30% (10 features specified, ~1 fully done)
- **Production readiness**: 40% (form validation, accessibility, mobile)

Key issues:
1. AI Assistant sidebar built but **never rendered** (dead code)
2. **Recharts not installed** — all chart-based features blocked
3. **Ant Design installed but never used** — CSS scoping ready, zero Ant components
4. No relationship graph, no subsetting graph, no quality visualization
5. 5 competitor-informed features not started (notifications, comments, onboarding, heatmap, Gantt)

---

## Architecture Decisions

1. **Install Recharts** for all chart visualizations (quality scores, distributions, heatmaps, PII donut)
2. **Use Ant Design Table** for data-heavy tables (PII results, audit log, job list) — already CSS-scoped
3. **Keep native HTML tables** for simple lists (projects, connections, policies)
4. **Wire AssistantSidebar** into root layout with project context from URL params
5. **Use react-hook-form + zod** for form validation standardization
6. **Add @tanstack/react-query** for server state management (replace manual fetch in stores)

---

## Phases (8 phases)

### Phase 25: Wire Missing Components + Install Dependencies
**Effort**: 1 day | **Impact**: Unblocks everything

- Wire `<AssistantSidebar>` into `layout.tsx` with project context
- Install `recharts`, `react-hook-form`, `zod`, `@hookform/resolvers`
- Wire real API data to dashboard stat cards (project count, job count from API)
- Fix Ant Design `.ant-scoped` wrapper — replace 3 key native HTML tables with Ant Table (PII results, audit log, job list)
- Verify assistant sidebar opens/closes from header Bot button

### Phase 26: Quality Visualization + Distribution Charts
**Effort**: 3 days | **Impact**: Core differentiator

- Recharts composite score gauge (0-100 with color gradient)
- Per-column distribution chart: overlaid histogram (real black, synthetic blue) per column
- Correlation heatmap triplet (original / synthetic / difference) — Recharts heatmap
- Privacy metrics display (DCR mean/min, identical matches)
- PII coverage donut chart on dashboard (detected/masked/pending)
- Wire quality API endpoint to frontend

### Phase 27: Relationship + Subsetting Graphs
**Effort**: 3 days | **Impact**: Visual differentiation

- ReactFlow graph in discovery page: nodes = tables (sized by row count), edges = FK relationships
- Click table node → navigate to column detail
- Subsetting dependency graph: same ReactFlow pattern, add traversal direction arrows (upstream/downstream)
- Dry-run analysis table: populate from API (table name, full count, subset count, %)
- Reuse workflow canvas node patterns for consistent styling

### Phase 28: Notification Center + Activity Feed
**Effort**: 2 days | **Impact**: Enterprise UX

- Notification store: in-app notifications from job events (completed/failed)
- Bell icon dropdown panel: notification list with action buttons, unread count badge
- Mark as read / mark all read
- Project activity feed on project detail page (who did what, when)
- Webhook delivery status in notification (if configured)

### Phase 29: Onboarding Wizard + Progressive Disclosure
**Effort**: 2 days | **Impact**: First-time user experience

- 5-step stepper component: Create Project → Add Connection → Run Discovery → Review PII → Apply Masking
- Contextual page highlighting (subtle border glow on target area)
- Skippable, resumable (checklist in sidebar bottom), "don't show again" preference in localStorage
- Progressive disclosure audit: ensure all config forms follow Airbyte pattern (smart defaults, collapsed advanced)
- Connection form: validate all fields have help text tooltips

### Phase 30: Side-by-Side Preview + PII Heatmap + Gantt View
**Effort**: 3 days | **Impact**: Competitor parity

- Enhanced side-by-side preview: column slide-out with 3 tabs (Settings / Sample Data / Comments placeholder)
- Color diff highlighting on changed values
- PII Heatmap on dashboard: CSS grid, each cell = table, color = PII density, click to drill
- Job Gantt timeline view: toggle between list and timeline, Recharts bar chart with temporal overlap
- Dual-mode toggle for masking rules (visual form ↔ JSON editor)

### Phase 31: Form Validation + Ant Design Tables + Skeleton Screens
**Effort**: 3 days | **Impact**: Polish

- Standardize all forms with react-hook-form + zod schemas
- Replace 3 native HTML tables with Ant Design Table (PII results, audit log, job list) — sortable, filterable, virtual scroll
- Skeleton loading screens for all pages (replace spinner placeholders)
- Consistent error display: inline validation + toast notifications
- Optimistic updates for quick actions (toggle, delete)

### Phase 32: Accessibility + Mobile + Final E2E
**Effort**: 3 days | **Impact**: Production readiness

- WCAG 2.1 AA audit: keyboard navigation on all interactive elements, ARIA labels, focus trapping in modals/drawers
- Screen reader testing (VoiceOver) on critical flows
- Color contrast verification (especially in dark mode)
- Mobile responsiveness pass on all 12 pages
- Comprehensive Playwright E2E: full workflow including new features (quality charts, subsetting graph, notifications)
- Cross-browser: Chrome, Firefox, Safari, Edge
- Performance: React.memo on heavy components, virtual scrolling, code splitting verification

---

## Success Criteria

| Metric | Target | Current |
|--------|--------|---------|
| Functional completeness | 95% | 60% |
| Visual completeness | 95% | 50% |
| Competitor feature parity | 80% | 30% |
| Production readiness | 90% | 40% |
| WCAG 2.1 AA compliance | Pass | Not tested |
| Playwright E2E coverage | All 12 pages + new features | 6 pages |
| npm run build | Zero errors | Zero errors |

---

## Open Questions

1. Should inline collaboration (comments, @mentions) be included in v0.4 or deferred to v0.5? It requires backend changes (new comments table + API).
2. Should 21st.dev marketplace components be integrated, or is the native implementation sufficient?
3. Is @tanstack/react-query worth adding now, or keep manual fetch in Zustand stores?

---

## References

| Document | Location |
|----------|----------|
| UI/UX Assessment | `.claude/plans/staged-gliding-moth.md` |
| Full Spec | `DATAWRANGLER.md` (UI/UX Specification section) |
| PAUL State | `.paul/ROADMAP.md` (v0.3 complete) |
