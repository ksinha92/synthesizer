# Synthia v0.10 — Rebrand, Privacy Hub Split, ADR Baseline

**Shipped:** 2026-05-17
**Phases:** Naming decision, UI refactor, ADR baseline
**Features closed:** Product rename, Privacy-Hub-as-landing → dedicated route, icon-only navigation, command palette routing, backend `StorageBackend` DI wiring
**Tests:** Frontend `tsc --noEmit` clean; 5 Playwright spec files updated for new product name; 2 new backend DI unit tests

## Why this milestone

Three threads landed on the same day:

1. **The product needed a name.** The internal codename "DataWrangler" misframed the product (informal, manual-sounding) versus what it actually is (AI-driven, compliance-focused, internal Ameritas TDM). See [ADR-0001](./adr/0001-product-name-synthia.md).
2. **The architectural decisions were undocumented.** Twelve real, load-bearing decisions lived only in `DATAWRANGLER.md` and `PLANNING.md`, with no traceable rationale or status. v0.10 introduces a formal `docs/adr/` directory with thirteen ADRs covering the highest-leverage decisions, each tagged honestly: `Accepted` only when the codebase backs it up; `Proposed` everywhere else.
3. **The project landing page conflated two ideas.** Privacy Hub was the project landing surface, but the same URL was *labeled* "Privacy Hub" in the live `WorkspaceTabBar` — clicking the tab took users back to the landing rather than a focused page. We split them.

## What changed

### Rebrand — DataWrangler → Synthia (Phase 2: UI surfaces)

Per the phased rollout in [ADR-0001](./adr/0001-product-name-synthia.md). Phase 2 covers everything user-visible in the running web app; later phases will rename env vars (compat shims first), Docker images, repo dir, and storage keys.

User-visible changes:

- Browser tab title: `DataWrangler` → `Synthia`
- Metadata description: `AI-Powered Test Data Management Platform` → `Your AI test data partner — production-safe data, generated on demand.`
- Welcome heading at `/`: `Welcome to DataWrangler` → `Welcome to Synthia`
- Login page logo + title: `DW` badge + `DataWrangler` → `S` badge + `Synthia`
- Top nav brand: `DataWrangler` → `Synthia` (with Sparkles icon retained)
- AI Assistant panel header: `DataWrangler Assistant` → `Synthia`
- Connection form helper copy: two strings updated
- Onboarding wizard step 2 description: rewritten with `Synthia`

Not yet renamed (intentional, deferred):

- Repo directory `ameritas-datawrnager/`
- Backend code, modules, schemas, classes, log strings
- Env vars `DATAWRANGLER_*` (compat aliases land in Phase 3)
- Storage keys `datawrangler-redirect`, `datawrangler-sidebar-collapsed` (need migration shim)
- Docker image + container names
- FastAPI `/docs` page title (backend rebuild required)
- Historic docs (`DATAWRANGLER.md`, `PLANNING.md`, prior release notes)

### Privacy Hub split

Before:

```
/projects/[id]/        → <PrivacyHub />                   (the project landing was Privacy Hub)
WorkspaceTabBar.Tab[0] → "Privacy Hub" / suffix=""        (label-vs-target mismatch)
```

After:

```
/projects/[id]/              → <ProjectOverview />        (new 6-tile dashboard)
/projects/[id]/privacy-hub   → <PrivacyHub />             (existing component, dedicated route)
WorkspaceTabBar.Tab[0]       → "Overview" / suffix=""     (matches actual landing)
WorkspaceTabBar.Tab[4]       → "Privacy Hub" / suffix="privacy-hub"  (matches new route)
```

`<PrivacyHub />` itself is unchanged — only the URL it mounts at moved.

`<ProjectOverview />` is a new 6-tile dashboard:

- Project header (name, environment, owner, last-modified)
- 4 stat cards: Tables discovered, Columns classified, Masking coverage %, Total jobs
- Privacy snapshot (3-figure summary + "Review in Privacy Hub →" link)
- Active jobs (filtered `status=running`, with progress bars)
- Recent activity (last 10 jobs across the project)
- Quick actions (Run discovery, Generate compliance report, Open Privacy Hub)

### Icon-only navigation with tooltips

Top global nav + project `WorkspaceTabBar` both icon-only on desktop. Each item exposes a 150ms-delay tooltip with:

- Bold label
- Muted one-line info description

Examples:

