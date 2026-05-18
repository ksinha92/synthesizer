# DataWrangler ↔ the enterprise-TDM reference — Feature Mapping & Enhancement Plan

Companion to `UX-DESIGN-GUIDE.md`. Goal: enumerate every Reference concept seen
in the reference screenshots, pair it with the equivalent DataWrangler concept,
and call out **what exists today**, **what's renamed**, **what's net-new**, and
**what must remain even though reference UX has no equivalent**.

User constraint: **no current DW feature is dropped.** the reference's IA may rename
things but everything DW does today keeps working.

## 1. One-to-one concept map

| Reference concept | DataWrangler today | Action |
| --- | --- | --- |
| Workspace | Project (`projects` table, `/projects/[id]/*` routes) | **Rename in UI only**: keep DB term "project", introduce visible label "Workspace" where appropriate, or pick one and stick with it. Recommend keeping "Project" (less ambiguous in a team context) and aligning enterprise-TDM-style chrome around it. |
| Workspace list | `/projects` route + `project-list.tsx` | Re-style as the reference's Workspaces table (Generation Status, Schema Changes, Tags, Permissions, Owner). All columns exist in our model already except **Tags** (need to add a `tags TEXT[]` column on projects or reuse existing settings JSON). |
| Workspace Settings | `/projects/[id]/settings` (currently minimal) + `connection-form-drawer.tsx` for source connection | Expand into a dedicated Settings tab with: Workspace Details (name/description/tags), Connection Type (source/target), Destination Settings, Advanced Overrides. |
| Source Connection | `connections` (`source` role) | Already 1:1. Surface `connector_type` icon prominently like reference UX does. |
| Destination Connection / Output | DW today writes synthetic output to the source connection's database (no separate destination concept) | **Net-new**: introduce **target/destination connection** as a first-class concept on `synthetic_configs`. Schema already has `target_connection_id` (nullable) — wire it through the UI. Add output modes: "same database (new schema)", "different connection", "download file", "S3 bucket" (compliance reports already use S3). Optional later: ephemeral/k8s like reference UX. |
| Sensitivity Scan (auto) | Discovery pipeline (`discovery_tasks.py`, PII detectors) | Already 1:1. UI surfacing weaker — see Privacy Hub below. |
| Sensitivity Type / PII type | `pii_type` enum on `discovered_columns` | Already 1:1. Display the catalog in admin (Sensitivity Rules page). |
| Sensitivity Rules (custom name/regex/value) | **Partial** — we have admin endpoints but no UI surfacing custom rules | **Net-new UI**: add `Sensitivity Rules` page under the global nav. Backend table needed: `sensitivity_rules` with name, pattern (regex / column-name), suggested_preset_id, applies_in. Migration `017_sensitivity_rules.py`. |
| Generator | Masking rule's `masking_type` + `masking_config` | 1:1 in concept, different name. Keep the `masking_type` enum but expose it as "Generator" in UI. |
| Generator Preset (reusable, named generator config) | **Missing** | **Net-new**: `generator_presets` table (name, generator_type, config JSONB, consistency BOOL, occurrences derived). Migration `018_generator_presets.py`. UI: global page with side-drawer edit. Masking rules gain `preset_id` FK. |
| Recommended Generators by Sensitivity Type | **Missing UI**, partial backend (we surface PII detection but not "recommended action") | **Net-new UI** built on existing detection. Each PII type maps to a default generator; group rows by sensitivity type in the panel; "Apply all" creates masking rules in bulk. |
| Linked columns / Consistency-with-another-column | **Missing** | **Net-new**: extend masking rules with `linked_column_ids UUID[]` and `consistency_group` so e.g. City and State stay correlated. Engine update in `masking_engine.py`. |
| Privacy Hub (project dashboard) | `/projects/[id]` landing page (just stat cards) | Replace with Privacy-Hub goal dashboard. Reuse existing PII discovery counts; add the unprotected-columns counter and Recommended Generators panel. |
| Database View (table+column working surface) | Split across `/discovery` and `/masking` pages today | **New combined page** at `/projects/[id]/database` showing all schemas → tables → columns with inline Status (Not Sensitive / Protected / Unprotected) and Applied Generator dropdown. Calls existing discovery + masking endpoints. |
| Table View | `/projects/[id]/discovery` (table-level) | Already exists; restyle to reference UX table layout (compact rows, status pills). |
| Foreign Keys / Virtual Foreign Keys | `discovered_relationships` table + manual override missing | We discover FKs already. **Net-new UI**: a Foreign Keys tab listing all relationships with the ability to add a "virtual FK" (user-asserted relationship without DB constraint). Migration `019_virtual_foreign_keys.py` to flag user-asserted vs discovered. |
| Subsetting (graph + per-table config) | `/projects/[id]/subsetting` + `dependency-graph.tsx` | Already exists, restyle drawer to match reference UX (Target Table Percentage / WHERE Clause / Lookup / Remove). Add inbound/outbound table listings already implied in our relationships table. |
| Schema Changes | **Missing** | **Net-new**: re-run discovery on a connection and surface the diff (added/removed tables, type changes). Implementable as a new endpoint `/discovery/diff` reusing the discovery storage. |
| Post-Job Actions (hooks after generation) | Webhooks (`webhook-manager.tsx`, Phase 19) | 1:1; surface the existing webhook config inside the workspace tab bar as "Post-Job Actions". |
| Jobs view | `/projects/[id]/jobs` + Gantt | Already exists, restyle. |
| Generate Data primary CTA | "Run discovery / Generate / Execute workflow" buttons scattered per page | **Unify**: single right-pinned "Generate Data ▾" split button with options: Run Discovery / Generate Synthetic / Apply Masking / Run Workflow / Run Subset. Wired to existing handlers. |
| Ephemeral DB integration | **Out of scope** | Skip — ephemeral DB provisioning is proprietary. Our equivalent could be docker-compose-based dev DBs later. |
| Structural Settings (system-wide) | `/admin` (Phase 18+) | Already exists. Rename "Admin" → "Settings" in the global nav for parity. |
| Compliance reports (HIPAA/GDPR/CCPA) | Phase 17 — DW-specific, no reference UX equivalent | **Keep** — value-add over reference UX. Surface in workspace tab bar. |
| AI Assistant sidebar | Phase 21 — DW-specific | **Keep** — value-add. Move trigger to the global header. |
| Workflows / DAG canvas | Phase 20, 27 — DW orchestration | **Keep** — reference UX has scheduling but not visual DAG. Worth retaining as power-user feature; surface as a workspace tab. |
| File-based synthetic (copybook / dictionary parsers) | Phase 43 — DW-specific (mainframe focus) | **Keep** — Ameritas-specific value. Add "File-based" as a workspace source type alongside DB connectors. |
| Onboarding wizard + tooltips | Phase 29 | **Keep**, may need re-targeting after IA change. |
| Notification center / activity feed | Phase 28 | **Keep**, slot into the new global header. |

