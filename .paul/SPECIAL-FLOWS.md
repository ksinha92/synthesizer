# Specialized Flows: DataWrangler

## Project-Level Skill Integrations

| Skill | Work Type | Priority | Trigger |
|-------|-----------|----------|---------|
| `/aegis:audit` | Security review — OWASP top 10, credential handling, PII protection | Required | Before any phase marked complete; mandatory before Phase 3 compliance work |

## Phase Overrides

| Phase | Additional Skill | Reason |
|-------|-----------------|--------|
| Phase 3 (Enterprise) | `/aegis:audit` | Compliance reports (HIPAA/GDPR/CCPA) require security posture validation before shipping |

## Templates & Assets

| Asset | Location | Usage |
|-------|----------|-------|
| Full Technical Spec | `DATAWRANGLER.md` | Reference during all phases — DDD structure, DB schema, API endpoints, UI wireframes |
| Sprint-Level Plan | `PLANNING.md` | Task breakdown per role per sprint |
| SEED Ideation | `projects/datawrangler/PLANNING.md` | Consolidated decisions and architecture from ideation |
| Graduated Brief | `apps/datawrangler/README.md` | Synthesized project brief |

## Installation Notes

- **AEGIS**: Not yet installed. Install before Phase 3 Sprint 10.
- **SEED**: Installed at `~/.claude/commands/seed/`. Used for ideation (complete).
- **PAUL**: Installed at `~/.claude/commands/paul/`. Active.

---
*Configured: 2026-03-28*