- `Privacy Hub` / `Review unprotected PII and apply masking`
- `Sensitivity Rules` / `Define PII detection patterns`
- `Compliance` / `GDPR / HIPAA / CCPA reports`

Mobile drawer keeps full labels (touch has no hover). All links retain `aria-label={label}` for screen readers.

New primitive: `components/ui/tooltip.tsx` — standard shadcn wrapper around the already-installed `@radix-ui/react-tooltip`. Uses `bg-card` / `text-card-foreground` rather than the (undefined-in-this-theme) `bg-popover` token, so tooltips render fully opaque in both light and dark modes.

### Command palette — context-aware routing

The ⌘K command palette previously hardcoded URLs like `/discovery`, `/masking`, `/jobs` — none of which exist as top-level routes. Seven of ten entries 404'd.

After:

- Five global entries (`/`, `/projects`, `/generator-presets`, `/sensitivity-rules`, `/admin`) shown always.
- Thirteen project-scoped entries shown **only** when the user is currently inside a project (URL matches `/projects/[id]/...`). Each is routed against the current `projectId` and tagged with an `in project` pill.
- Placeholder text adapts to context.
- Includes the new `Privacy Hub` route.

### Backend — `StorageBackend` DI wiring (ADR-0010 extension)

Implements one item from [ADR-0010](./adr/0010-pluggable-storage-backend.md)'s **Proposed extensions** list: *DI-resolved `StorageBackend`*.

- `backend/app/container.py`: added `storage_backend = providers.Singleton(_build_storage_backend, settings=settings)`. The factory branches on `settings.STORAGE_BACKEND` ∈ `{local, s3}` and constructs the right concrete class with all required args from `Settings`.
- `backend/app/api/v1/compliance.py:download_report`: switched to `@inject` + `Depends(Provide["storage_backend"])`. Dropped direct `LocalFilesystemStorage` import.
- `backend/app/infrastructure/messaging/compliance_tasks.py`: replaced inline `LocalFilesystemStorage()` with `Container().storage_backend()`.
- `backend/app/infrastructure/messaging/subsetting_tasks.py`: replaced the `if settings.STORAGE_BACKEND == "s3"` inline branch (which silently crashed because `S3Storage()` was called with no args) with `Container().storage_backend()`.
- New `backend/tests/unit/test_container_storage.py`: parametrized test asserting the container resolves to `LocalFilesystemStorage` and `S3Storage` correctly under both env values.

Latent bug fixed: `subsetting_tasks.py`'s `S3Storage()` zero-arg call would have `TypeError`'d the moment `STORAGE_BACKEND=s3` was ever set in production. The new DI path passes all five required constructor args through `Settings`.

ADR-0010 promoted: *DI-resolved `StorageBackend`* moved from `Proposed` to verified-in-code; `Status:` line annotated `DI wiring also Accepted as of 2026-05-17`.

### Architecture Decision Records — baseline

New `docs/adr/` directory with thirteen ADRs plus `README.md` (index + status semantics) and `template.md` (MADR-style template). See the [ADR index](./adr/README.md).

| #    | Title                                                  | Status                                                                           |
| ---- | ------------------------------------------------------ | -------------------------------------------------------------------------------- |
| 0001 | Rename product to Synthia                              | Accepted (decision); rollout Proposed                                            |
| 0002 | Domain-Driven Design with bounded contexts             | Accepted                                                                         |
| 0003 | Hybrid frontend design system (shadcn + Ant Design)    | Accepted                                                                         |
| 0004 | Three synthetic data engines from MVP                  | Accepted (caveat: see ADR-0005)                                                  |
| 0005 | No SDV code dependency (BUSL license)                  | **Proposed** — contradicts current `ctgan` dep                                   |
| 0006 | LLM provider abstraction (Claude + Ollama)             | Accepted (abstraction); routing + outbound-redaction Proposed                    |
| 0007 | SSO via SAML/OIDC + JWT service accounts               | **Proposed** — OIDC partial; SAML lib not in deps                                |
| 0008 | Docker Compose on VMs (not Kubernetes)                 | Accepted                                                                         |
| 0009 | Four-layer PII detection pipeline                      | **Proposed** — end-to-end pipeline not verified against current code             |
| 0010 | Pluggable storage backend                              | Accepted (minimal ABC + Local + S3 + DI); streaming/exists/presign/DB Proposed   |
| 0011 | Event-driven communication between bounded contexts    | **Proposed** — events defined; bus not implemented                               |
| 0012 | Celery + Redis async tasks                             | Accepted (broker); per-queue / DLQ / circuit-breaker policies Proposed           |
| 0013 | Single-tenant internal deployment                      | Accepted                                                                         |