## 2. Net-new capabilities to add

Bundled in priority order. Each row is sized to roughly one phase.

| # | Capability | Phase scope | Backend lift | Frontend lift |
| --- | --- | --- | --- | --- |
| 1 | Two-bar shell (global + workspace tabs) + Generate Data CTA | Layout-only | none | high (replaces app-shell, header, sidebar) |
| 2 | Privacy Hub dashboard at project level | Layout + queries | small (aggregate query) | medium |
| 3 | Database View — unified column-level working surface | Layout + write paths | small (no schema change; reuse masking-rule create) | high |
| 4 | Recommended Generators panel (bulk apply) | Backend + UI | medium (default-generator-by-pii-type table or config) | medium |
| 5 | Generator Presets | Backend + UI | medium (migration 018, repo, API) | high (presets page + drawer) |
| 6 | Sensitivity Rules admin page (user-defined detectors) | Backend + UI | medium (migration 017, integration into discovery scan) | medium |
| 7 | Linked columns / consistency-across-columns | Backend deep | high (masking engine update, deterministic joint generation) | low (UI is a multi-select + toggle) |
| 8 | Destination connection (target) as first-class | Backend + UI | medium (wire `target_connection_id`, output-mode selector) | medium |
| 9 | Foreign Keys tab + virtual FK assertion | Backend + UI | small (migration 019, flag column) | low |
| 10 | Schema Changes tab (rerun discovery diff) | Backend + UI | medium (diff endpoint, retention) | medium |

## 3. Features DW keeps, even though reference UX has no equivalent

These are differentiators; they MUST remain accessible after the refactor.

1. **AI Assistant sidebar** (chat-driven NL prompts → masking/synthetic configs).
2. **Compliance reports** (HIPAA/GDPR/CCPA with PDF export).
3. **Visual workflow DAG canvas** (ReactFlow, scheduled + on-demand).
4. **File-based synthetic** (copybook / Excel dictionary parsers).
5. **RBAC + audit trail** (admin endpoints exist).
6. **Webhook fan-out + Dead-Letter Queue + retry** (we surface these in admin).
7. **Encryption key rotation** (Fernet, admin endpoint).
8. **Notification center / activity feed**.
9. **CLI tool** (Phase 19).
10. **Onboarding wizard + tooltips** (Phase 29).

For each, the design guide specifies *where* they live in the new IA:

- AI Assistant → trigger in global header right side, opens right drawer.
- Compliance → workspace tab bar.
- Workflows → workspace tab bar.
- File-based synthetic → workspace setup choice (source type).
- RBAC / audit / webhooks / key rotation / DLQ → Structural Settings (the renamed Admin).
- Notification center → global header.
- CLI tool → docs entry under Help menu.

## 4. Renames / vocabulary alignment

Strictly **UI labels** — database tables and code identifiers stay put unless
a phase explicitly migrates them.

| DB / code term | UI label after refactor |
| --- | --- |
| Project | Project (kept; "Workspace" considered and rejected) |
| Masking rule | Generator assignment |
| Masking policy | Generator collection (or just keep "Policy") |
| Masking type (`hash`, `redact`, `faker`, …) | Generator type |
| Synthetic config | Generation config |
| Subset config | Subset |
| Discovery result | Sensitivity scan |
| PII type | Sensitivity type |
| Admin | Structural Settings |
| Connections | Connections (source) + Destinations (target) — same table, surface separately |

## 5. Migrations summary (proposed)

| Rev | Purpose |
| --- | --- |
| 017 | `sensitivity_rules` table |
| 018 | `generator_presets` table + `masking_rules.preset_id` FK |
| 019 | `discovered_relationships.is_virtual BOOLEAN` flag |
| 020 | `projects.tags TEXT[]` (or move into existing `settings` JSONB) |
| 021 | `masking_rules.linked_column_ids UUID[]` + `consistency_group TEXT` |

(Numbering picks up from current head `016`; not finalized in code.)

## 6. Open questions

These need a product call before the implementation phases start:

- **"Workspace" vs "Project"** — final label decision.
- **Generator vs Masking rule** terminology — full rename in code or UI-only?
- **Destination connectors** — same connector types as source, or a strict subset?
- **Generator Preset scope** — global only, or also per-project overrides?
- **Linked columns determinism** — same hashing salt across columns, or shared random seed?

Tracked separately; will not block initial chrome / Privacy Hub / Database View
work.
