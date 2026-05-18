# ADR-0003: Hybrid Frontend Design System (shadcn/Tailwind + Ant Design v5)

- **Status:** Accepted
- **Date:** 2026-05-17
- **Deciders:** Synthia core team, frontend lead
- **Tags:** frontend, design-system, ui

**Implementation status (2026-05-17):** verified at the dependency level. `frontend/components.json` and `frontend/tailwind.config.ts` are present, and DATAWRANGLER.md "Tech Stack" lists shadcn/ui + Tailwind + Ant Design v5 + 21st.dev. Theme-token wiring between shadcn and Ant `ConfigProvider`, and the CSS scoping discipline described here, should be audited against current `frontend/src/` usage before extending.

## Context

Synthia's UI has two distinct surfaces with conflicting needs:

1. **App chrome and modern flows** — dashboards, wizards, onboarding, settings, marketing-style landing surfaces, the LLM chat panel. These need a clean, modern SaaS aesthetic, fast iteration, and full theming control (Synthia supports dark + light + system modes).
2. **Heavy data surfaces** — schema explorers, large editable tables, filterable PII review queues, masking rule grids, audit log views. These need battle-tested enterprise components with virtualization, multi-column sort/filter, row selection semantics, and cell editors out of the box.

Building either set of needs in a single component library is wasteful: shadcn/Radix gives unmatched control over chrome but no production-grade data grid; Ant Design ships a deep data grid but a heavy, opinionated aesthetic that fights modern theming.

## Decision

Use a **hybrid design system**:

- **Primary:** [shadcn/ui](https://ui.shadcn.com) + Tailwind CSS for ~80% of the UI (layout, forms, modals, wizards, navigation, theming, marketing/landing surfaces).
- **Secondary:** Ant Design v5 *only* for data-heavy components — Table, Tree, Transfer, Cascader, DatePicker (range), large form grids.
- **Tertiary:** [21st.dev](https://21st.dev) marketplace components for one-off premium UI (animated landing, pricing tables, etc.) when shadcn primitives are not enough.

**Boundary rules:**

- Ant Design CSS is **scoped** (via `ConfigProvider` + namespaced prefix / CSS layer) so it cannot leak into shadcn surfaces.
- Theme tokens (color, radius, spacing) flow from Tailwind/shadcn theme → Ant Design `ConfigProvider` so both libraries share dark/light/system modes.
- New components default to shadcn. Ant Design is reached for only when an Ant component would clearly cost less than building on shadcn primitives.
- 21st.dev components are vendored (not runtime-imported) so license/IP and offline builds are deterministic.

## Consequences

**Positive**
- Modern, brand-controllable chrome with shadcn; production-grade data UX with Ant.
- Single, coherent theme across both libraries via shared design tokens.
- Lower build cost than rebuilding `Table`/`Tree`/`Transfer` on Radix primitives.

**Negative / Tradeoffs**
- Two component vocabularies in one codebase; engineers must learn when to reach for which.
- Bundle size is larger than a single-library approach. Mitigated by route-level code splitting for Ant-heavy screens.
- Style boundary requires discipline; without `ConfigProvider` scoping, Ant resets can leak.

**Neutral**
- Frontend tests are split: Jest for shadcn-side components, Jest + Ant testing utilities for data-grid surfaces.

## Alternatives Considered

- **shadcn/ui only.** Rejected: rebuilding an enterprise-grade Table/Tree on Radix primitives is multi-sprint work outside the product's value path.
- **Ant Design only.** Rejected: Ant's default visual language is hard to make feel modern; theming and dark-mode polish take longer than building chrome on shadcn.
- **Material UI (MUI).** Rejected: opinionated aesthetic similar to Ant but with weaker enterprise data components (DataGrid Pro is paid + license complexity).
- **Custom design system from scratch.** Rejected: out of scope for a 26-week internal tool.

## Related

- Related to: ADR-0002 (DDD), ADR-0013 (single-tenant — internal-only theming is acceptable)
- References: `frontend/components.json`, `frontend/tailwind.config.ts`, DATAWRANGLER.md "Tech Stack"