Status discipline: an ADR is `Accepted` only when (a) the listed deciders have ratified it, or (b) the codebase already implements it and the ADR documents the realized decision. Each ADR carries an `Implementation status` note tying its claims to current code or explicitly flagging gaps.

## Dashboard correctness fixes (Project Overview)

Caught and fixed during the Privacy-Hub-split work:

- **False zeros on fetch failure.** Stat cards no longer render `0` when their API source fails — they show `—`. Mechanism: `.catch(() => null)` instead of `.catch(() => empty-shape)`, with state typed `number | null`. Tile bodies (Privacy snapshot, Active jobs, Recent activity) distinguish three states: `null` = fetch failed (error message), `[]` = succeeded with no data (empty state), non-empty = list.
- **Stale data leak across `projectId` changes.** The previous project's name, stat values, and tile data sat in React state through the entire new fetch, causing one painted frame of `Project A`'s data under `/projects/B`'s URL. Fixed with a render-time conditional state reset (the React-sanctioned pattern for prop-driven resets) rather than the broken effect-only approach.
- **`Jobs run today` was wrong by construction.** The client filtered the last 10 jobs by today's date prefix, undercounting any project running >10 jobs/day. Replaced with **Total jobs** sourced from `JobListResponse.total_count`, which the API already returns. Accurate by definition, no extra request.
- **`WorkflowIndicator` preservation.** Initial overview-dev pass dropped the workflow progress indicator (not in the brief's tile list). Re-added as a one-line `<WorkflowIndicator />` mount in `page.tsx` above the dashboard so the workflow-step UX isn't regressed.

## Test updates

| File                                             | Changes                                                                    |
| ------------------------------------------------ | -------------------------------------------------------------------------- |
| `tests/e2e/assistant-notifications.spec.ts`      | 5× `"text=DataWrangler Assistant"` → `"text=Synthia"`                      |
| `tests/e2e/dashboard.spec.ts`                    | 2× `"Welcome to DataWrangler"` → `"Welcome to Synthia"`                    |
| `tests/e2e/accessibility.spec.ts`                | 2× same                                                                    |
| `tests/e2e/user-journeys.spec.ts`                | 1× same                                                                    |
| `tests/e2e/full-workflow.spec.ts`                | `describe("DataWrangler Full Workflow")` + 1× h1 assertion                 |
| `backend/tests/unit/test_container_storage.py`   | **New** — parametrized DI resolution test for Local + S3 backends          |

## Known follow-ups (next milestone)

- **Phase 3 of rebrand:** env var aliases `SYNTHIA_*` with `DATAWRANGLER_*` fallback (one-release compat window). Followed by Phase 4 (service/image names) and Phase 5 (repo dir).
- **ADR-0011 implementation:** event bus + `event_log` table + at least one publish/subscribe reference path (e.g., `PIIDetected` → masking rule suggestion).
- **ADR-0005 resolution:** decide whether to remove `ctgan` (and rebuild the CTGAN path on permissive primitives) or scope the "no SDV-family" stance to *new* dependencies only.
- **ADR-0007 implementation:** ship a working SAML path (currently OIDC + JWT only) or rewrite the ADR to drop SAML.
- **`main.py` wire-list consolidation:** the manual `container.wire(modules=[...])` call lists fewer modules than the `wiring_config` on `Container`. Pick one source of truth.
- **Stale `next dev` shell session.** The dev server has been restarted twice this session because the bash tool's timeout killed the foreground server; future runs should use `nohup … & disown` from the start.

## Migration / deployment notes

- **Backend Docker stack must be rebuilt** to pick up the `storage_backend` DI changes: `make dev-down && make dev` (or `docker compose -f docker-compose.dev.yml up --build backend worker`). Today's UI changes are served by the frontend dev server directly — no backend rebuild required for those.
- **Existing user state preserved**: the `datawrangler-redirect` (session-redirect) and `datawrangler-sidebar-collapsed` (sidebar preference) localStorage keys are unchanged this release. They'll be renamed alongside an automatic migration shim in a later phase.
- **No new env vars, no new migrations** — this release is UI + DI wiring + docs only.
